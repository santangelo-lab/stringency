"""Agreement and consensus (design 8.4). No majority vote: dissent is the information.

Writes: consensus (via the store), holds (through `holds.open_hold`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from stringency import hashing
from stringency.db.store import Store
from stringency.holds import HoldOutcome, HoldRequest, open_hold
from stringency.policy import AgreementRule
from stringency.predicates.context import EvidenceTable
from stringency.repeat import Replicate


@dataclass
class ItemConsensus:
    item_id: str
    label: str | None
    ontology_id: str | None
    source: str  # agreed | accepted | override | unresolved
    replicate_labels: list[str | None]
    replicate_confidence: list[str | None]
    hold_kind: str | None = None
    hold_reason: str | None = None
    review_id: str | None = None
    hold_id: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "label": self.label,
            "ontology_id": self.ontology_id,
            "source": self.source,
            "replicate_labels": self.replicate_labels,
            "replicate_confidence": self.replicate_confidence,
            "review_id": self.review_id,
            "hold_id": self.hold_id,
            "notes": self.notes,
        }


def item_judgments(
    replicates: list[Replicate], item_id: str
) -> list[tuple[int, dict[str, Any] | None]]:
    """(replicate index, judgment or None when that replicate is invalid or lacks the item)."""
    out: list[tuple[int, dict[str, Any] | None]] = []
    for rep in replicates:
        j = (
            next((i for i in rep.items() if str(i.get("item_id")) == item_id), None)
            if rep.valid
            else None
        )
        out.append((rep.index, j))
    return out


def decide(item_id: str, replicates: list[Replicate], rule: AgreementRule) -> ItemConsensus:
    js = item_judgments(replicates, item_id)
    labels = [j.get("label") if j else None for _, j in js]
    confs = [j.get("confidence") if j else None for _, j in js]
    ic = ItemConsensus(item_id, None, None, "unresolved", labels, confs)
    hold_on = set(rule.hold_on)
    invalid = [i for i, j in js if j is None]
    if invalid and "any_invalid" in hold_on:
        ic.hold_kind, ic.hold_reason = "run_disagreement", f"invalid replicate(s) {invalid}"
        return ic
    valid = [j for _, j in js if j is not None]
    abstained = [j for j in valid if j.get("abstain")]
    called = [j for j in valid if not j.get("abstain")]
    distinct = {j.get("label") for j in called}
    if len(distinct) > 1:
        ic.hold_kind, ic.hold_reason = (
            "run_disagreement",
            f"labels differ: {sorted(str(d) for d in distinct)}",
        )
        return ic
    if valid and len(abstained) == len(valid):
        ic.hold_kind, ic.hold_reason = "self_uncertain", "every replicate abstained"
        return ic
    if abstained and "any_abstain" in hold_on:
        ic.hold_kind, ic.hold_reason = "self_uncertain", f"{len(abstained)} replicate(s) abstained"
        return ic
    lows = [j for j in called if j.get("confidence") == "low"]
    if lows and "any_low" in hold_on:
        ic.hold_kind, ic.hold_reason = (
            "self_uncertain",
            f"{len(lows)} replicate(s) reported low confidence",
        )
        return ic
    if not called:
        ic.hold_kind, ic.hold_reason = "self_uncertain", "no valid call"
        return ic
    ic.source = "agreed"
    ic.label = called[0].get("label")
    ic.ontology_id = called[0].get("ontology_id")
    if abstained:
        ic.notes.append(f"{len(abstained)} abstention(s) logged under relaxed agreement")
    if lows:
        ic.notes.append(f"{len(lows)} low-confidence call(s) logged under relaxed agreement")
    return ic


def item_evidence_digest(tables: Mapping[str, EvidenceTable], item_id: str) -> str:
    rows = {name: t.rows.get(item_id) for name, t in tables.items()}
    return hashing.prefixed(hashing.hash_json(rows))


def apply_review(
    store: Store, ic: ItemConsensus, review_id: str, replicates: list[Replicate]
) -> None:
    """Take the label a prior or current review settled on (design 7.3)."""
    row = store.one("SELECT * FROM reviews WHERE review_id = ?", (review_id,))
    if row is None:
        return
    ic.review_id = review_id
    if row["verdict"] == "override" and row["correction_json"]:
        corr = json.loads(row["correction_json"])
        ic.label, ic.ontology_id, ic.source = corr.get("label"), corr.get("ontology_id"), "override"
    elif row["verdict"] == "accept":
        chosen = row["chosen_replicate"]
        js = dict(item_judgments(replicates, ic.item_id))
        j = (
            js.get(chosen)
            if chosen is not None
            else next((v for v in js.values() if v and not v.get("abstain")), None)
        )
        if j is not None:
            ic.label, ic.ontology_id = j.get("label"), j.get("ontology_id")
        ic.source = "accepted"
    ic.hold_kind = None


def settle_items(
    store: Store,
    *,
    run_id: str,
    step_id: str,
    module_ref: str,
    input_digest: str,
    params_hash: str,
    items: list[str],
    replicates: list[Replicate],
    rule: AgreementRule,
    tables: Mapping[str, EvidenceTable],
) -> tuple[list[ItemConsensus], list[HoldOutcome]]:
    """Consensus per item; a hold per disagreeing, abstaining, or low-confidence item, with
    rebind of prior verdicts. Writes: consensus, holds."""
    out: list[ItemConsensus] = []
    holds: list[HoldOutcome] = []
    for item in items:
        ic = decide(item, replicates, rule)
        if ic.hold_kind is not None:
            h = open_hold(
                store,
                HoldRequest(
                    run_id=run_id,
                    step_id=step_id,
                    kind=ic.hold_kind,
                    reason=ic.hold_reason or ic.hold_kind,
                    waits_on_role="reviewer",
                    bound_module_version=module_ref,
                    bound_input_digest=input_digest,
                    bound_params_hash=params_hash,
                    item_id=item,
                    bound_item_evidence_digest=item_evidence_digest(tables, item),
                    context={
                        "replicate_labels": ic.replicate_labels,
                        "replicate_confidence": ic.replicate_confidence,
                    },
                ),
            )
            holds.append(h)
            ic.hold_id = h.hold_id
            if h.rebound and h.review_id:
                apply_review(store, ic, h.review_id, replicates)
                ic.notes.append("resolved by rebind to a prior review")
        store.set_consensus(
            {
                "run_id": run_id,
                "step_id": step_id,
                "item_id": item,
                "label": ic.label,
                "ontology_id": ic.ontology_id,
                "source": ic.source,
                "replicate_labels_json": ic.replicate_labels,
                "replicate_confidence_json": ic.replicate_confidence,
                "review_id": ic.review_id,
            }
        )
        out.append(ic)
    return out, holds


def consensus_json(
    items: list[ItemConsensus], considered_set: Mapping[str, Any] | None = None
) -> str:
    """The consensus output. With `considered_set` (a module declaring `considered_set: true`),
    the denominator record the engine took from the items table rides along (design 3.5, E2)."""
    doc: dict[str, Any] = {"consensus": 1, "items": [i.to_json() for i in items]}
    if considered_set is not None:
        doc["considered_set"] = dict(considered_set)
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def consensus_from_store(
    store: Store, run_id: str, step_id: str, items: list[str]
) -> list[ItemConsensus]:
    """The decided consensus of a step, one record per item in the judgment's item order (items
    the table no longer lists come last). Reads: consensus, holds. This is what the consensus
    output is rewritten from when the last item hold settles (design 8.4): the store's rows,
    never a replicate."""
    rows = {
        str(r["item_id"]): r
        for r in store.all(
            "SELECT * FROM consensus WHERE run_id = ? AND step_id = ?", (run_id, step_id)
        )
    }
    order = [str(i) for i in items] + [i for i in rows if i not in {str(x) for x in items}]
    out: list[ItemConsensus] = []
    for item in order:
        r = rows.get(item)
        if r is None:
            continue
        hold = store.one(
            "SELECT hold_id FROM holds WHERE run_id = ? AND step_id = ? AND item_id = ? "
            "ORDER BY rowid DESC LIMIT 1",
            (run_id, step_id, item),
        )
        ic = ItemConsensus(
            item_id=item,
            label=r["label"],
            ontology_id=r["ontology_id"],
            source=r["source"],
            replicate_labels=json.loads(r["replicate_labels_json"]),
            replicate_confidence=json.loads(r["replicate_confidence_json"]),
            review_id=r["review_id"],
            hold_id=hold["hold_id"] if hold is not None else None,
        )
        if r["source"] in ("accepted", "override") and r["review_id"]:
            ic.notes.append(f"{r['source']} by review {r['review_id']}")
        out.append(ic)
    return out
