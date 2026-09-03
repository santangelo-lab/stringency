"""Replicated invocations (design 3.5 step 4, 9.3): validate each response against the
schema, retry once in the direct family with the error appended, record every invocation.

Writes: invocations, messages (response text), judgments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
    index: int
    structured: dict[str, Any] | None
    valid: bool
    invocations: list[Invocation]

    def items(self) -> list[dict[str, Any]]:
        if not self.valid or self.structured is None:
            return []
        items = self.structured.get("items")
        if isinstance(items, list):
            return [dict(i) for i in items]
        return [dict(self.structured)]


def validate_response(inv: Invocation, schema: dict[str, Any]) -> list[str]:
    if inv.structured is None:
        return [inv.error or "no structured response"]
    return validate(inv.structured, schema)


def run_direct(
    harness: Harness, requests: list[Request], schema: dict[str, Any], sampling: Sampling
) -> list[Replicate]:
    out: list[Replicate] = []
    for req in requests:
        inv = harness.invoke(req.prompt, schema, sampling=sampling, request=req)
        errors = validate_response(inv, schema)
        inv.schema_valid = not errors
        invs = [inv]
        if errors:
            retry_prompt = req.prompt + RETRY_NOTE.format(errors="\n".join(errors[:10]))
            req2 = Request(**{**req.__dict__, "prompt": retry_prompt})
            inv2 = harness.invoke(retry_prompt, schema, sampling=sampling, request=req2)
            errors = validate_response(inv2, schema)
            inv2.schema_valid = not errors
            invs.append(inv2)
        final = invs[-1]
        out.append(
            Replicate(
                req.replicate,
                final.structured if final.schema_valid else None,
                final.schema_valid,
                invs,
            )
        )
    return out


def collect_dispatch(
    harness: Harness, requests: list[Request], schema: dict[str, Any], dispatch_dir: Any
) -> list[Replicate]:
    out: list[Replicate] = []
    for req, inv in zip(requests, harness.collect(requests, dispatch_dir), strict=True):
        errors = validate_response(inv, schema)
        inv.schema_valid = not errors and bool(inv.nonce_ok)
        if not inv.schema_valid and inv.error is None:
            inv.error = "; ".join(errors[:5])
        out.append(
            Replicate(
                req.replicate, inv.structured if inv.schema_valid else None, inv.schema_valid, [inv]
            )
        )
    return out


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
    """Writes: invocations (one row per call, retries included), messages, judgments."""
    by_rep = {r.replicate: r for r in requests}
    for rep in replicates:
        req = by_rep[rep.index]
        for inv in rep.invocations:
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
                    "prompt_hash": prompt_hash,
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
                    "sampling_json": sampling.to_json(),
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
                    "extra_json": {"error": rep.invocations[-1].error},
                    "attempt": attempt,
                },
            )


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
