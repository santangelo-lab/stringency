"""`repro.*`: reproducibility facts. Invariant except `intermediate_dropped` and `env_unverified`."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


@predicate(
    id="repro.dirty_tree",
    version=1,
    scope=["*"],
    phase="run_open",
    default=Disposition.BLOCK,
    invariant=True,
)
def dirty_tree(ctx: GateContext) -> Verdict:
    if ctx.project.git_dirty and not ctx.project.allow_dirty_reason:
        return Verdict(True, "the method repo has uncommitted changes", {"allow_dirty": False})
    return Verdict(False)


@predicate(
    id="repro.env_unpinned",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def env_unpinned(ctx: GateContext) -> Verdict:
    m = ctx.project.module_for(ctx.action.module)
    if m is None:
        return Verdict(False)
    digest = ctx.project.env_digests.get(m.env, None)
    if digest is None:
        return Verdict(True, f"no environment digest for env {m.env}", {"env": m.env})
    return Verdict(False)


@predicate(
    id="repro.seed_unset",
    version=1,
    scope=["stochastic:true"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def seed_unset(ctx: GateContext) -> Verdict:
    m = ctx.project.module_for(ctx.action.module)
    if m is None or not m.stochastic:
        return Verdict(False)
    seed = ctx.action.parameters.get(m.seed_param or "seed")
    if seed is None:
        return Verdict(
            True, f"seed parameter {m.seed_param} is unset", {"seed_param": m.seed_param}
        )
    return Verdict(False)


@predicate(
    id="repro.input_digest_mismatch",
    version=1,
    scope=["*"],
    phase=["run_open", "pre"],
    default=Disposition.BLOCK,
    invariant=True,
)
def input_digest_mismatch(ctx: GateContext) -> Verdict:
    recorded = {i.name: i.blake3 for i in ctx.project.inputs.items}
    now = ctx.project.input_digests_now
    if ctx.phase == "pre" and ctx.project.pipeline.has_step(ctx.action.step_id):
        wanted = {
            r.name
            for r in ctx.project.pipeline.step(ctx.action.step_id).refs().values()
            if r.kind == "inputs"
        }
    else:
        wanted = set(recorded)
    bad = {
        n: {"recorded": recorded[n], "now": now.get(n)}
        for n in wanted
        if n in now and now[n] != recorded.get(n)
    }
    if bad:
        return Verdict(
            True, "an input's current hash differs from the recorded hash", {"inputs": bad}
        )
    return Verdict(False)


@predicate(
    id="repro.intermediate_dropped", version=1, scope=["*"], phase="post", default=Disposition.FLAG
)
def intermediate_dropped(ctx: GateContext) -> Verdict:
    """The step consumed an object type, produced none, and a later step needs one."""
    m = ctx.project.module_for(ctx.action.module)
    if m is None or not ctx.project.pipeline.has_step(ctx.action.step_id):
        return Verdict(False)
    obj_types = set(ctx.project.object_types)
    consumed = {i.type for i in m.inputs.values() if i.type in obj_types}
    produced = {o.type for o in m.outputs.values() if o.type in obj_types}
    dropped = consumed - produced
    if not dropped:
        return Verdict(False)
    later_needs: list[str] = []
    for sid in ctx.project.pipeline.downstream(ctx.action.step_id):
        later = ctx.project.module_for(ctx.project.pipeline.step(sid).module)
        if later and any(i.type in dropped for i in later.inputs.values()):
            later_needs.append(sid)
    if later_needs:
        return Verdict(
            True,
            f"object type(s) {sorted(dropped)} consumed and not retained; needed by {later_needs}",
            {"dropped": sorted(dropped), "needed_by": later_needs},
        )
    return Verdict(False)


@predicate(
    id="repro.env_unverified",
    version=1,
    scope=["runner:operator"],
    phase="post",
    default=Disposition.FLAG,
)
def env_unverified(ctx: GateContext) -> Verdict:
    if ctx.output is not None and ctx.output.env_status == "as_reported":
        return Verdict(
            True,
            "the reported environment could not be matched to the environment manifest",
            {"env_status": "as_reported", "reported": ctx.output.observed.get("container")},
        )
    return Verdict(False)
