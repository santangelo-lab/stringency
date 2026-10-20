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
        # a skipped conditional step is done (L13); no run before 0.2.7 has one, so every
        # earlier verdict is unchanged and the version stays 1
        if ctx.project.step_status.get(p) not in ("completed", "skipped")
    }
    if incomplete:
        return Verdict(
            True, "an input references a step that is not completed", {"predecessors": incomplete}
        )
    return Verdict(False)


@predicate(
    id="topo.input_type_mismatch",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def input_type_mismatch(ctx: GateContext) -> Verdict:
    """Open mode (open_mode_plan.md 2.5, 2026-10-16): a bound input whose recorded kind differs
    from the type the module declares for it. Reads `project.artifact_kinds` (digest to kind as
    the engine recorded it); an input whose digest is not there (an `arity: many` list, a run
    opened before the capture) is not judged."""
    m = ctx.project.module_for(ctx.action.module)
    if m is None:
        return Verdict(False)
    bad: dict[str, dict[str, str]] = {}
    for name, digest in ctx.action.inputs.items():
        spec = m.inputs.get(name)
        if spec is None:
            continue
        bare = digest.removeprefix("blake3:")
        kind = ctx.project.artifact_kinds.get(bare)
        if kind is not None and kind != spec.type:
            bad[name] = {"declared": spec.type, "bound": kind}
    if bad:
        names = ", ".join(
            f"{k} ({v['bound']} bound, {v['declared']} declared)" for k, v in bad.items()
        )
        return Verdict(
            True, f"an input is bound to the wrong kind of artifact: {names}", {"inputs": bad}
        )
    return Verdict(False)
