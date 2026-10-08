"""Whether the engine is still executing a step (backlog L15).

An engine step writes no trace event between `running` and its outcome, so the console's stale
rule (time since the last event) fired on a clustering step that was computing (lung, 2026-10-08,
eighteen minutes in). While `execute_engine` runs a step's script, the engine keeps a mark at
`runs/<run_id>/.engine-active.json` naming its pid, host and step; the console asks whether that
process is alive instead of how long it has been quiet. The mark is not the trace: nothing reads it
to decide admissibility, and a missing or leftover mark changes only what the console shows.
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

MARK = ".engine-active.json"


def mark_path(root: Path, run_id: str) -> Path:
    return root / "runs" / run_id / MARK


@contextmanager
def executing(root: Path, run_id: str, step_id: str) -> Iterator[None]:
    """Write the mark for the length of the block and remove it after, however the block ends.
    Writes `runs/<run_id>/.engine-active.json` only; no trace table."""
    p = mark_path(root, run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "step_id": step_id,
        "started": datetime.now(UTC).isoformat(),
    }
    tmp = p.with_name(MARK + ".tmp")
    tmp.write_text(json.dumps(body))
    tmp.replace(p)
    try:
        yield
    finally:
        with suppress(OSError):
            p.unlink()


def pid_alive(pid: int) -> bool:
    """True when a process with this pid exists on this host, whoever owns it."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # another account's process: it exists
    return True


def _cmdline(pid: int) -> list[str] | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    return [a.decode(errors="replace") for a in raw.split(b"\0") if a]


def _is_stringency_run(argv: list[str]) -> bool:
    return any(Path(a).name == "stringency" for a in argv) and "run" in argv


def run_process_in(root: Path) -> bool | None:
    """For runs whose engine wrote no mark (0.2.10 and earlier): is a `stringency run` process
    working in this project directory? True when one is found, None otherwise: another account's
    process cannot have its working directory read, so not finding one proves nothing."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    target = root.resolve()
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        argv = _cmdline(int(d.name))
        if not argv or not _is_stringency_run(argv):
            continue
        try:
            cwd = Path(os.readlink(d / "cwd")).resolve()
        except OSError:
            continue
        if cwd == target:
            return True
    return None


def engine_alive(root: Path, run_id: str, step_id: str) -> bool | None:
    """True when the engine executing `step_id` of this run is alive, False when it is gone,
    None when this host cannot tell (the mark names another host, or there is no mark and no
    /proc). Reads the mark and /proc; writes nothing."""
    p = mark_path(root, run_id)
    try:
        mark = json.loads(p.read_text())
    except (OSError, ValueError):
        mark = None
    if isinstance(mark, dict) and mark.get("step_id") == step_id:
        if mark.get("host") != socket.gethostname():
            return None
        pid = mark.get("pid")
        if not isinstance(pid, int) or not pid_alive(pid):
            return False
        argv = _cmdline(pid)
        # a reused pid: the process exists but is not a stringency engine
        return argv is None or any("stringency" in a for a in argv)
    return run_process_in(root)
