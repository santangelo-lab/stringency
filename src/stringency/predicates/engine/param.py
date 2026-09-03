"""`param.*`: proposed parameters against the declared schema, defaults, and ranges (design 3.1)."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


def _declared(ctx: GateContext) -> set[str] | None:
    m = ctx.project.module_for(ctx.action.module)
    if m is None:
        return None
    return set(m.declared_params)


@predicate(
    id="param.undeclared",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def undeclared(ctx: GateContext) -> Verdict:
    declared = _declared(ctx)
    if declared is None:
        return Verdict(False)
    extra = sorted(set(ctx.action.parameters) - declared)
    if extra:
        return Verdict(
            True,
            f"parameter(s) not declared by the module: {extra}",
            {"undeclared": extra, "declared": sorted(declared)},
        )
    return Verdict(False)


@predicate(
    id="param.locked_changed", version=1, scope=["*"], phase="pre", default=Disposition.BLOCK
)
def locked_changed(ctx: GateContext) -> Verdict:
    if not ctx.project.pipeline.has_step(ctx.action.step_id):
        return Verdict(False)
    step = ctx.project.pipeline.step(ctx.action.step_id)
    locked_profile = ctx.policy.profile(ctx.project.profile).params == "locked"
    changed: dict[str, dict[str, object]] = {}
    for name, decl in step.params.items():
        value = ctx.action.parameters.get(name, decl.default)
        if value == decl.default:
            continue
        if decl.fixed or locked_profile:
            changed[name] = {"default": decl.default, "proposed": value, "fixed": decl.fixed}
    if changed:
        why = (
            "parameters are locked under this profile"
            if locked_profile
            else "a fixed parameter differs from its default"
        )
        return Verdict(True, why, {"changed": changed})
    return Verdict(False)


@predicate(
    id="param.out_of_range",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=[],
)
def out_of_range(ctx: GateContext) -> Verdict:
    """Blocks by default; the policy maps it to flag under `params: free` (design 6.5)."""
    if not ctx.project.pipeline.has_step(ctx.action.step_id):
        return Verdict(False)
    step = ctx.project.pipeline.step(ctx.action.step_id)
    bad: dict[str, dict[str, object]] = {}
    for name, decl in step.params.items():
        if decl.fixed:
            continue
        value = ctx.action.parameters.get(name, decl.default)
        if not decl.in_range(value):
            bad[name] = {"proposed": value, "range": decl.range, "options": decl.options}
    if bad:
        return Verdict(
            True,
            "a proposed value is outside the declared range or options",
            {"out_of_range": bad},
            severity="free" if ctx.policy.profile(ctx.project.profile).params == "free" else None,
        )
    return Verdict(False)
