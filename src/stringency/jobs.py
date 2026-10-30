"""Detached verbs (L134 c): `run`, `call`, `exec`, `deliver` and `controls run` take `--detach`.

An operator behind a command limit (Claude Science's compute connection ends a command after
sixty seconds) starts the verb with `--detach`: the verb starts itself again in a child that
survives the parent (a new session, `setsid`), prints `{job_id, pid, log}` and exits 0 at once.
`wait --job <id>` blocks until the child has exited and then prints what the verb printed, with
its exit code.

    <project>/prov/jobs/<job_id>/
      job.json     {job_id, argv, cwd, host, pid, started}
      stdout       what the verb printed (its JSON payload when it was given --json)
      stderr       its messages: the `log` the payload names
      stdin        the parent's standard input, kept when the command line reads `-`
      exit.json    {exit_code, ended}, written by the child as it exits

Nothing here touches the trace: the child is the ordinary verb, which writes the trace as it
would in the foreground. Reads and writes only the files above.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stringency.clock import now_iso
from stringency.exit_codes import ConfigError, Exit
from stringency.ids import new_id

JOB_ENV = "STRINGENCY_JOB_DIR"
POLL_SECONDS = 1.0


def find_root(start: Path | None = None) -> Path:
    """The project directory at or above `start` (a `stringency.yml`), found without loading the
    project or its plugin."""
    cur = (start or Path.cwd()).resolve()
    for cand in (cur, *cur.parents):
        if (cand / "stringency.yml").exists():
            return cand
    raise ConfigError("no stringency project found here or in a parent directory")


def jobs_dir(root: Path) -> Path:
    return Path(root) / "prov" / "jobs"


def child_argv(argv: list[str] | None = None) -> list[str]:
    """The command line the child runs: this process's own arguments without `--detach`.
    Refuses when the arguments are not a `stringency` command line carrying `--detach` (a verb
    called in-process, as a test runner does, has no command line to start again)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--detach" not in args:
        raise ConfigError(
            "--detach starts the verb's own command line again in a child; it needs the "
            "`stringency` command line, not an in-process call"
        )
    return [a for a in args if a != "--detach"]


def detach(argv: list[str] | None = None, *, root: Path | None = None) -> dict[str, Any]:
    """Start the verb in a detached child and return `{job_id, pid, log}` with the job's files.
    The child is `python -P -m stringency.cli.app <argv>` in this directory, in its own session,
    its stdin the saved standard input when the command line reads `-` (else nothing), its
    stdout and stderr the job's files. Writes: `prov/jobs/<job_id>/` (job.json, stdin)."""
    args = child_argv(argv)
    root = find_root() if root is None else Path(root)
    job_id = new_id()
    d = jobs_dir(root) / job_id
    d.mkdir(parents=True)
    stdin_path: Path | None = None
    if "-" in args:
        stdin_path = d / "stdin"
        stdin_path.write_bytes(sys.stdin.buffer.read() if not sys.stdin.isatty() else b"")
    env = {**os.environ, JOB_ENV: str(d)}
    cmd = [sys.executable, "-P", "-m", "stringency.cli.app", *args]
    with contextlib.ExitStack() as stack:
        out = stack.enter_context((d / "stdout").open("wb"))
        err = stack.enter_context((d / "stderr").open("wb"))
        fin: Any = (
            stack.enter_context(stdin_path.open("rb"))
            if stdin_path is not None
            else subprocess.DEVNULL
        )
        proc = subprocess.Popen(  # noqa: S603 - this engine's own command line
            cmd,
            cwd=os.getcwd(),
            stdin=fin,
            stdout=out,
            stderr=err,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
    record = {
        "job_id": job_id,
        "argv": ["stringency", *args],
        "cwd": os.getcwd(),
        "host": socket.gethostname(),
        "pid": proc.pid,
        "started": now_iso(),
    }
    (d / "job.json").write_text(json.dumps(record, indent=2) + "\n")
    return {
        "schema": "stringency.job/1",
        "job_id": job_id,
        "pid": proc.pid,
        "log": str(d / "stderr"),
        "stdout": str(d / "stdout"),
        "wait": f"stringency wait --job {job_id}",
    }


def detached_text(p: dict[str, Any]) -> str:
    return (
        f"job {p['job_id']} started (pid {p['pid']}); log {p['log']}\n"
        f"`{p['wait']}` prints what it printed, with its exit code, once it has exited"
    )


def run_as_job(job_dir: Path, entry: Callable[[], Any]) -> None:
    """The child's side: run the verb, then write `exit.json` with its exit code, whatever the
    verb did. Writes: `prov/jobs/<job_id>/exit.json` (by rename, so a reader never sees half)."""
    code = 0
    try:
        entry()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except BaseException:  # noqa: BLE001 - recorded as an internal error, then exit 1
        traceback.print_exc()
        code = int(Exit.INTERNAL)
    finally:
        with contextlib.suppress(Exception):
            sys.stdout.flush()
            sys.stderr.flush()
        tmp = job_dir / "exit.json.tmp"
        tmp.write_text(json.dumps({"exit_code": code, "ended": now_iso()}) + "\n")
        tmp.replace(job_dir / "exit.json")
    raise SystemExit(code)


@dataclass
class JobResult:
    state: str  # exited | running | lost
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    detail: dict[str, Any] | None = None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_job(
    root: Path,
    job_id: str,
    *,
    timeout: float | None = None,
    poll: float = POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> JobResult:
    """Block until the job's child has exited (its `exit.json`), the timeout passes (`running`,
    exit 10, as `wait` does at a timeout), or the child is gone without an exit record on this
    host (`lost`, exit 1). Reads: `prov/jobs/<job_id>/`. Writes nothing."""
    d = jobs_dir(root) / job_id
    if "/" in job_id or job_id in ("", ".", "..") or not (d / "job.json").is_file():
        raise ConfigError(f"no job {job_id} in {root}")
    rec = json.loads((d / "job.json").read_text())
    pid = int(rec.get("pid") or 0)
    here = rec.get("host") == socket.gethostname()
    start = time.monotonic()
    while True:
        ex = d / "exit.json"
        if ex.is_file():
            code = int(json.loads(ex.read_text()).get("exit_code", 1))
            return JobResult(
                "exited",
                code,
                (d / "stdout").read_text(errors="replace"),
                (d / "stderr").read_text(errors="replace"),
            )
        if here and pid and not _alive(pid) and not ex.is_file():
            return JobResult(
                "lost",
                int(Exit.INTERNAL),
                "",
                (d / "stderr").read_text(errors="replace"),
                {
                    "job_id": job_id,
                    "pid": pid,
                    "log": str(d / "stderr"),
                    "message": f"job {job_id}: pid {pid} ended without recording an exit code",
                },
            )
        waited = time.monotonic() - start
        if timeout is not None and waited >= timeout:
            return JobResult(
                "running",
                int(Exit.HELD),
                detail={
                    "job_id": job_id,
                    "pid": pid,
                    "log": str(d / "stderr"),
                    "argv": rec.get("argv"),
                    "started": rec.get("started"),
                    "waited_s": round(waited, 1),
                    "message": f"job {job_id} is still running after {waited:.0f}s; "
                    f"`stringency wait --job {job_id}` again",
                },
            )
        sleep(poll if timeout is None else max(0.0, min(poll, timeout - waited)))
