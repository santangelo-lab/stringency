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


# Host system directories are never bound: the image supplies its own. Binding them shadows the
# container's binaries (`/bin/echo` in a command used to bind the host's `/usr/bin` over the
# image's). The engine venv may live under `/usr/local` or `/opt`, so only these exact trees.
_SYSTEM_DIRS = tuple(
    Path(p)
    for p in (
        "/bin",
        "/sbin",
        "/lib",
        "/lib32",
        "/lib64",
        "/libx32",
        "/usr/bin",
        "/usr/sbin",
        "/usr/lib",
        "/usr/lib32",
        "/usr/lib64",
        "/usr/libexec",
        "/usr/share",
        "/usr/include",
        "/etc",
        "/dev",
        "/proc",
        "/sys",
        "/run",
        "/boot",
    )
)


def _is_system(path: Path) -> bool:
    return path == Path("/") or any(path == d or d in path.parents for d in _SYSTEM_DIRS)


def bind_set(job: Job) -> list[str]:
    """The host directories a job needs visible inside the container, deduplicated and with
    any directory nested under another dropped.

    A path is bound at its resolved location, and, when the job named it through a symlink
    (`/lab/...` for `/data/lab/...` on PROTSEQ), also at the name the job used, as
    `<resolved>:<as named>`, so the unresolved argument the module receives exists under
    `--containall`."""
    named: set[Path] = {Path(p) for p in job.bind_paths} | {job.cwd}
    for arg in job.command:
        for p in _paths_in(str(arg)):
            named.add(p if p.is_dir() else p.parent)
    if job.stdin_json is not None:
        for p in _paths_in(dict(job.stdin_json)):
            named.add(p if p.is_dir() else p.parent)
    # container path -> host path; the identity mapping plus one alias per symlinked name
    mappings: dict[Path, Path] = {}
    for d in named:
        host = d.resolve()
        if _is_system(host):
            continue
        mappings[host] = host
        if d.is_absolute() and d != host:
            mappings[d] = host
    ordered = sorted(mappings, key=lambda c: (len(c.parts), str(c)))
    kept: dict[Path, Path] = {}
    for c in ordered:
        host = mappings[c]
        redundant = any(
            (c == kc or kc in c.parents) and kh / c.relative_to(kc) == host
            for kc, kh in kept.items()
        )
        if not redundant:
            kept[c] = host
    return sorted(str(h) if c == h else f"{h}:{c}" for c, h in kept.items())


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

    def command_line(self, job: Job) -> list[str]:
        """`<binary> exec --containall --pwd <cwd> --bind ... <image> <command>`: the argv
        `run` executes, and the line an operator ticket prints."""
        image = self.image_for(job.env_name)
        cmd: list[str] = [self.binary, "exec", "--containall", "--pwd", str(job.cwd)]
        for b in bind_set(job):
            cmd += ["--bind", b]
        # `--containall` gives the container a 64 MB tmpfs at /tmp; module code that uses
        # tempfile (the splitter stages a whole punch there) fills it. Bind a per-step directory
        # on the data array instead, so temporary files land beside the step's outputs.
        cmd += ["--bind", f"{job.cwd / 'tmp'}:/tmp"]
        cmd += [str(image) if image else "<no image>", *[str(c) for c in job.command]]
        return cmd

    def run(self, job: Job) -> ExecResult:
        job.cwd.mkdir(parents=True, exist_ok=True)
        (job.cwd / "tmp").mkdir(exist_ok=True)
        out = job.stdout_path or job.cwd / "stdout.txt"
        err = job.stderr_path or job.cwd / "stderr.txt"
        image = self.image_for(job.env_name)
        cmd = self.command_line(job)
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
