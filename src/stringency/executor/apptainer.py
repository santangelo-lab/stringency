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
strings in `stdin_json` (inputs and outputs), and `ro_bind_paths` read-only (the project's
method checkout, so shared code beside the modules is reachable; design 10.3, 2026-10-14).
Binds nested under another bind are dropped.
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
    (`/lab/...` for `/data/lab/...` on a workstation that links the two), also at the name the job used, as
    `<resolved>:<as named>`, so the unresolved argument the module receives exists under
    `--containall`."""
    named: set[Path] = {Path(p) for p in job.bind_paths} | {job.cwd}
    for arg in job.command:
        for p in _paths_in(str(arg)):
            named.add(p if p.is_dir() else p.parent)
    if job.stdin_json is not None:
        for p in _paths_in(dict(job.stdin_json)):
            named.add(p if p.is_dir() else p.parent)
    # container path -> (host path, read-only); the identity mapping plus one alias per
    # symlinked name. Read-only binds (the method checkout) come first in the order, so a
    # read-write bind nested under one (the module directory) is dropped and the module sees its
    # own files read-only; a read-only bind nested under a kept read-write one is redundant.
    mappings: dict[Path, tuple[Path, bool]] = {}
    # a directory the job lists in `ro_bind_paths` stays read-only even when a path under it
    # is named by the command or the stdin document (an exec step's inputs, open mode 2026-10-16):
    # only an explicit `bind_paths` entry or the working directory binds read-write there
    explicit_ro = {Path(d).resolve() for d in job.ro_bind_paths}
    explicit_rw = {Path(d).resolve() for d in job.bind_paths} | {job.cwd.resolve()}

    def forced_ro(host: Path) -> bool:
        if host in explicit_rw or any(h in host.parents for h in explicit_rw):
            return False
        return host in explicit_ro or any(h in host.parents for h in explicit_ro)

    def add(d: Path, ro: bool) -> None:
        host = d.resolve()
        if _is_system(host):
            return
        ro = ro or forced_ro(host)
        if host not in mappings or not ro:
            mappings[host] = (host, ro and mappings.get(host, (host, True))[1])
        if d.is_absolute() and d != host and (d not in mappings or not ro):
            mappings[d] = (host, ro and mappings.get(d, (host, True))[1])

    for d in job.ro_bind_paths:
        add(Path(d), True)
    for d in named:
        add(d, False)
    ordered = sorted(mappings, key=lambda c: (len(c.parts), str(c)))
    kept: dict[Path, tuple[Path, bool]] = {}
    for c in ordered:
        host, ro = mappings[c]
        redundant = any(
            (c == kc or kc in c.parents) and kh / c.relative_to(kc) == host
            for kc, (kh, _) in kept.items()
        )
        if not redundant:
            kept[c] = (host, ro)
    out = []
    for c, (h, ro) in kept.items():
        if ro:
            out.append(f"{h}:{c}:ro")
        else:
            out.append(str(h) if c == h else f"{h}:{c}")
    return sorted(out)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


CANDIDATE_BINARIES = ("apptainer", "singularity")


def image_candidates(image: str, envs_root: Path) -> list[Path]:
    """Where an environment manifest's `image` may be (design 10.3, backlog L31): an absolute
    path as given; a bare name or relative path under `$STRINGENCY_IMAGES`, then under the
    user's `images_root` (`~/.config/stringency/config.yml`), then in the method checkout (where
    a relative path pointed before 0.2.19) and its `envs/` directory."""
    from stringency import siteconfig

    p = Path(image)
    if p.is_absolute():
        return [p]
    out: list[Path] = []
    env_root = os.environ.get("STRINGENCY_IMAGES")
    if env_root:
        out.append(Path(env_root) / p)
    site = siteconfig.images_root()
    if site is not None:
        out.append(site / p)
    out.append(envs_root.parent / p)
    out.append(envs_root / p)
    return out


def resolve_image(image: str, envs_root: Path) -> Path:
    """The first candidate that exists, else the first candidate (so a message names where the
    image was looked for)."""
    candidates = image_candidates(image, envs_root)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


_ISOLATION: dict[tuple[str, str], bool] = {}


def network_isolation(binary: str, image: Path | None) -> bool | None:
    """Whether unprivileged `<binary> exec --net --network none <image> /bin/true` works on
    this host (open_mode_plan.md 2.4): True, False, or None when it cannot be tried (no binary,
    no image). Tried once per binary and image for the life of the process; `probe` reports it
    and the executor adds the flags to an `exec` step's line only when it is True."""
    if image is None or not image.exists() or shutil.which(binary) is None:
        return None
    key = (binary, str(image))
    if key not in _ISOLATION:
        try:
            proc = subprocess.run(
                [binary, "exec", "--net", "--network", "none", str(image), "/bin/true"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            _ISOLATION[key] = proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _ISOLATION[key] = False
    return _ISOLATION[key]


NETWORK_FLAGS = ["--net", "--network", "none"]


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
        return resolve_image(str(image), self.envs_root)

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
        if self.network_for(job) == "none":
            cmd += NETWORK_FLAGS
        for b in bind_set(job):
            cmd += ["--bind", b]
        # `--containall` gives the container a 64 MB tmpfs at /tmp; module code that uses
        # tempfile (the splitter stages a whole punch there) fills it. Bind a per-step directory
        # on the data array instead, so temporary files land beside the step's outputs.
        cmd += ["--bind", f"{job.cwd / 'tmp'}:/tmp"]
        cmd += [str(image) if image else "<no image>", *[str(c) for c in job.command]]
        return cmd

    def network_for(self, job: Job) -> str | None:
        """`none` when the job asks for isolation and the host enforces it, `unenforced` when it
        asks and the host cannot, None when it does not ask."""
        if job.network != "none":
            return None
        return (
            "none" if network_isolation(self.binary, self.image_for(job.env_name)) else "unenforced"
        )

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
            network=self.network_for(job),
        )
