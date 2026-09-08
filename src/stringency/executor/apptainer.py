"""Apptainer executor (design 10.3).

`apptainer exec --containall --bind <paths> <image.sif> <command>`. The environment digest is
the SIF's sha256 recorded in `envs/manifest.yml` (`environments.<env>.image`, `.sha256`),
verified against the file at run open: a missing image, a missing digest, or a digest that
disagrees with the file yields no digest and `repro.env_unpinned` fires.

The binary is `apptainer` when present, otherwise `singularity` (same command line); the
environment variable `STRINGENCY_APPTAINER_BIN` overrides both. The command recorded in
`executions.command` names whichever was used.

`--containall` hides the host filesystem, so the executor binds everything the job refers to:
the declared `bind_paths`, the working directory, the directory of every existing absolute
path in the command (the script), and the directory of every existing absolute path among the
strings in `stdin_json` (inputs and outputs). Binds nested under another bind are dropped.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from stringency.executor.base import ExecResult, Job
from stringency.operator_exec.envcheck import load_env_manifest


def _paths_in(value: object) -> list[Path]:
    """Existing absolute paths among the strings of a JSON-like value."""
    found: list[Path] = []
    if isinstance(value, str):
        if value.startswith("/") and Path(value).exists():
            found.append(Path(value))
    elif isinstance(value, dict):
        for v in value.values():
            found.extend(_paths_in(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            found.extend(_paths_in(v))
    return found


def bind_set(job: Job) -> list[str]:
    """The host directories a job needs visible inside the container, deduplicated and with
    any directory nested under another dropped."""
    dirs: set[Path] = {Path(p).resolve() for p in job.bind_paths} | {job.cwd.resolve()}
    for arg in job.command:
        for p in _paths_in(str(arg)):
            dirs.add((p if p.is_dir() else p.parent).resolve())
    if job.stdin_json is not None:
        for p in _paths_in(dict(job.stdin_json)):
            dirs.add((p if p.is_dir() else p.parent).resolve())
    ordered = sorted(dirs, key=lambda d: (len(d.parts), str(d)))
    kept: list[Path] = []
    for d in ordered:
        if not any(d == k or k in d.parents for k in kept):
            kept.append(d)
    return sorted(str(d) for d in kept)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


CANDIDATE_BINARIES = ("apptainer", "singularity")


def find_binary() -> str:
    """`STRINGENCY_APPTAINER_BIN` if set, else the first of apptainer, singularity on PATH,
    else `apptainer` so the failure names the expected tool."""
    override = os.environ.get("STRINGENCY_APPTAINER_BIN")
    if override:
        return override
    for name in CANDIDATE_BINARIES:
        if shutil.which(name):
            return name
    return CANDIDATE_BINARIES[0]


class ApptainerExecutor:
    kind = "apptainer"

    def __init__(self, envs_root: Path, binary: str | None = None) -> None:
        self.envs_root = envs_root
        self.binary = binary or find_binary()
        self._verified: dict[str, str | None] = {}

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def image_for(self, env_name: str) -> Path | None:
        entry = load_env_manifest(self.envs_root).get(env_name, {})
        image = entry.get("image")
        if not image:
            return None
        p = Path(str(image))
        if not p.is_absolute():
            p = self.envs_root.parent / p
        return p

    def env_digest(self, env_name: str) -> str | None:
        """The manifest's sha256 for the env, only when the SIF on disk hashes to it."""
        if env_name in self._verified:
            return self._verified[env_name]
        entry = load_env_manifest(self.envs_root).get(env_name, {})
        want = str(entry.get("sha256") or "").removeprefix("sha256:")
        image = self.image_for(env_name)
        digest = None
        if want and image is not None and image.exists() and sha256_file(image) == want:
            digest = want
        self._verified[env_name] = digest
        return digest

    def run(self, job: Job) -> ExecResult:
        job.cwd.mkdir(parents=True, exist_ok=True)
        out = job.stdout_path or job.cwd / "stdout.txt"
        err = job.stderr_path or job.cwd / "stderr.txt"
        image = self.image_for(job.env_name)
        binds = bind_set(job)
        cmd: list[str] = [self.binary, "exec", "--containall", "--pwd", str(job.cwd)]
        for b in binds:
            cmd += ["--bind", b]
        cmd += [str(image) if image else "<no image>", *[str(c) for c in job.command]]
        stdin = (
            json.dumps(dict(job.stdin_json), sort_keys=True) if job.stdin_json is not None else None
        )
        t0 = time.monotonic()
        timed_out = False
        with open(out, "w") as fo, open(err, "w") as fe:
            if image is None or not image.exists():
                fe.write(f"no image for env {job.env_name} in {self.envs_root / 'manifest.yml'}\n")
                code = 127
            else:
                try:
                    proc = subprocess.run(
                        cmd, input=stdin, stdout=fo, stderr=fe, text=True, timeout=job.timeout
                    )
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    code, timed_out = 124, True
                except FileNotFoundError as e:
                    fe.write(f"{e}\n")
                    code = 127
        return ExecResult(
            exit_code=code,
            stdout_path=out,
            stderr_path=err,
            duration_ms=int((time.monotonic() - t0) * 1000),
            env_digest=self.env_digest(job.env_name),
            command=" ".join(cmd),
            timed_out=timed_out,
        )
