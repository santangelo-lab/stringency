"""Local executor: a subprocess in the current environment.

`env_digest` is the blake3 of `uv.lock` or `renv.lock` under `<method>/envs/<env_name>/`;
with neither present no digest is reported and `repro.env_unpinned` fires.

`interpreter_for` names interpreters portably (`python3`, `Rscript`, `bash`) so the same Job
runs inside a container; this executor resolves `python3` to the engine's own interpreter so
development runs see the engine venv.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from stringency import hashing
from stringency.executor.base import ExecResult, Job

LOCKFILES = ("uv.lock", "renv.lock")


def interpreter_for(script: Path) -> list[str]:
    suffix = script.suffix.lower()
    if suffix == ".py":
        return ["python3", str(script)]
    if suffix in {".r", ".R"}:
        return ["Rscript", str(script)]
    if suffix == ".sh":
        return ["bash", str(script)]
    return [str(script)]


class LocalExecutor:
    kind = "local"

    def __init__(self, envs_root: Path) -> None:
        self.envs_root = envs_root

    def env_digest(self, env_name: str) -> str | None:
        d = self.envs_root / env_name
        for name in LOCKFILES:
            lock = d / name
            if lock.exists():
                return hashing.hash_file(lock)
        return None

    def run(self, job: Job) -> ExecResult:
        job.cwd.mkdir(parents=True, exist_ok=True)
        out = job.stdout_path or job.cwd / "stdout.txt"
        err = job.stderr_path or job.cwd / "stderr.txt"
        stdin = (
            json.dumps(dict(job.stdin_json), sort_keys=True) if job.stdin_json is not None else None
        )
        command = [str(c) for c in job.command]
        if command and command[0] == "python3":
            command[0] = sys.executable
        t0 = time.monotonic()
        timed_out = False
        with open(out, "w") as fo, open(err, "w") as fe:
            try:
                proc = subprocess.run(
                    command,
                    cwd=job.cwd,
                    input=stdin,
                    stdout=fo,
                    stderr=fe,
                    text=True,
                    timeout=job.timeout,
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
            command=" ".join(command),
            timed_out=timed_out,
        )
