"""`param.*`: proposed parameters against the declared schema, defaults, and ranges (design 3.1)."""

from __future__ import annotations

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


def _rationale(ctx: GateContext) -> dict[str, Any]:
    r = ctx.action.rationale or {}
    return {
        "text": str(r.get("text") or ""),
        "cited": list(r.get("cited") or []),
        "considered": list(r.get("considered") or []),
    }


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
    version=2,
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
    it considered (L55); the reason opens with what kind of proposal this is. `log` under
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
    version=2,
    scope=["*"],
    phase="pre",
    default=Disposition.FLAG,
    summary=(
        "Every number in the operator's reason must appear in a cell the proposal cites or be "
        "a value the proposal sets; this lists the numbers that do neither."
    ),
)
def reason_unmatched(ctx: GateContext) -> Verdict:
    """A numeral in the proposal's reason matches no cited cell, or the reason carries numerals
    and cites nothing (L55): the rationale is the object under test, never trusted (design 6.8),
    checked as `ans.numeral_unmatched` checks an answer. Only an agent's proposal with a reason
    is read. Version 2 (backlog L93, 2026-10-22): the proposal's own parameter values are not
    claims about evidence and match without a citation, so "a floor of 200 genes" is not flagged
    for 200 when 200 is the value proposed."""
    from stringency.citations import cited_values
    from stringency.predicates.engine.judg import _numeral_problems

    if ctx.action.proposed_by != "agent":
        return Verdict(False)
    r = _rationale(ctx)
    if not r["text"].strip():
        return Verdict(False)
    allowed = cited_values(r["cited"]) + [
        v for v in ctx.action.parameters.values() if isinstance(v, (int, float, str))
    ]
    problems = _numeral_problems(r["text"], allowed, {"reason": True})
    if not problems:
        return Verdict(False)
    nums = ", ".join(p["numeral"] for p in problems)
    if not r["cited"]:
        return Verdict(
            True, f"the reason carries numerals ({nums}) and cites nothing", {"numerals": nums}
        )
    return Verdict(
        True, f"a numeral in the reason matches no cited cell: {nums}", {"numerals": nums}
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
