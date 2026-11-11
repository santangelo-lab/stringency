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
    id="init.column_missing", version=2, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def column_missing(ctx: GateContext) -> Verdict:
    """Every design column exists in every raw object input, per the extractor pass. An input
    bound through `derived_from` is a delivered artifact of an earlier run, not a raw input:
    its columns are whatever the upstream module produced, so it is skipped here. So is an input
    declared with `role: reference`: it describes other studies' observations, not this design's.

    Version 2 (2026-11-10): the reason names each input, the columns it lacks and the columns
    it has. Version 1 said only that some column was absent, and the refusal a drafter read at
    `declare --check` gave nothing to mend the design by (a unit written as a sentence where
    its column's name belongs, found when the first h5ad was checked)."""
    want = ctx.design.columns()
    derived = {
        i.name
        for i in ctx.project.inputs.items
        if i.derived_from is not None or getattr(i, "role", "observation") == "reference"
    }
    missing: dict[str, list[str]] = {}
    present: dict[str, list[str]] = {}
    for name, obj in ctx.state.objects.items():
        if name in derived:
            continue
        cols = obj.fields.get("columns")
        if cols is None:
            continue
        have = set(cols) if isinstance(cols, dict | list) else set()
        gone = [c for c in want if c not in have]
        if gone:
            missing[name] = gone
            present[name] = sorted(str(c) for c in have)
    if missing:
        said = "; ".join(
            f"{name} lacks {', '.join(repr(c) for c in gone)} (it has "
            + (", ".join(present[name][:20]) or "no columns")
            + (f", and {len(present[name]) - 20} more" if len(present[name]) > 20 else "")
            + ")"
            for name, gone in missing.items()
        )
        return Verdict(
            True,
            "design column(s) absent from the raw input: "
            + said
            + ". Every unit other than the observation, every factor's `column` and every "
            "batch variable names a column of the input",
            {"missing": missing, "present": present},
        )
    return Verdict(False)


@predicate(
    id="init.name_unresolved", version=1, scope=SCOPE, phase="init", default=Disposition.BLOCK
)
def name_unresolved(ctx: GateContext) -> Verdict:
    """A name declared in `objective.yml` `params` (a `text:` parameter, design 3.1, L163) that
    is not a column, or not a value of its column, of any input the step descends from: the
    confirm hold would cover a setup whose step `param.name_unresolved` will block. The same
    resolution as that predicate, against the inputs' summaries from the extractor pass. An
    empty value, a naming convention, and a name with no summary to check against do not fire."""
    from stringency.names import resolve_step

    pipeline = ctx.project.pipeline
    names = [i.name for i in ctx.project.inputs.items]
    missing: dict[str, list[dict[str, object]]] = {}
    says: list[str] = []
    for sid, values in (ctx.objective.params or {}).items():
        if not pipeline.has_step(sid) or not isinstance(values, dict):
            continue
        for r in resolve_step(pipeline, sid, values, ctx.state.objects, names, only=list(values)):
            if r.status == "missing":
                missing.setdefault(sid, []).append(r.to_json())
                says.append(f"step {sid}: {r.says()}")
    if missing:
        return Verdict(
            True,
            "a declared name names nothing in the input: " + "; ".join(says),
            {"unresolved": missing},
        )
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
    """A deliverable is an output name some step produces, or `<step>.<output>` naming a step
    whose module produces that output (L135; a qualified name fired here before, so no
    recorded verdict changes)."""
    produced: set[str] = set()
    for step in ctx.project.pipeline.steps:
        m = ctx.project.modules.get(step.module)
        if m is not None:
            produced |= set(m.outputs)
            produced |= {f"{step.id}.{o}" for o in m.outputs}
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
