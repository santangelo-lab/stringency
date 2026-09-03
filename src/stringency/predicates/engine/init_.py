"""`init.*` compatibility predicates (design 2.7, 6.5). Phase `init`, scope `project`.

They read the declarations and the bound pipeline out of the context. `init.column_missing`
reads the extractor pass stored in `ctx.state.objects`.
"""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate

SCOPE = ["project"]


@predicate(
    id="init.contrast_undeclared", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def contrast_undeclared(ctx: GateContext) -> Verdict:
    bad = [c for c in ctx.objective.contrasts if c[0] not in ctx.design.factors]
    if bad:
        return Verdict(
            True,
            f"contrast names factor(s) not in the design: {sorted({c[0] for c in bad})}",
            {"contrasts": bad, "declared_factors": sorted(ctx.design.factors)},
        )
    return Verdict(False)


@predicate(
    id="init.level_undeclared", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def level_undeclared(ctx: GateContext) -> Verdict:
    bad: list[dict[str, object]] = []
    for c in ctx.objective.contrasts:
        f = ctx.design.factors.get(c[0])
        if f is None:
            continue
        for lvl in c[1:]:
            if lvl not in f.levels:
                bad.append({"factor": c[0], "level": lvl, "declared": f.levels})
    if bad:
        return Verdict(True, "contrast names a level the design does not list", {"missing": bad})
    return Verdict(False)


@predicate(
    id="init.replication_unit_undeclared",
    version=1,
    scope=SCOPE,
    phase="init",
    default=Disposition.BLOCK,
)
def replication_unit_undeclared(ctx: GateContext) -> Verdict:
    ru = ctx.objective.replication_unit
    if ru is None:
        return Verdict(False)
    declared = set(ctx.design.units) | set(ctx.design.units.values())
    if ru not in declared:
        return Verdict(
            True,
            f"objective replication unit {ru} is not a declared design unit",
            {"replication_unit": ru, "declared_units": ctx.design.units},
        )
    return Verdict(False)


@predicate(
    id="init.column_missing", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def column_missing(ctx: GateContext) -> Verdict:
    """Every design column exists in every raw object input, per the extractor pass."""
    want = ctx.design.columns()
    missing: dict[str, list[str]] = {}
    for name, obj in ctx.state.objects.items():
        cols = obj.fields.get("columns")
        if cols is None:
            continue
        have = set(cols) if isinstance(cols, dict | list) else set()
        gone = [c for c in want if c not in have]
        if gone:
            missing[name] = gone
    if missing:
        return Verdict(True, "design column(s) absent from the raw input", {"missing": missing})
    return Verdict(False)


@predicate(
    id="init.question_unsupported", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def question_unsupported(ctx: GateContext) -> Verdict:
    q = ctx.objective.question
    answers = ctx.project.pipeline.answers
    if q not in answers:
        return Verdict(
            True,
            f"pipeline {ctx.project.pipeline.name} does not declare that it answers {q}",
            {"question": q, "answers": answers},
        )
    return Verdict(False)


@predicate(
    id="init.deliverable_unproduced",
    version=1,
    scope=SCOPE,
    phase="init",
    default=Disposition.BLOCK,
)
def deliverable_unproduced(ctx: GateContext) -> Verdict:
    produced: set[str] = set()
    for step in ctx.project.pipeline.steps:
        m = ctx.project.modules.get(step.module)
        if m is not None:
            produced |= set(m.outputs)
    missing = [d for d in ctx.objective.deliverables if d not in produced]
    if missing:
        return Verdict(
            True,
            f"deliverable(s) produced by no step: {missing}",
            {"missing": missing, "produced": sorted(produced)},
        )
    return Verdict(False)


@predicate(
    id="init.reference_mismatch", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def reference_mismatch(ctx: GateContext) -> Verdict:
    """An input declaring a reference `build` must match the pipeline's `reference_build`."""
    want = ctx.project.pipeline.reference_build
    if want is None:
        return Verdict(False)
    bad = [
        {"input": i.name, "build": i.build}
        for i in ctx.project.inputs.items
        if i.build is not None and i.build != want
    ]
    if bad:
        return Verdict(True, f"input reference build differs from {want}", {"mismatch": bad})
    return Verdict(False)
