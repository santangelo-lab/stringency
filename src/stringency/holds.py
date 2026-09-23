"""Holds (design 7.2, 7.4): creation with rebind of prior verdicts.

Reads: reviews (prior accept/override with the same bindings). Writes: holds; and when a
prior verdict rebinds, the hold is created and immediately resolved by reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from stringency.db.store import Store


@dataclass(frozen=True)
class HoldRequest:
    run_id: str
    step_id: str
    kind: str  # flag | self_uncertain | run_disagreement | confirm
    reason: str
    waits_on_role: str
    bound_module_version: str
    bound_input_digest: str
    bound_params_hash: str
    item_id: str | None = None
    bound_item_evidence_digest: str | None = None
    context: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class HoldOutcome:
    hold_id: str
    rebound: bool  # resolved immediately from a prior verdict
    review_id: str | None


def prior_verdict(store: Store, req: HoldRequest) -> Any:
    """Reads: reviews joined to holds. The most recent accept/override matching the bindings
    and hold kind, or None."""
    sql = (
        "SELECT r.review_id, r.verdict FROM reviews r JOIN holds h ON h.hold_id = r.hold_id "
        "WHERE r.verdict IN ('accept', 'override') AND h.kind = ? "
        "AND r.bound_module_version = ? AND r.bound_input_digest = ? AND r.bound_params_hash = ? "
    )
    params: list[Any] = [
        req.kind,
        req.bound_module_version,
        req.bound_input_digest,
        req.bound_params_hash,
    ]
    if req.item_id is not None:
        sql += "AND h.item_id = ? AND r.bound_item_evidence_digest IS ? "
        params += [req.item_id, req.bound_item_evidence_digest]
    else:
        sql += "AND h.item_id IS NULL "
    sql += "ORDER BY r.ts DESC, r.rowid DESC LIMIT 1"
    return store.one(sql, tuple(params))


def open_hold(store: Store, req: HoldRequest) -> HoldOutcome:
    """Create a hold; if a prior verdict binds to it, resolve it at once with `via: rebind`."""
    prior = prior_verdict(store, req)
    hold_id = store.create_hold(
        {
            "run_id": req.run_id,
            "step_id": req.step_id,
            "item_id": req.item_id,
            "kind": req.kind,
            "reason": req.reason,
            "waits_on_role": req.waits_on_role,
            "bound_module_version": req.bound_module_version,
            "bound_input_digest": req.bound_input_digest,
            "bound_params_hash": req.bound_params_hash,
            "bound_item_evidence_digest": req.bound_item_evidence_digest,
            "context_json": dict(req.context or {}),
        }
    )
    if prior is not None:
        store.resolve_hold(hold_id, prior["review_id"], "rebind")
        return HoldOutcome(hold_id, True, prior["review_id"])
    return HoldOutcome(hold_id, False, None)


def open_holds(store: Store, run_id: str, step_id: str | None = None) -> list[Any]:
    """Reads: holds with no resolving review."""
    if step_id is None:
        return store.all(
            "SELECT * FROM holds WHERE run_id = ? AND resolved_by_review IS NULL AND resolved_via IS NULL ORDER BY created, rowid",
            (run_id,),
        )
    return store.all(
        "SELECT * FROM holds WHERE run_id = ? AND step_id = ? AND resolved_by_review IS NULL AND resolved_via IS NULL "
        "ORDER BY created, rowid",
        (run_id, step_id),
    )
