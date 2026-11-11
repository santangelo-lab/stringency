"""`param.*`: proposed parameters against the declared schema, defaults, and ranges (design 3.1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


def _decision_points(ctx: GateContext) -> dict[str, Any]:
    """The agent-chosen parameters of the action with what the pipeline declares for each
    (L61): name -> {default, proposed, declared, decl} where `decl` is the `ParamDecl` (None when
    only the module schema declares it)."""
    m = ctx.project.module_for(ctx.action.module)
    step = (
        ctx.project.pipeline.step(ctx.action.step_id)
        if ctx.project.pipeline.has_step(ctx.action.step_id)
        else None
    )
    out: dict[str, Any] = {}
    for name, source in ctx.action.param_source.items():
        if source != "agent":
            continue
        value = ctx.action.parameters.get(name)
        default: object = None
        declared = False
        decl = None
        if step is not None and name in step.params:
            decl = step.params[name]
            default, declared = decl.default, True
        elif m is not None and name in m.declared_params:
            schema = m.declared_params[name]
            default = schema.get("default") if isinstance(schema, dict) else None
            declared = True
        if not declared:
            continue  # `param.undeclared` blocks it
        out[name] = {"default": default, "proposed": value, "decl": decl}
    return out


def _names(ctx: GateContext, only: list[str] | None = None) -> list[Any]:
    """The step's names (`text:` parameters) resolved against the summaries of what it reads
    (`names.resolve_step`); empty for a step outside the pipeline. Reads the state only."""
    from stringency.names import resolve_step

    return resolve_step(
        ctx.project.pipeline,
        ctx.action.step_id,
        ctx.action.parameters,
        ctx.state.objects,
        [i.name for i in ctx.project.inputs.items],
        only,
    )


def _rationale(ctx: GateContext) -> dict[str, Any]:
    r = ctx.action.rationale or {}
    return {
        "text": str(r.get("text") or ""),
        "cited": list(r.get("cited") or []),
        "considered": list(r.get("considered") or []),
        "question": str(r.get("question") or ""),
    }


def reason_numerals(
    design: Any, parameters: Mapping[str, Any], rationale: Mapping[str, Any]
) -> dict[str, list[dict[str, str]]]:
    """A proposal's reason read as an answer is read (`ans.classify_numerals`): each numeral a
    cited cell, a name in backticks, or a failure. The names a mark may resolve to: the keys of
    the rows the reason cites, the design's levels, the parameter values (numerals inside a
    string value count: `cluster = 20`, `6,0,8,17`), the values the proposal considered, and
    the question an on-demand step answers. Shared by `param.reason_unmatched` and by the
    form check `propose` makes before it writes anything. Reads the cited cells' values from
    the rationale; touches no file and no table."""
    from stringency.citations import cited_values
    from stringency.predicates.engine.ans import classify_numerals, numeral_sources

    cited = list(rationale.get("cited") or [])
    src = {
        "key": [str(c["row"]) for c in cited if c.get("row") is not None and "missing" not in c],
        "param": [str(v) for v in parameters.values() if isinstance(v, (int, float, str))],
        "considered": [str(v) for v in rationale.get("considered") or []],
        "question": str(rationale.get("question") or ""),
    }
    return classify_numerals(
        str(rationale.get("text") or ""),
        cited_values(cited),
        numeral_sources(design, {"numeral_sources": src}),
    )


def _evidence_sources(points: dict[str, Any]) -> list[str]:
    """The decision evidence sources of the proposed parameters, in parameter order."""
    out: list[str] = []
    for p in points.values():
        decl = p.get("decl")
        ev = decl.decision.evidence if decl is not None and decl.decision is not None else None
        if ev is not None and ev.source and ev.source not in out:
            out.append(ev.source)
    return out


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
    id="param.locked_changed", version=2, scope=["*"], phase="pre", default=Disposition.BLOCK
)
def locked_changed(ctx: GateContext) -> Verdict:
    """Version 2 (2026-11-10, L163): under `params: locked` a name the person declared in
    `objective.yml` is admitted (it says how the data is labelled, and the confirm hold covered
    it); a name from any other source is a change like any other."""
    if not ctx.project.pipeline.has_step(ctx.action.step_id):
        return Verdict(False)
    step = ctx.project.pipeline.step(ctx.action.step_id)
    locked_profile = ctx.policy.profile(ctx.project.profile).params == "locked"
    changed: dict[str, dict[str, object]] = {}
    for name, decl in step.params.items():
        value = ctx.action.parameters.get(name, decl.default)
        if value == decl.default:
            continue
        if decl.is_name and ctx.action.param_source.get(name) == "declared":
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
    id="param.name_unresolved",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=[],
    summary=(
        "A parameter that names a column, or a value of a column, names nothing in the data "
        "the step reads."
    ),
)
def name_unresolved(ctx: GateContext) -> Verdict:
    """A name (`text: column`, `text: {value_of: ...}`; design 3.1, L163) whose value is not a
    column, or not a value of its column, of any object the step reads, whatever set it: the
    declaration, the agent, or the pipeline's own default. An empty value means none and is not
    checked; a naming convention (`prefix`) is not checked; a name with no summary to check
    against is listed as not checked and does not fire. The step is not run on a name that
    names nothing: propose the name again, with one of the nearest that exist."""
    found = _names(ctx)
    missing = [r for r in found if r.status == "missing"]
    if not missing:
        return Verdict(False)
    return Verdict(
        True,
        "a name names nothing in the data the step reads: " + "; ".join(r.says() for r in missing),
        {
            "unresolved": [r.to_json() for r in missing],
            "not_checked": [r.to_json() for r in found if r.status == "unchecked"],
        },
    )


@predicate(
    id="param.out_of_range",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=[],
    summary=(
        "A proposed value is outside the range or options the pipeline declares for the parameter."
    ),
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


@predicate(
    id="param.agent_proposed",
    version=3,
    scope=["*"],
    phase="pre",
    default=Disposition.FLAG,
    summary=(
        "The operator chose a value for a parameter the method leaves open; a person approves or rejects the choice before the step runs."
    ),
)
def agent_proposed(ctx: GateContext) -> Verdict:
    """The agent proposes, the person approves (owner decision 2026-09-18; roadmap Lane A 5a):
    an admitted parameter whose value the agent chose, and which differs from the committed
    default, opens a flag hold under `standard`; a decision point declaring `decision.hold:
    always` opens it at the default too (L61, the owner's ask of 2026-10-07). The hold's
    evidence is the table the reviewer needs: parameter, default, proposed, and from version 2
    each parameter's declared evidence, the citations the proposal resolved and the candidates
    it considered (L55), and from version 3, for a name (`text:`, L163), what the proposed
    value resolves to in the objects the step reads (`resolves`: the column and its values);
    the reason opens with what kind of proposal this is. `log` under
    `params: free` (policy), moot under `params: locked` where `param.locked_changed` blocks the
    change first."""
    points = _decision_points(ctx)
    proposed: dict[str, dict[str, object]] = {}
    for name, p in points.items():
        decl = p["decl"]
        always = decl is not None and decl.decision is not None and decl.decision.hold == "always"
        if p["proposed"] == p["default"] and not always:
            continue  # equal to the default: no choice made
        entry: dict[str, object] = {"default": p["default"], "proposed": p["proposed"]}
        if decl is not None and decl.decision is not None:
            entry["evidence"] = decl.decision.evidence.describe()
            entry["hold"] = decl.decision.hold
        proposed[name] = entry
    if not proposed:
        return Verdict(False)
    for r in _names(ctx, only=list(proposed)):
        # version 3 (L163): what a proposed name resolves to in the objects the step reads
        proposed[r.parameter]["resolves"] = r.to_json()
    names = ", ".join(sorted(proposed))
    r = _rationale(ctx)
    from stringency.citations import summary_line

    opening = summary_line(r["cited"], r["considered"], _evidence_sources(points))
    return Verdict(
        True,
        f"{opening}; the agent chose {names}; a person approves the choice",
        {
            "proposed": proposed,
            "rationale_ref": ctx.action.rationale_ref,
            "cited": r["cited"],
            "considered": r["considered"],
        },
    )


@predicate(
    id="param.reason_unmatched",
    version=3,
    scope=["*"],
    phase="pre",
    default=Disposition.FLAG,
    summary=(
        "Every bare number in the operator's reason must appear in a cell the proposal cites; "
        "a name (a cited row's key, a design level, a value the proposal sets or considered, a "
        "numeral of the question) is written in backticks. This lists the numbers that are "
        "neither a cited measurement nor a name that resolves."
    ),
)
def reason_unmatched(ctx: GateContext) -> Verdict:
    """The reason of a proposal carries numerals that match no cited cell: values quoted from
    evidence without `--cite`, or numbers invented (L55, backlog L61). A reason with numerals is
    checked as `ans.numeral_unmatched` checks an answer. Only an agent's proposal with a reason
    is read. Version 2 (backlog L93, 2026-10-22): the proposal's own parameter values were not
    claims about evidence and matched without a citation. Version 3 (L157, 2026-11-10): a name
    is marked, a measurement is bare (`ans.classify_numerals`). In backticks a numeral must be
    the key of a cited row, a design level, a parameter value (numerals inside a string value
    count), a considered value or a numeral of the question a call answers; a hyphenated
    identifier (`6-2`), a year and a count before a unit word need no mark; every other bare
    numeral must match a cited cell, the proposal's own values included (in `a floor of 200
    genes` the 200 goes in backticks). The reason says of each failing numeral whether it is a name to put in backticks
    or a measurement to cite, and the evidence lists what was left unchecked (`not_checked`).
    `propose` refuses a reason whose only failures are names written bare before it writes
    anything, so this fires on what a mark would not mend."""
    if ctx.action.proposed_by != "agent":
        return Verdict(False)
    r = _rationale(ctx)
    if not r["text"].strip():
        return Verdict(False)
    got = reason_numerals(ctx.design, ctx.action.parameters, r)
    if not got["failed"]:
        return Verdict(False)
    nums = ", ".join(p["numeral"] for p in got["failed"])
    evidence = {
        "numerals": nums,
        "problems": [{"reason": True, **p} for p in got["failed"]],
        "not_checked": got["exempt"],
    }
    if not r["cited"]:
        return Verdict(True, f"the reason carries numerals ({nums}) and cites nothing", evidence)
    return Verdict(
        True,
        "a numeral in the reason matches no cited cell: "
        + ", ".join(f"{p['numeral']} (nearest: {p['nearest']})" for p in got["failed"]),
        evidence,
    )


@predicate(
    id="param.uncited",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.FLAG,
    summary=(
        "The method names the evidence a decision rests on; the proposal cites nothing from it."
    ),
)
def uncited(ctx: GateContext) -> Verdict:
    """A decision point whose declared evidence is a source, proposed by the agent without one
    citation that resolves into that source (L55). Flag under standard, block under strict
    (the profile's remap). A `text:` or `none` evidence asks for no citation."""
    points = _decision_points(ctx)
    r = _rationale(ctx)
    missing: list[str] = []
    for name, p in points.items():
        decl = p["decl"]
        if decl is None or decl.decision is None or not decl.decision.evidence.source:
            continue
        always = decl.decision.hold == "always"
        if p["proposed"] == p["default"] and not always:
            continue
        src = decl.decision.evidence.source
        if not any(c.get("source") == src and "missing" not in c for c in r["cited"]):
            missing.append(f"{name} ({src})")
    if missing:
        return Verdict(
            True,
            "the proposal cites nothing from the evidence the method names for "
            + ", ".join(missing),
            {"uncited": missing},
        )
    return Verdict(False)


@predicate(
    id="param.schema_invalid",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.BLOCK,
    invariant=True,
)
def schema_invalid(ctx: GateContext) -> Verdict:
    """Open mode (open_mode_plan.md 2.5, 2026-10-16): the action's declared parameters fail the
    module's `params.schema.json` (enum, bounds, type). A tool run on demand has no pipeline
    declaration with a range, so the module schema is the one bound on its values; undeclared
    names are `param.undeclared`'s and are left out here."""
    from stringency.schemas import validate

    m = ctx.project.module_for(ctx.action.module)
    if m is None or not m.params_schema:
        return Verdict(False)
    declared = set(m.declared_params)
    instance = {k: v for k, v in ctx.action.parameters.items() if k in declared}
    problems = validate(instance, m.params_schema)
    if problems:
        return Verdict(
            True,
            "a parameter fails the module's schema: " + "; ".join(problems),
            {"problems": problems, "parameters": instance},
        )
    return Verdict(False)
