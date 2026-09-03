"""Actions (design 5): a concrete proposal, written to the trace before its pre-gate runs."""

from __future__ import annotations

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
    param_source: dict[str, str]  # per parameter: default | agent
    inputs: dict[str, str]  # input name -> blake3:<hex>
    input_digest: str
    params_hash: str
    proposed_by: str  # pipeline | agent
    rationale_ref: str | None = None
    ticket: str | None = None
    proposed_at: str = field(default_factory=now_iso)

    def with_ticket(self, ticket: str) -> Action:
        return Action(**{**self.__dict__, "ticket": ticket})


def coerce_value(text: str) -> Any:
    """`--set k=v` values arrive as text. Numbers, booleans, null become typed; else string."""
    low = text.strip().lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"null", "none"}:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def build_action(
    *,
    run_id: str,
    step: StepDecl,
    module: Module,
    attempt: int,
    input_digests: dict[str, str],
    proposed: dict[str, Any] | None = None,
    rationale_ref: str | None = None,
) -> Action:
    """Merge committed defaults with agent-proposed values (design 3.1, 5).

    Every declared pipeline parameter takes its default unless the agent proposed a value.
    Undeclared proposals are kept in `parameters` so `param.undeclared` can see them.
    """
    proposed = dict(proposed or {})
    params: dict[str, Any] = {}
    source: dict[str, str] = {}
    for name, decl in step.params.items():
        if name in proposed:
            params[name] = proposed.pop(name)
            source[name] = "agent"
        else:
            params[name] = decl.default
            source[name] = "default"
    # module schema defaults for params the pipeline did not mention
    for name, schema in module.declared_params.items():
        if name not in params:
            if name in proposed:
                params[name] = proposed.pop(name)
                source[name] = "agent"
            elif isinstance(schema, dict) and "default" in schema:
                params[name] = schema["default"]
                source[name] = "default"
    for name, value in proposed.items():  # undeclared anywhere: recorded, then blocked by gate
        params[name] = value
        source[name] = "agent"
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
        proposed_by="agent" if any(v == "agent" for v in source.values()) else "pipeline",
        rationale_ref=rationale_ref,
    )


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
