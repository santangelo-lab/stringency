"""`topo.*`: the action stays inside the bound topology. Invariant."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


@predicate(
    id="topo.undeclared_step",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def undeclared_step(ctx: GateContext) -> Verdict:
    pipeline = ctx.project.pipeline
    if not pipeline.has_step(ctx.action.step_id):
        return Verdict(
            True,
            f"step {ctx.action.step_id} is not in the bound topology",
            {"step": ctx.action.step_id},
        )
    step = pipeline.step(ctx.action.step_id)
    if step.module != ctx.action.module:
        return Verdict(
            True,
            f"step {step.id} is bound to {step.module}, action names {ctx.action.module}",
            {"bound": step.module, "proposed": ctx.action.module},
        )
    m = ctx.project.module_for(ctx.action.module)
    if m is not None and ctx.project.mode not in m.modes:
        return Verdict(True, f"module {m.ref} excludes mode {ctx.project.mode}", {"modes": m.modes})
    return Verdict(False)


@predicate(
    id="topo.predecessor_incomplete",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def predecessor_incomplete(ctx: GateContext) -> Verdict:
    pipeline = ctx.project.pipeline
    if not pipeline.has_step(ctx.action.step_id):
        return Verdict(False)
    incomplete = {
        p: ctx.project.step_status.get(p, "pending")
        for p in pipeline.step(ctx.action.step_id).predecessors()
        if ctx.project.step_status.get(p) != "completed"
    }
    if incomplete:
        return Verdict(
            True, "an input references a step that is not completed", {"predecessors": incomplete}
        )
    return Verdict(False)
