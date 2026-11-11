"""Declared parameter values, checked when the declarations are (design 2.5; PLAN L168).

`objective.yml` `params` gives a step's parameter a value the step takes as given. The step
gate judges that value when the step runs (`param.locked_changed`, `param.out_of_range`,
`param.schema_invalid`). Whether those predicates will block it is known from the pipeline, the
module's schema, the policy and the profile alone, so `init` and `declare --check` say so
before a person confirms the setup and before any earlier step has run. The step-time
predicates stay: this moves the news, it does not replace the gate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.modules import ModuleIndex
from stringency.pipelines import Pipeline
from stringency.policy import Policy
from stringency.predicates.context import Disposition
from stringency.predicates.registry import registry
from stringency.schemas import validate


def _blocks(policy: Policy, profile: str, predicate_id: str) -> bool:
    spec = registry.get(predicate_id)
    return spec is not None and policy.effective(spec, profile) == Disposition.BLOCK


def values_the_gate_would_block(
    pipeline: Pipeline,
    modules: ModuleIndex,
    params: Mapping[str, Mapping[str, Any]],
    policy: Policy,
    profile: str,
) -> list[str]:
    """One line per declared value its step's pre-gate would block under this policy and
    profile, each with the step, the parameter, the step-time predicate's own reason and the
    predicate's id. Empty when every declared value would be admitted. A predicate the policy
    makes a flag or a log under this profile (out of range under `params: free`) is not a
    block and is left to the step. Reads nothing but its arguments."""
    locked_profile = policy.profile(profile).params == "locked"
    locked_blocks = _blocks(policy, profile, "param.locked_changed")
    range_blocks = _blocks(policy, profile, "param.out_of_range")
    schema_blocks = _blocks(policy, profile, "param.schema_invalid")
    out: list[str] = []
    for sid, values in params.items():
        step = pipeline.step(sid)
        module = modules.require(step.module)
        for name, value in values.items():
            where = f"step {sid}, parameter {name}"
            decl = step.params.get(name)
            changed = decl is not None and value != decl.default
            # a declared name is admitted under every profile (param.locked_changed@2, L163)
            if decl is not None and decl.is_name:
                changed = False
            if decl is not None and changed and (decl.fixed or locked_profile) and locked_blocks:
                why = (
                    "parameters are locked under this profile"
                    if locked_profile
                    else "a fixed parameter differs from its default"
                )
                out.append(
                    f"{where}: {why} (default {decl.default!r}, declared {value!r}; "
                    "param.locked_changed)"
                )
                continue
            if decl is not None and not decl.fixed and not decl.in_range(value) and range_blocks:
                bound = (
                    f"range {decl.range}" if decl.range is not None else f"options {decl.options}"
                )
                out.append(
                    f"{where}: a proposed value is outside the declared range or options "
                    f"(declared {value!r}, {bound}; param.out_of_range)"
                )
                continue
            schema = module.declared_params.get(name)
            if isinstance(schema, dict) and schema_blocks:
                # the instance and schema shaped as the step-time predicate's, so the text is its
                problems = validate({name: value}, {"type": "object", "properties": {name: schema}})
                if problems:
                    out.append(
                        f"{where}: a parameter fails the module's schema: "
                        + "; ".join(problems)
                        + f" (declared {value!r}; param.schema_invalid)"
                    )
    return out
