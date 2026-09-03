"""Step and run states, transitions, events (design 7.1).

Every transition goes through `transition`, which checks the edge against the table in 7.1
and writes the `step_events` row in the same transaction as the status change (via the store).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from stringency.db.store import Store


class StepStatus(StrEnum):
    PENDING = "pending"
    PROPOSED = "proposed"
    ADMISSIBLE = "admissible"
    HELD = "held"
    BLOCKED = "blocked"
    RUNNING = "running"
    AWAITING_EXECUTION = "awaiting_execution"
    DISPATCHING = "dispatching"
    PRODUCED = "produced"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


S = StepStatus

# (from, to) edges from design 7.1
EDGES: frozenset[tuple[StepStatus, StepStatus]] = frozenset(
    {
        (S.PENDING, S.PROPOSED),
        (S.PROPOSED, S.ADMISSIBLE),
        (S.PROPOSED, S.HELD),
        (S.PROPOSED, S.BLOCKED),
        (S.ADMISSIBLE, S.RUNNING),
        (S.ADMISSIBLE, S.AWAITING_EXECUTION),
        (S.ADMISSIBLE, S.DISPATCHING),
        (S.AWAITING_EXECUTION, S.RUNNING),
        (S.DISPATCHING, S.RUNNING),
        (S.RUNNING, S.PRODUCED),
        (S.RUNNING, S.FAILED),
        (S.PRODUCED, S.COMPLETED),
        (S.PRODUCED, S.HELD),
        (S.PRODUCED, S.REJECTED),
        (S.HELD, S.ADMISSIBLE),
        (S.HELD, S.COMPLETED),
        (S.HELD, S.BLOCKED),
        (S.HELD, S.REJECTED),
        (S.BLOCKED, S.PROPOSED),
        (S.REJECTED, S.PROPOSED),
        (S.FAILED, S.PROPOSED),
    }
)

TERMINAL_FOR_ATTEMPT = frozenset({S.BLOCKED, S.REJECTED, S.FAILED})
RETRYABLE = TERMINAL_FOR_ATTEMPT | {S.PENDING}


class IllegalTransition(Exception):
    pass


def step_status(store: Store, run_id: str, step_id: str) -> StepStatus:
    s = store.scalar("SELECT status FROM steps WHERE run_id = ? AND step_id = ?", (run_id, step_id))
    if s is None:
        raise KeyError(f"no step {step_id} in run {run_id}")
    return StepStatus(s)


def all_step_status(store: Store, run_id: str) -> dict[str, str]:
    return {
        r["step_id"]: r["status"]
        for r in store.all("SELECT step_id, status FROM steps WHERE run_id = ?", (run_id,))
    }


def transition(
    store: Store,
    run_id: str,
    step_id: str,
    to: StepStatus,
    *,
    payload: Mapping[str, Any] | None = None,
    attempt: int | None = None,
) -> None:
    """Move a step along one edge of 7.1. Writes: step_events then steps.status."""
    frm = step_status(store, run_id, step_id)
    if (frm, to) not in EDGES:
        raise IllegalTransition(f"{step_id}: {frm} -> {to} is not a transition in design 7.1")
    store.set_step_status(
        run_id,
        step_id,
        str(to),
        dict(payload or {}),
        attempt=attempt,
        started=to in {S.RUNNING, S.AWAITING_EXECUTION, S.DISPATCHING},
        ended=to in {S.COMPLETED, S.REJECTED, S.FAILED, S.BLOCKED},
    )


def derive_run_status(statuses: Mapping[str, str], order: list[str]) -> str:
    """Design 7.1: held if any step is held; blocked or failed if the frontier is; completed
    when every step is completed; otherwise running."""
    vals = [statuses.get(s, "pending") for s in order]
    if any(v == "held" for v in vals):
        return "held"
    if all(v == "completed" for v in vals):
        return "completed"
    for v in vals:
        if v == "completed":
            continue
        if v in ("blocked", "rejected"):
            return "blocked"
        if v == "failed":
            return "failed"
        break
    return "running"
