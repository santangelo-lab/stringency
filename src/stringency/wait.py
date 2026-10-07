"""`stringency wait` (design 14.1, added 2026-10-07): block until a person has answered.

An operator that has handed a hold to a person sleeps on `wait --hold <id>` instead of polling
`run`; a Claude Code session arms it as a background command and is re-invoked when it returns.
`wait --run <id>` returns when anything about the run changes: its status, a step's status, or
the set of open holds. Polls the trace every few seconds over a read-only connection; never
writes.

Reads: holds, reviews, runs, steps.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.db.store import Store, refuse_network_filesystem
from stringency.exit_codes import ConfigError, Exit

POLL_SECONDS = 5.0
CLOSED = ("completed", "abandoned")


@dataclass
class WaitResult:
    event: str  # resolved | withdrawn | changed | closed | timeout
    exit_code: int
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "stringency.wait/1",
            "event": self.event,
            "exit_code": self.exit_code,
            "message": self.message,
            **self.detail,
        }


def open_read_only(root: Path) -> Store:
    """A read-only connection to the project's trace; no migration, no pragma that writes."""
    path = root / "prov" / "run.db"
    refuse_network_filesystem(path)
    if not path.exists():
        raise ConfigError(f"no trace database at {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return Store(conn, path)


def _poll[T](
    read: Callable[[], T | None],
    *,
    timeout: float | None,
    poll: float,
    sleep: Callable[[float], None],
) -> tuple[T | None, float]:
    """Call `read` until it returns something or the timeout passes."""
    start = time.monotonic()
    while True:
        got = read()
        waited = time.monotonic() - start
        if got is not None:
            return got, waited
        if timeout is not None and waited >= timeout:
            return None, waited
        sleep(poll if timeout is None else max(0.0, min(poll, timeout - waited)))


def wait_hold(
    store: Store,
    hold_id: str,
    *,
    timeout: float | None = None,
    poll: float = POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> WaitResult:
    """Return when the hold is resolved by a review or withdrawn. Reads: holds, reviews."""
    first = store.one("SELECT * FROM holds WHERE hold_id = ?", (hold_id,))
    if first is None:
        raise ConfigError(f"no hold {hold_id} in this project")

    def read() -> Any:
        h = store.one("SELECT * FROM holds WHERE hold_id = ?", (hold_id,))
        if h is not None and (h["resolved_by_review"] or h["resolved_via"]):
            return h
        return None

    h, waited = _poll(read, timeout=timeout, poll=poll, sleep=sleep)
    base = {
        "hold_id": hold_id,
        "run_id": first["run_id"],
        "step_id": first["step_id"],
        "item_id": first["item_id"],
        "kind": first["kind"],
        "waited_s": round(waited, 1),
    }
    if h is None:
        return WaitResult(
            "timeout",
            int(Exit.HELD),
            f"hold {hold_id} is still open after {round(waited)} s",
            base,
        )
    if not h["resolved_by_review"]:
        return WaitResult(
            "withdrawn",
            int(Exit.OK),
            f"hold {hold_id} was withdrawn ({h['resolved_via']}); no one reviewed it",
            {**base, "resolved_via": h["resolved_via"], "review": None},
        )
    r = store.one("SELECT * FROM reviews WHERE review_id = ?", (h["resolved_by_review"],))
    review = (
        {
            "review_id": r["review_id"],
            "verdict": r["verdict"],
            "reason": r["reason"],
            "reviewer": r["reviewer"],
            "via": r["via"],
            "ts": r["ts"],
        }
        if r is not None
        else None
    )
    msg = f"hold {hold_id} resolved"
    if review is not None:
        reason = f': "{review["reason"]}"' if review["reason"] else ""
        msg = (
            f"hold {hold_id} resolved: {review['verdict']} by {review['reviewer']} "
            f"via {review['via']}{reason}"
        )
    return WaitResult(
        "resolved",
        int(Exit.OK),
        msg,
        {**base, "resolved_via": h["resolved_via"], "review": review},
    )


def _run_reading(store: Store, run_id: str) -> dict[str, Any]:
    run = store.one("SELECT status FROM runs WHERE run_id = ?", (run_id,))
    assert run is not None
    steps = {
        r["step_id"]: r["status"]
        for r in store.all("SELECT step_id, status FROM steps WHERE run_id = ?", (run_id,))
    }
    holds = sorted(
        r["hold_id"]
        for r in store.all(
            "SELECT hold_id FROM holds WHERE run_id = ? "
            "AND resolved_by_review IS NULL AND resolved_via IS NULL",
            (run_id,),
        )
    )
    return {"status": run["status"], "steps": steps, "open_holds": holds}


def wait_run(
    store: Store,
    run_id: str,
    *,
    timeout: float | None = None,
    poll: float = POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> WaitResult:
    """Return when the run's status, a step's status, or its open holds change; at once when
    the run is already closed. Reads: runs, steps, holds."""
    if store.one("SELECT run_id FROM runs WHERE run_id = ?", (run_id,)) is None:
        raise ConfigError(f"no run {run_id} in this project")
    before = _run_reading(store, run_id)
    if before["status"] in CLOSED:
        return WaitResult(
            "closed",
            int(Exit.OK),
            f"run {run_id} is {before['status']}",
            {"run_id": run_id, "before": before, "after": before, "waited_s": 0.0},
        )

    def read() -> dict[str, Any] | None:
        now = _run_reading(store, run_id)
        return now if now != before else None

    after, waited = _poll(read, timeout=timeout, poll=poll, sleep=sleep)
    detail = {"run_id": run_id, "before": before, "after": after, "waited_s": round(waited, 1)}
    if after is None:
        return WaitResult(
            "timeout",
            int(Exit.HELD),
            f"run {run_id} unchanged after {round(waited)} s ({before['status']})",
            detail,
        )
    changed = sorted(s for s in after["steps"] if after["steps"][s] != before["steps"].get(s))
    parts = [f"run {run_id} is {after['status']}"]
    if changed:
        parts.append("steps changed: " + ", ".join(f"{s} {after['steps'][s]}" for s in changed))
    resolved = sorted(set(before["open_holds"]) - set(after["open_holds"]))
    opened = sorted(set(after["open_holds"]) - set(before["open_holds"]))
    if resolved:
        parts.append("holds closed: " + ", ".join(resolved))
    if opened:
        parts.append("holds opened: " + ", ".join(opened))
    return WaitResult("changed", int(Exit.OK), "; ".join(parts), detail)
