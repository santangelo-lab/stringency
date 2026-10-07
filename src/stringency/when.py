"""Conditional steps (L13, design 3.1 and 7.1 as amended 2026-10-07).

A step with `when: {step, param, equals | not_equals}` runs only when the referenced ancestor's
admitted parameter satisfies the condition. When the step is reached (every predecessor
completed or skipped) and the condition is false, the run loop moves it `pending -> skipped`
with the evaluation in the `step_events` payload; successors treat it as done, and an input
bound to its outputs resolves to nothing.

Reads: steps, actions, step_events. Writes nothing; the transition is the run loop's.
"""

from __future__ import annotations

import json
from typing import Any

from stringency.db.store import Store
from stringency.pipelines import Pipeline


def admitted_params(store: Store, run_id: str, step_id: str) -> dict[str, Any] | None:
    """The parameters of the step's latest action in this run, or for a step a fork inherited,
    in the run it was inherited from. None when no action exists. Reads: actions, step_events."""
    seen: set[str] = set()
    while run_id not in seen:
        seen.add(run_id)
        row = store.one(
            "SELECT params_json FROM actions WHERE run_id=? AND step_id=? "
            "ORDER BY attempt DESC, rowid DESC LIMIT 1",
            (run_id, step_id),
        )
        if row is not None:
            return dict(json.loads(row["params_json"]))
        ev = store.one(
            "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? "
            "AND event IN ('status:completed', 'status:skipped') ORDER BY seq DESC LIMIT 1",
            (run_id, step_id),
        )
        parent = json.loads(ev["payload_json"]).get("inherited_from") if ev else None
        if not parent:
            return None
        run_id = str(parent)
    return None


def skip_decision(
    store: Store, pipeline: Pipeline, run_id: str, step_id: str
) -> dict[str, Any] | None:
    """The `step_events` payload that skips the step, or None when it runs (no `when`, the
    condition holds, or the referenced step is not yet decided). A step whose `when` names a
    skipped step is skipped too: the parameter it asks about was never admitted.
    Reads: steps, actions, step_events."""
    when = pipeline.step(step_id).when
    if when is None:
        return None
    ref_status = store.scalar(
        "SELECT status FROM steps WHERE run_id=? AND step_id=?", (run_id, when.step)
    )
    if ref_status == "skipped":
        return {
            "when": when.describe(),
            "actual": None,
            "reason": f"skipped: {pipeline.title(when.step)} was skipped",
        }
    if ref_status != "completed":
        return None
    params = admitted_params(store, run_id, when.step) or {}
    actual = params.get(when.param)
    if when.holds(actual):
        return None
    return {
        "when": when.describe(),
        "actual": actual,
        "reason": f"skipped: {when.param} was {_show(actual)}",
    }


def skip_reason(store: Store, run_id: str, step_id: str) -> str | None:
    """The recorded reason of a skipped step ("skipped: integration was harmony"), or None.
    Reads: step_events."""
    ev = store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? "
        "AND event='status:skipped' ORDER BY seq DESC LIMIT 1",
        (run_id, step_id),
    )
    if ev is None:
        return None
    reason = json.loads(ev["payload_json"]).get("reason")
    return str(reason) if reason else "skipped"


def _show(value: Any) -> str:
    if value is None:
        return "not set"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
