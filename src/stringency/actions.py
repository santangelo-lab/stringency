"""Actions (design 5): a concrete proposal, written to the trace before its pre-gate runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from stringency import hashing
from stringency.clock import now_iso
from stringency.exit_codes import BlockedError
from stringency.ids import new_id

if TYPE_CHECKING:
    from stringency.db.store import Store
    from stringency.modules import Module
    from stringency.pipelines import StepDecl


@dataclass(frozen=True)
class Action:
    action_id: str
    run_id: str
    step_id: str
    attempt: int
    operation: str
    module: str
    parameters: dict[str, Any]
    param_source: dict[
        str, str
    ]  # per parameter: default | agent | person | fork | inherited | declared
    inputs: dict[str, str]  # input name -> blake3:<hex>
    input_digest: str
    params_hash: str
    proposed_by: str  # pipeline | agent | person | fork | inherited | declared
    rationale_ref: str | None = None
    ticket: str | None = None
    proposed_at: str = field(default_factory=now_iso)
    # in memory only, never a column: the rationale record behind `rationale_ref` as the
    # pre-gate sees it (`{text, cited, considered}`, backlog L55), so predicates read the
    # resolved citations without I/O. `action_from_row` leaves it None.
    rationale: Mapping[str, Any] | None = None

    def with_ticket(self, ticket: str) -> Action:
        return Action(**{**self.__dict__, "ticket": ticket})


def coerce_value(text: str, schema: Mapping[str, Any] | None = None) -> Any:
    """`--set k=v` values arrive as text. Numbers, booleans, null become typed; else string.
    With the parameter's schema (backlog L47, L39): an array takes `[a,b]` or `a,b`, each
    element coerced by its items schema; a string parameter keeps the text as given, so an enum
    member spelled `none` or `null` is that member and not the null value."""
    raw = text.strip()
    kind = schema.get("type") if schema else None
    if kind == "array":
        inner = raw[1:-1] if raw.startswith("[") and raw.endswith("]") else raw
        items = schema.get("items") if schema else None
        item_schema = items if isinstance(items, dict) else None
        return [coerce_value(p, item_schema) for p in inner.split(",") if p.strip()]
    if kind == "string":
        return raw
    if schema and isinstance(schema.get("enum"), list) and raw in schema["enum"]:
        return raw  # an enum member as spelled, whatever the schema's type (`none`, `null`)
    if schema is None and raw.startswith("[") and raw.endswith("]"):
        return [coerce_value(p) for p in raw[1:-1].split(",") if p.strip()]
    low = raw.lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"null", "none"}:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def build_action(
    *,
    run_id: str,
    step: StepDecl,
    module: Module,
    attempt: int,
    input_digests: dict[str, str],
    proposed: dict[str, Any] | None = None,
    rationale_ref: str | None = None,
    source_label: str = "agent",
    inherited: dict[str, tuple[Any, str]] | None = None,
) -> Action:
    """Merge committed defaults with proposed and inherited values (design 2.6, 3.1, 5).

    Every declared pipeline parameter takes its default unless a value was proposed or
    inherited. A proposed value is recorded with its source: `agent` (the operator's proposal,
    which `param.agent_proposed` puts before a person) or `fork` (a person's `fork --set` delta,
    made with a reason on the run row). `inherited` is what a forked run's ancestor admitted for
    the step, as name -> (value, label) from `fork.inherited_params`: a value the ancestor took at
    its default keeps the label `default`, any other is `inherited`, and a proposed value
    overrides it (backlog L27: a fork of the pilot ran at the pipeline defaults). Undeclared
    proposals are kept in `parameters` so `param.undeclared` can see them.
    """
    proposed = dict(proposed or {})
    carried = dict(inherited or {})
    params: dict[str, Any] = {}
    source: dict[str, str] = {}

    def take(name: str) -> bool:
        if name in proposed:
            params[name] = proposed.pop(name)
            source[name] = source_label
            return True
        if name in carried:
            params[name], source[name] = carried.pop(name)
            return True
        return False

    for name, decl in step.params.items():
        if not take(name):
            params[name] = decl.default
            source[name] = "default"
    # module schema defaults for params the pipeline did not mention
    for name, schema in module.declared_params.items():
        if (
            name not in params
            and not take(name)
            and isinstance(schema, dict)
            and "default" in schema
        ):
            params[name] = schema["default"]
            source[name] = "default"
    for name, value in proposed.items():  # undeclared anywhere: recorded, then blocked by gate
        params[name] = value
        source[name] = source_label
    labels = {v for v in source.values() if v != "default"}
    # `person` (open mode, design 5 amended 2026-10-16): a value the person dictated in their own
    # words, recorded with their words as the reason; it opens no `param.agent_proposed` hold
    if source_label in labels:
        proposed_by = source_label
    elif "agent" in labels:
        proposed_by = "agent"
    elif "person" in labels:
        proposed_by = "person"
    elif "inherited" in labels:
        proposed_by = "inherited"
    elif "declared" in labels:
        proposed_by = "declared"
    else:
        proposed_by = "pipeline"
    prefixed = {
        k: hashing.prefixed(hashing.strip_prefix(v)) for k, v in sorted(input_digests.items())
    }
    return Action(
        action_id=new_id(),
        run_id=run_id,
        step_id=step.id,
        attempt=attempt,
        operation=module.manifest.operation,
        module=module.ref,
        parameters=params,
        param_source=source,
        inputs=prefixed,
        input_digest=hashing.prefixed(hashing.hash_json(prefixed)),
        params_hash=hashing.prefixed(hashing.hash_json(params)),
        proposed_by=proposed_by,
        rationale_ref=rationale_ref,
    )


def rationale_record(text: str | None) -> dict[str, Any] | None:
    """The message behind an action's `rationale_ref`, read back (backlog L55): a JSON object
    `{text, cited, considered}` written by `propose --cite`, or a plain sentence from before,
    returned as `{text, cited: [], considered: []}`. None for no rationale."""
    if text is None:
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and "text" in doc:
        return {
            "text": str(doc.get("text") or ""),
            "cited": list(doc.get("cited") or []),
            "considered": list(doc.get("considered") or []),
        }
    return {"text": text, "cited": [], "considered": []}


def write_action(store: Store, action: Action) -> None:
    """Writes: actions. Called before the pre-gate so rejected proposals are kept."""
    store.insert(
        "actions",
        {
            "action_id": action.action_id,
            "run_id": action.run_id,
            "step_id": action.step_id,
            "attempt": action.attempt,
            "operation": action.operation,
            "module": action.module,
            "params_json": action.parameters,
            "params_hash": action.params_hash,
            "inputs_json": action.inputs,
            "input_digest": action.input_digest,
            "proposed_by": action.proposed_by,
            "rationale_ref": action.rationale_ref,
            "proposed_at": action.proposed_at,
            "param_source_json": action.param_source,
            "ticket": action.ticket,
        },
    )


def require_admissible(blocked: list[str]) -> None:
    if blocked:
        raise BlockedError("blocked: " + "; ".join(blocked))
