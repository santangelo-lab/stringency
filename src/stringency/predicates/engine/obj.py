"""`obj.*`: the objective stays reachable (design 6.5, forward feasibility)."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate

TERMINAL = {"blocked", "rejected", "failed"}


@predicate(
    id="obj.feasibility", version=1, scope=["*"], phase=["pre", "post"], default=Disposition.BLOCK
)
def feasibility(ctx: GateContext) -> Verdict:
    """counts_per_group for any level of any contrast below min_n_per_group."""
    need = ctx.objective.min_n_per_group
    unit = ctx.objective.replication_unit or ctx.design.replication_unit
    if not need or unit is None or not ctx.objective.contrasts:
        return Verdict(False)
    short: list[dict[str, object]] = []
    for obj_name, obj in ctx.state.objects.items():
        cpg = obj.counts_per_group
        for factor, la, lb in (tuple(c) for c in ctx.objective.contrasts):
            levels = cpg.get(factor)
            if levels is None:
                continue
            for lvl in (la, lb):
                counts = levels.get(lvl, {})
                n = counts.get(unit)
                if n is None:
                    continue
                if n < need:
                    short.append(
                        {
                            "object": obj_name,
                            "factor": factor,
                            "level": lvl,
                            "unit": unit,
                            "n": n,
                            "min": need,
                        }
                    )
    if short:
        return Verdict(
            True,
            "a contrast level has fewer replication units than min_n_per_group",
            {"short": short},
        )
    return Verdict(False)


@predicate(
    id="obj.deliverable_unreachable", version=1, scope=["*"], phase="pre", default=Disposition.FLAG
)
def deliverable_unreachable(ctx: GateContext) -> Verdict:
    pipeline = ctx.project.pipeline
    unreachable: list[str] = []
    for d in ctx.objective.deliverables:
        producers: list[str] = []
        for s in pipeline.steps:
            mm = ctx.project.module_for(s.module)
            if mm is not None and d in mm.outputs:
                producers.append(s.id)
        if producers and all(ctx.project.step_status.get(p) in TERMINAL for p in producers):
            unreachable.append(d)
    if unreachable:
        return Verdict(
            True,
            f"no remaining step produces deliverable(s) {unreachable}",
            {"unreachable": unreachable},
        )
    return Verdict(False)
