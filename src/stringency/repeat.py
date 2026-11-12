"""Replicated invocations (design 3.5 step 4, 9.3): validate each response against the
schema, retry once in the direct family with the error appended, record every invocation.

Writes: invocations, messages (response text), judgments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from stringency import hashing
from stringency.clock import now_iso
from stringency.db.store import Store
from stringency.harness.base import Harness, Invocation, Request, Sampling
from stringency.ids import new_id
from stringency.schemas import validate

RETRY_NOTE = (
    "\n\n---\nYour previous response failed validation:\n{errors}\n"
    "Return corrected JSON that matches the schema exactly.\n"
)


@dataclass
class Replicate:
    """One of the module's replicates (1 to `judgment.replicates`). Under `all_items` it is one
    request; under `per_item` it is one request per item, gathered by `gather` (backlog L172), and
    `structured` is `{"items": [...]}` either way. `invocations` lists every call, retries
    included; `requests` is parallel to it, naming the request each call answered."""

    index: int
    structured: dict[str, Any] | None
    valid: bool
    invocations: list[Invocation]
    requests: list[Request] = field(default_factory=list)

    def items(self) -> list[dict[str, Any]]:
        if not self.valid or self.structured is None:
            return []
        items = self.structured.get("items")
        if isinstance(items, list):
            return [dict(i) for i in items]
        return [dict(self.structured)]

    @property
    def error(self) -> str | None:
        """Why the replicate is invalid: its last call's error, or under `per_item` the error of
        each item whose request failed, named by the item. None when valid or unknown."""
        if not self.invocations:
            return None
        if not self.requests or self.requests[-1].item is None:
            return self.invocations[-1].error
        last: dict[int, tuple[Request, Invocation]] = {}
        for req, inv in zip(self.requests, self.invocations, strict=True):
            last[req.number] = (req, inv)
        errors = [
            f"item {req.item}: {inv.error or 'invalid'}"
            for req, inv in last.values()
            if not inv.schema_valid
        ]
        if errors:
            return "; ".join(errors)
        return self.invocations[-1].error


def validate_response(
    inv: Invocation, schema: dict[str, Any], req: Request | None = None
) -> list[str]:
    """The schema's errors; and for a `per_item` request, an answer whose `item_id` is not the
    item it asked about (the review of PR 34: such an answer was gathered under the wrong item
    and `judg.items_incomplete` blocked with no word of why). The message names both items, so
    the direct family's retry is told and an invalid replicate's error says it."""
    if inv.structured is None:
        return [inv.error or "no structured response"]
    errors = validate(inv.structured, schema)
    if req is not None and req.item is not None:
        got = inv.structured.get("item_id")
        if got is not None and str(got) != req.item:
            errors.append(
                f"this request asks about item {req.item}; the response answers item {got}"
            )
    return errors


def gather(per_request: list[Replicate]) -> list[Replicate]:
    """The module's replicates from one result per request (backlog L172). Under `all_items`
    each request is a replicate and nothing changes. Under `per_item` the requests of one
    replicate are joined: its `structured` is `{"items": [...]}` in the requests' order (the
    shape an `all_items` response has, so consensus and the `judg.*` gates read both alike),
    and it is valid only when every one of its requests is, as one invalid response makes an
    `all_items` replicate invalid. Writes nothing."""
    if not any(r.requests and r.requests[0].item is not None for r in per_request):
        return per_request
    by_rep: dict[int, Replicate] = {}
    for r in per_request:
        rep = by_rep.setdefault(r.index, Replicate(r.index, {"items": []}, True, []))
        rep.invocations.extend(r.invocations)
        rep.requests.extend(r.requests)
        if r.valid and r.structured is not None and rep.structured is not None:
            rep.structured["items"].append(dict(r.structured))
        else:
            rep.valid = False
    for rep in by_rep.values():
        if not rep.valid:
            rep.structured = None
    return [by_rep[k] for k in sorted(by_rep)]


def run_direct(
    harness: Harness, requests: list[Request], schema: dict[str, Any], sampling: Sampling
) -> list[Replicate]:
    out: list[Replicate] = []
    for req in requests:
        inv = harness.invoke(req.prompt, schema, sampling=sampling, request=req)
        errors = validate_response(inv, schema, req)
        inv.schema_valid = not errors
        invs = [inv]
        if errors:
            retry_prompt = req.prompt + RETRY_NOTE.format(errors="\n".join(errors[:10]))
            req2 = Request(**{**req.__dict__, "prompt": retry_prompt})
            inv2 = harness.invoke(retry_prompt, schema, sampling=sampling, request=req2)
            errors = validate_response(inv2, schema, req)
            inv2.schema_valid = not errors
            invs.append(inv2)
        final = invs[-1]
        if errors and final.error is None:
            final.error = "; ".join(errors[:5])  # why the call is invalid, as collection says it
        out.append(
            Replicate(
                req.replicate,
                final.structured if final.schema_valid else None,
                final.schema_valid,
                invs,
                [req] * len(invs),
            )
        )
    return gather(out)


def collect_dispatch(
    harness: Harness, requests: list[Request], schema: dict[str, Any], dispatch_dir: Any
) -> list[Replicate]:
    out: list[Replicate] = []
    for req, inv in zip(requests, harness.collect(requests, dispatch_dir), strict=True):
        errors = validate_response(inv, schema, req)
        inv.schema_valid = not errors and bool(inv.nonce_ok)
        if not inv.schema_valid and inv.error is None:
            inv.error = "; ".join(errors[:5])
        out.append(
            Replicate(
                req.replicate,
                inv.structured if inv.schema_valid else None,
                inv.schema_valid,
                [inv],
                [req],
            )
        )
    return gather(out)


def record_invocations(
    store: Store,
    *,
    run_id: str,
    step_id: str,
    action_id: str,
    replicates: list[Replicate],
    requests: list[Request],
    prompt_hash: str,
    template_path: str,
    template_blob: str | None,
    sampling: Sampling,
    attempt: int,
) -> None:
    """Writes: invocations (one row per call, retries included), messages, judgments. Each
    invocation row carries the module's replicate and its request's own nonce and prompt; under
    `per_item` its `sampling_json` names the item the request asked about (L172)."""
    by_rep = {r.replicate: r for r in requests}
    for rep in replicates:
        reqs = rep.requests or [by_rep[rep.index]] * len(rep.invocations)
        for req, inv in zip(reqs, rep.invocations, strict=True):
            resp_hash = hashing.hash_text(inv.raw_text) if inv.raw_text else None
            if resp_hash:
                store.store_message(resp_hash, inv.raw_text)
            store.insert(
                "invocations",
                {
                    "invocation_id": new_id(),
                    "run_id": run_id,
                    "step_id": step_id,
                    "action_id": action_id,
                    "replicate": rep.index,
                    "template_path": template_path,
                    "template_blob": template_blob,
                    # each replicate's own prompt (L83: its ordering of items and vocabulary)
                    "prompt_hash": hashing.hash_text(req.prompt) if req.prompt else prompt_hash,
                    "model_requested": inv.model_requested,
                    "model_resolved": inv.model_resolved,
                    "harness_kind": inv.harness_kind,
                    "harness_version": inv.harness_version,
                    "via": inv.via,
                    "isolation": inv.isolation,
                    "nonce": req.nonce,
                    "nonce_ok": inv.nonce_ok,
                    "request_path": inv.request_path,
                    "response_path": inv.response_path,
                    "reported_json": inv.reported,
                    "sampling_json": {
                        **sampling.to_json(),
                        **({"perturbation": dict(req.perturbation)} if req.perturbation else {}),
                        **({"item": req.item} if req.item is not None else {}),
                    },
                    "response_hash": resp_hash,
                    "schema_valid": inv.schema_valid,
                    "tokens_in": inv.tokens_in,
                    "tokens_out": inv.tokens_out,
                    "duration_ms": inv.duration_ms,
                    "bit_reproducible": False,
                    "tool_calls_json": inv.tool_calls,
                    "ts": now_iso(),
                },
            )
        for item in rep.items():
            rationale = str(item.get("rationale", ""))
            rref = hashing.hash_text(rationale) if rationale else None
            if rref:
                store.store_message(rref, rationale)
            extra = {
                k: v
                for k, v in item.items()
                if k
                not in {
                    "item_id",
                    "label",
                    "ontology_id",
                    "confidence",
                    "abstain",
                    "supporting_evidence",
                    "contradicting_evidence",
                    "rationale",
                }
            }
            store.insert(
                "judgments",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "item_id": str(item.get("item_id")),
                    "replicate": rep.index,
                    "label": item.get("label"),
                    "ontology_id": item.get("ontology_id"),
                    "confidence": item.get("confidence"),
                    "abstain": bool(item.get("abstain")),
                    "supporting_json": item.get("supporting_evidence", []),
                    "contradicting_json": item.get("contradicting_evidence", []),
                    "rationale_ref": rref,
                    "schema_valid": True,
                    "extra_json": extra,
                    "attempt": attempt,
                },
            )
        if not rep.valid:
            store.insert(
                "judgments",
                {
                    "run_id": run_id,
                    "step_id": step_id,
                    "item_id": "*",
                    "replicate": rep.index,
                    "label": None,
                    "ontology_id": None,
                    "confidence": None,
                    "abstain": None,
                    "supporting_json": [],
                    "contradicting_json": [],
                    "rationale_ref": None,
                    "schema_valid": False,
                    "extra_json": {"error": rep.error},
                    "attempt": attempt,
                },
            )


def asked_item(sampling_json: Any) -> str | None:
    """The item a `per_item` invocation asked about, from its `sampling_json`; None under
    `all_items` (L172)."""
    try:
        doc = json.loads(sampling_json) if isinstance(sampling_json, str) else sampling_json
    except json.JSONDecodeError:
        return None
    item = doc.get("item") if isinstance(doc, dict) else None
    return None if item is None else str(item)


def answering_invocation(
    store: Store, run_id: str, step_id: str, replicate: int, item_id: str | None
) -> Any:
    """The invocation that answered `item_id` for `replicate` on a step, latest first (for who
    answered, backlog L70): under `per_item` the call that asked about that item, not the
    replicate's last call, which asked about another (the review of PR 34); under `all_items`
    the replicate's latest call. For a replicate recorded invalid as a whole (`item_id` `*`)
    the replicate's latest call. None when no call matches. Reads: invocations."""
    rows = store.all(
        "SELECT * FROM invocations WHERE run_id = ? AND step_id = ? AND replicate = ? "
        "ORDER BY rowid DESC",
        (run_id, step_id, replicate),
    )
    if not rows:
        return None
    asked = [(asked_item(r["sampling_json"]), r) for r in rows]
    for item, r in asked:
        if item is not None and item == item_id:
            return r
    for item, r in asked:
        if item is None:
            return r
    return rows[0] if item_id == "*" else None


def wrap_schema(item_schema: dict[str, Any], batching: str) -> dict[str, Any]:
    """`all_items`: one object with an `items` array of judgments; `per_item`: the item schema."""
    if batching == "per_item":
        return item_schema
    inner = {k: v for k, v in item_schema.items() if k not in {"$schema", "$defs", "$id"}}
    wrapped: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["items"],
        "properties": {"items": {"type": "array", "items": inner}},
        "additionalProperties": False,
    }
    if "$defs" in item_schema:
        wrapped["$defs"] = item_schema["$defs"]  # hoisted so `#/$defs/...` refs still resolve
    return wrapped


def judgments_jsonl(replicates: list[Replicate]) -> str:
    lines = []
    for rep in replicates:
        for item in rep.items():
            lines.append(json.dumps({**item, "replicate": rep.index}, sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")
