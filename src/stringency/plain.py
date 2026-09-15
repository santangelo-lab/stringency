"""Plain sentences for a lay reader (design 12.1 spirit; ux-two-audiences 3.2 and 6).

`run --json` and `status --json` carry `plain`: one or two engine-rendered sentences built from
the pipeline's step titles and the run's statuses, so a skill relays them and composes no
progress prose of its own from codes. The words come from the trace; nothing is interpreted.

Reads: step statuses and the `Next` the loop returned (which read steps, holds, actions, and
predicate_results). Writes nothing.
"""

from __future__ import annotations

from typing import Any

from stringency.config import Roles
from stringency.methods import number_word
from stringency.pipelines import Pipeline


def _join(titles: list[str]) -> str:
    return ", ".join(titles)


def progress_sentence(pipeline: Pipeline, statuses: dict[str, str]) -> str:
    """Which steps have completed, by title, in pipeline order."""
    done = [pipeline.title(s) for s in pipeline.order() if statuses.get(s) == "completed"]
    if not done:
        return "No step has completed."
    return f"Completed: {_join(done)}."


def stop_sentence(
    pipeline: Pipeline,
    roles: Roles,
    kind: str,
    step_id: str | None,
    detail: dict[str, Any],
    statuses: dict[str, str],
) -> str:
    """Where the run stopped and why, one sentence per `Next.kind`."""
    title = pipeline.title(step_id) if step_id else None
    if kind == "held":
        holds = detail.get("holds") or []
        h = holds[0] if holds else {}
        role = h.get("waits_on_role") or "owner"
        who = roles.owner if role == "owner" else roles.reviewer
        more = len(holds) - 1
        tail = (
            f"; {number_word(more)} more decision{'s' if more != 1 else ''} wait"
            if more > 0
            else ""
        )
        if h.get("kind") == "confirm" or not h.get("step_id"):
            return f"Stopped: the plan for this project waits for the owner ({who}) to confirm it{tail}."
        item = f" on item {h['item_id']}" if h.get("item_id") else ""
        return f"Stopped: {pipeline.title(h['step_id'])} waits for the {role} ({who}) to decide{item}{tail}."
    if kind == "blocked":
        return f"Stopped: {title} was blocked before it ran: {_reasons(detail)}."
    if kind == "rejected":
        return f"Stopped: the output of {title} was rejected: {_reasons(detail)}."
    if kind == "failed":
        return f"Stopped: {title} failed to run."
    if kind == "awaiting_execution":
        return f"Stopped: {title} is ready for the operator to run and hand back."
    if kind == "dispatching":
        n = int(detail.get("requests") or 0)
        noun = "judgment" if n == 1 else "judgments"
        return f"Stopped: {number_word(n)} {noun} requested for {title}."
    if kind == "completed":
        until = detail.get("until")
        if until:
            return f"Stopped after {pipeline.title(until)}, as asked."
        return "The run is complete."
    if kind == "runnable":
        waiting = detail.get("waiting_on") or []
        if waiting:
            return f"Next: {title}, after {_join([pipeline.title(w) for w in waiting])}."
        return f"Next: {title}."
    return f"Stopped: {title or 'the run'} is {kind}; the engine cannot continue."


def _reasons(detail: dict[str, Any]) -> str:
    preds = detail.get("predicates") or []
    reasons = [str(p.get("reason") or p.get("predicate_id") or "") for p in preds]
    return "; ".join(r for r in reasons if r) or "no reason recorded"


def plain_next(
    pipeline: Pipeline,
    roles: Roles,
    kind: str,
    step_id: str | None,
    detail: dict[str, Any],
    statuses: dict[str, str],
) -> str:
    """The `plain` field: progress, then the stop, as two sentences on one line."""
    return (
        progress_sentence(pipeline, statuses)
        + " "
        + stop_sentence(pipeline, roles, kind, step_id, detail, statuses)
    )
