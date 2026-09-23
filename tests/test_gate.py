"""M4: predicates (must-fire and must-pass for every one), policy resolution, gate writes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from stringency.actions import write_action
from stringency.gate import evaluate, in_scope_specs
from stringency.policy import Policy
from stringency.predicates import Disposition, GateContext, registry
from stringency.predicates.context import OutputBundle, OutputInfo
from stringency.project import Project
from stringency.state import StepRecord
from tests.helpers import (
    SUMMARY_TABLE,
    frame_object,
    judgment,
    judgment_bundle,
    make_action,
    make_ctx,
    replicate,
    unanimous_replicates,
)

CtxFn = Callable[[Project], GateContext]


def _deterministic_bundle(**kw: Any) -> OutputBundle:
    return OutputBundle(outputs={"object": OutputInfo("object", "frame", "x", "blake3:00")}, **kw)


# (predicate id, must-fire ctx builder, must-pass ctx builder)
CASES: list[tuple[str, CtxFn, CtxFn]] = [
    (
        "topo.undeclared_step",
        lambda p: make_ctx(
            p,
            "01_filter",
            action=make_action(p, "01_filter")[0].__class__(
                **{**make_action(p, "01_filter")[0].__dict__, "step_id": "99_bogus"}
            ),
        ),
        lambda p: make_ctx(p, "01_filter"),
    ),
    (
        "topo.predecessor_incomplete",
        lambda p: make_ctx(p, "02_summarize", step_status={"01_filter": "held"}),
        lambda p: make_ctx(p, "02_summarize"),
    ),
    (
        "repro.dirty_tree",
        lambda p: make_ctx(p, "01_filter", phase="run_open", git_dirty=True),
        lambda p: make_ctx(
            p, "01_filter", phase="run_open", git_dirty=True, allow_dirty_reason="testing"
        ),
    ),
    (
        "repro.env_unpinned",
        lambda p: make_ctx(p, "01_filter", env_digests={"toy-py": None}),
        lambda p: make_ctx(p, "01_filter"),
    ),
    (
        "repro.input_digest_mismatch",
        lambda p: make_ctx(p, "01_filter", input_digests_now={"groups": "ff" * 32}),
        lambda p: make_ctx(p, "01_filter"),
    ),
    (
        "repro.intermediate_dropped",
        # summarize consumes a frame and emits only a table, but 04_compare needs a frame:
        # rewire so 04_compare reads from 02 to make the drop matter is not possible without a
        # pipeline edit, so use a step_status view: the predicate reads types only.
        lambda p: _dropped_ctx(p),
        lambda p: make_ctx(p, "01_filter", phase="post", output=_deterministic_bundle()),
    ),
    (
        "repro.env_unverified",
        lambda p: make_ctx(
            p, "01_filter", phase="post", output=_deterministic_bundle(env_status="as_reported")
        ),
        lambda p: make_ctx(
            p, "01_filter", phase="post", output=_deterministic_bundle(env_status="verified")
        ),
    ),
    (
        "param.undeclared",
        lambda p: make_ctx(p, "01_filter", proposed={"max_value": 3}),
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 20}),
    ),
    (
        "param.locked_changed",
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 20}, profile="strict"),
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 20}, profile="standard"),
    ),
    (
        "param.out_of_range",
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 41}),
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 40}),
    ),
    (
        "param.agent_proposed",
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 20}),
        lambda p: make_ctx(p, "01_filter", proposed={"min_value": 10}),  # equals the default
    ),
    (
        "out.schema_conformance",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(unanimous_replicates(), schema_errors={"judgments": "bad"}),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "obj.feasibility",
        lambda p: make_ctx(p, "02_summarize", objects={"object": frame_object("frame_b_empty")}),
        lambda p: make_ctx(p, "02_summarize"),
    ),
    (
        "obj.deliverable_unreachable",
        lambda p: make_ctx(
            p, "02_summarize", step_status={"01_filter": "completed", "04_compare": "blocked"}
        ),
        lambda p: make_ctx(p, "02_summarize"),
    ),
    (
        "exec.script_drift",
        lambda p: make_ctx(
            p,
            "01_filter",
            phase="post",
            output=_deterministic_bundle(
                observed={"script": {"path": "modules/filter-rows/pre.py", "blob": "b" * 64}}
            ),
            script_blobs={"filter-rows@0.1.1": "a" * 64},
        ),
        lambda p: make_ctx(
            p,
            "01_filter",
            phase="post",
            output=_deterministic_bundle(
                observed={"script": {"path": "modules/filter-rows/pre.py", "blob": "a" * 64}}
            ),
            script_blobs={"filter-rows@0.1.1": "a" * 64},
        ),
    ),
    (
        "exec.plan_drift",
        lambda p: make_ctx(
            p,
            "01_filter",
            phase="post",
            output=_deterministic_bundle(observed={"params": {"min_value": 40}}),
        ),
        lambda p: make_ctx(
            p,
            "01_filter",
            phase="post",
            output=_deterministic_bundle(observed={"params": {"min_value": 10}}),
        ),
    ),
    (
        "prov.orphan_artifact",
        lambda p: make_ctx(
            p,
            "05_report",
            phase="deliver",
            output=_deterministic_bundle(observed={"missing_sidecars": ["x.tsv"]}),
        ),
        lambda p: make_ctx(p, "05_report", phase="deliver", output=_deterministic_bundle()),
    ),
    (
        "judg.evidence_exists",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(
                [
                    replicate(
                        [
                            judgment(
                                "A",
                                "abundant",
                                supporting=[
                                    {
                                        "table": "summary",
                                        "row": "Z",
                                        "column": "mean_value",
                                        "value": 1,
                                    }
                                ],
                            ),
                            judgment("B", "sparse"),
                            judgment("C", "variable"),
                        ]
                    )
                ]
            ),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "judg.vocabulary_resolves",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(
                unanimous_replicates({"A": "plentiful", "B": "sparse", "C": "variable"})
            ),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "judg.confidence_consistent",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(
                [
                    replicate(
                        [
                            judgment(
                                "A",
                                "abundant",
                                "high",
                                supporting=[
                                    {
                                        "table": "summary",
                                        "row": "A",
                                        "column": "mean_value",
                                        "value": 74.31,
                                    }
                                ],
                            ),
                            judgment("B", "sparse"),
                            judgment("C", "variable"),
                        ]
                    )
                ]
            ),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "judg.numeric_claims_match",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(
                [
                    replicate(
                        [
                            judgment("A", "abundant", rationale="mean of 74.3 but I recall 80.1"),
                            judgment("B", "sparse"),
                            judgment("C", "variable"),
                        ]
                    )
                ]
            ),
        ),
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(
                [
                    replicate(
                        [
                            judgment("A", "abundant", rationale="mean 74.3 over 3 units"),
                            judgment("B", "sparse"),
                            judgment("C", "variable"),
                        ]
                    )
                ]
            ),
        ),
    ),
    (
        "judg.replicates_below_min",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle(unanimous_replicates(), valid=[True, True, False]),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "judg.items_incomplete",
        lambda p: make_ctx(
            p,
            "03_label",
            phase="post",
            output=judgment_bundle([replicate([judgment("A", "abundant")])]),
        ),
        lambda p: make_ctx(
            p, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
        ),
    ),
    (
        "toy.replication_unit",
        lambda p: make_ctx(p, "04_compare", proposed={"replicate_unit": "row"}),
        lambda p: make_ctx(p, "04_compare"),
    ),
    (
        "toy.no_correction",
        lambda p: make_ctx(p, "04_compare", proposed={"correction": "none"}),
        lambda p: make_ctx(p, "04_compare"),
    ),
    (
        "toy.filter_after_summary",
        lambda p: make_ctx(
            p, "01_filter", history=(StepRecord("02_summarize", "summarize_groups", {}, {}),)
        ),
        lambda p: make_ctx(p, "01_filter"),
    ),
]


def _dropped_ctx(p: Project) -> GateContext:
    """02_summarize consumes a frame and keeps none; pretend 04_compare is downstream of it."""
    from stringency.pipelines import Pipeline

    pipe = Pipeline.model_validate(
        {
            "pipeline": 1,
            "name": "t",
            "version": "0",
            "domain": "stringency-toy",
            "answers": ["compare_groups"],
            "steps": [
                {
                    "id": "01_filter",
                    "module": "filter-rows@0.1.1",
                    "inputs": {"object": "$inputs.groups"},
                },
                {
                    "id": "02_summarize",
                    "module": "summarize-groups@0.1.1",
                    "inputs": {"object": "$steps.01_filter.object"},
                },
                {
                    "id": "04_compare",
                    "module": "compare-groups@0.1.0",
                    "inputs": {"object": "$steps.01_filter.object"},
                    "params": {"replicate_unit": "unit", "correction": "bh"},
                },
            ],
        }
    )
    ctx = make_ctx(
        p,
        "02_summarize",
        phase="post",
        output=OutputBundle(outputs={"table": OutputInfo("table", "table", "x", "blake3:00")}),
    )
    # 04_compare is downstream of 01_filter only in the real pipeline; make it downstream of 02 here
    pipe2 = pipe.model_copy(
        update={
            "steps": [
                pipe.steps[0],
                pipe.steps[1],
                pipe.steps[2].model_copy(
                    update={"inputs": {"object": "$steps.02_summarize.table"}}
                ),
            ]
        }
    )
    pc = ctx.project.__class__(**{**ctx.project.__dict__, "pipeline": pipe2})
    return GateContext(**{**ctx.__dict__, "project": pc})


def _run_one(pid: str, ctx: GateContext) -> bool:
    spec = registry.get(pid)
    assert spec is not None, pid
    assert spec.in_phase(ctx.phase), f"{pid} not in phase {ctx.phase}"
    return spec.fn(ctx).fired


@pytest.mark.parametrize("pid,fire,pass_", CASES, ids=[c[0] for c in CASES])
def test_predicate_must_fire_and_must_pass(
    project: Project, pid: str, fire: CtxFn, pass_: CtxFn
) -> None:
    assert _run_one(pid, fire(project)) is True, f"{pid} should fire"
    assert _run_one(pid, pass_(project)) is False, f"{pid} should pass"


def test_every_registered_predicate_has_a_case() -> None:
    covered = {c[0] for c in CASES}
    missing = (
        {s.id for s in registry.all()}
        - covered
        - {s.id for s in registry.all() if s.id.startswith("init.")}
    )
    # repro.seed_unset and judg.considered_set_missing are covered below with a synthetic module
    assert missing <= {"repro.seed_unset", "judg.considered_set_missing"}, missing


def test_seed_unset_and_considered_set(project: Project) -> None:
    from stringency.modules import ModuleManifest

    base = project.modules.require("compare-groups@0.1.0").manifest
    stoch = base.model_copy(
        update={
            "stochastic": True,
            "seed_param": "seed",
            "params_schema": {
                "type": "object",
                "properties": {"seed": {"type": "integer"}, **base.params_schema["properties"]},
            },
        }
    )
    assert isinstance(stoch, ModuleManifest)
    ctx = make_ctx(project, "04_compare")
    pc = ctx.project.__class__(
        **{**ctx.project.__dict__, "modules": {**ctx.project.modules, stoch.ref: stoch}}
    )
    ctx2 = GateContext(**{**ctx.__dict__, "project": pc})
    assert _run_one("repro.seed_unset", ctx2) is True
    act = ctx.action.__class__(
        **{**ctx.action.__dict__, "parameters": {**ctx.action.parameters, "seed": 7}}
    )
    assert _run_one("repro.seed_unset", GateContext(**{**ctx2.__dict__, "action": act})) is False

    lab = project.modules.require("label-groups@0.1.1").manifest
    cs = lab.model_copy(
        update={"judgment": lab.judgment.model_copy(update={"considered_set": True})}
    )  # type: ignore[union-attr]
    ctx3 = make_ctx(
        project, "03_label", phase="post", output=judgment_bundle(unanimous_replicates())
    )
    pc3 = ctx3.project.__class__(
        **{**ctx3.project.__dict__, "modules": {**ctx3.project.modules, cs.ref: cs}}
    )
    assert (
        _run_one("judg.considered_set_missing", GateContext(**{**ctx3.__dict__, "project": pc3}))
        is True
    )
    ctx4 = make_ctx(
        project,
        "03_label",
        phase="post",
        output=judgment_bundle(unanimous_replicates(), considered_set={"n": 3}),
    )
    assert (
        _run_one("judg.considered_set_missing", GateContext(**{**ctx4.__dict__, "project": pc3}))
        is False
    )


# -- policy ---------------------------------------------------------------------------


def _eff(policy: Policy, pid: str, profile: str) -> Disposition:
    spec = registry.get(pid)
    assert spec is not None
    return policy.effective(spec, profile)


def test_profiles_remap(project: Project) -> None:
    pol = project.policy
    assert _eff(pol, "toy.filter_after_summary", "standard") == Disposition.FLAG
    assert _eff(pol, "toy.filter_after_summary", "strict") == Disposition.BLOCK
    assert _eff(pol, "toy.no_correction", "exploratory") == Disposition.FLAG
    assert _eff(pol, "toy.no_correction", "standard") == Disposition.BLOCK


def test_invariants_never_remapped(project: Project) -> None:
    for pid in (
        "repro.dirty_tree",
        "repro.env_unpinned",
        "repro.input_digest_mismatch",
        "topo.undeclared_step",
        "topo.predecessor_incomplete",
        "param.undeclared",
    ):
        for prof in ("strict", "standard", "exploratory"):
            assert _eff(project.policy, pid, prof) == Disposition.BLOCK, (pid, prof)


def test_override_wins_over_remap(project: Project) -> None:
    # policy.yml overrides toy.filter_after_summary to log under exploratory (remap would give flag)
    assert _eff(project.policy, "toy.filter_after_summary", "exploratory") == Disposition.LOG


def test_param_policies(project: Project) -> None:
    pol = project.policy
    # locked: any change blocks
    assert _run_one(
        "param.locked_changed",
        make_ctx(project, "01_filter", proposed={"min_value": 12}, profile="strict"),
    )
    # ranged: in range passes, out of range blocks
    assert not _run_one(
        "param.out_of_range", make_ctx(project, "01_filter", proposed={"min_value": 12})
    )
    assert _run_one(
        "param.out_of_range", make_ctx(project, "01_filter", proposed={"min_value": 99})
    )
    assert _eff(pol, "param.out_of_range", "standard") == Disposition.BLOCK
    # free: out of range flags
    assert _eff(pol, "param.out_of_range", "exploratory") == Disposition.FLAG
    # undeclared blocks everywhere
    for prof in ("strict", "standard", "exploratory"):
        assert _run_one(
            "param.undeclared", make_ctx(project, "01_filter", proposed={"bogus": 1}, profile=prof)
        )
        assert _eff(pol, "param.undeclared", prof) == Disposition.BLOCK
    # a fixed parameter (no range) may not change even under standard
    from stringency.pipelines import ParamDecl

    step = project.pipeline.step("04_compare")
    fixed = step.model_copy(
        update={"params": {**step.params, "correction": ParamDecl(default="bh")}}
    )
    ctx = make_ctx(project, "04_compare", proposed={"correction": "bonferroni"})
    pipe = project.pipeline.model_copy(
        update={"steps": [fixed if s.id == "04_compare" else s for s in project.pipeline.steps]}
    )
    pc = ctx.project.__class__(**{**ctx.project.__dict__, "pipeline": pipe})
    assert _run_one("param.locked_changed", GateContext(**{**ctx.__dict__, "project": pc}))


def test_policy_digest_changes(project: Project, tmp_path):  # type: ignore[no-untyped-def]
    from stringency.policy import load_policy
    from stringency.predicates.registry import PredicateSpec, Registry

    d1 = project.policy.digest(registry)
    # a different policy file
    edited = tmp_path / "policy.yml"
    edited.write_text(
        (project.method_root / "policy.yml").read_text().replace("version: 0.1.0", "version: 0.1.1")
    )
    assert load_policy(edited).digest(registry) != d1
    # a different predicate version
    reg2 = Registry()
    for s in registry.all():
        reg2.add(
            PredicateSpec(
                **{**s.__dict__, "version": s.version + (1 if s.id == "toy.no_correction" else 0)}
            )
        )
    assert project.policy.digest(reg2) != d1
    assert project.policy.digest(registry) == d1


# -- gate writes ----------------------------------------------------------------------


def test_gate_writes_action_and_results_even_when_blocked(project: Project) -> None:
    from stringency.ids import new_id

    store = project.store
    run_id = new_id()
    store.open_run(
        {
            "run_id": run_id,
            "project_id": project.config.project_id,
            "git_sha": "x",
            "git_dirty": False,
            "host": "h",
            "user": "u",
            "policy_version": "0.1.0",
            "policy_digest": "pd",
            "stringency_version": "0",
        }
    )
    action, module = make_action(
        project, "04_compare", proposed={"correction": "none"}, run_id=run_id
    )
    write_action(store, action)
    ctx = make_ctx(project, "04_compare", action=action)
    result = evaluate(
        ctx,
        registry=registry,
        store=store,
        policy_digest="pd",
        module=module.manifest,
        runner="engine",
    )
    assert [r.spec.id for r in result.blocked] == ["toy.no_correction"]
    assert store.scalar("SELECT COUNT(*) FROM actions WHERE action_id=?", (action.action_id,)) == 1
    rows = store.all(
        "SELECT predicate_id, fired, default_disposition, effective_disposition FROM predicate_results WHERE action_id=?",
        (action.action_id,),
    )
    by = {r["predicate_id"]: r for r in rows}
    assert by["toy.no_correction"]["fired"] == 1
    assert by["toy.no_correction"]["effective_disposition"] == "block"
    assert by["toy.replication_unit"]["fired"] == 0
    # scope: judgment predicates not evaluated for a deterministic step
    assert "judg.evidence_exists" not in by
    assert {
        "topo.undeclared_step",
        "param.undeclared",
        "obj.feasibility",
        "repro.env_unpinned",
    } <= set(by)


def test_in_scope_specs_by_kind_and_runner(project: Project) -> None:
    lab = project.modules.require("label-groups@0.1.1").manifest
    post_ids = {
        s.id
        for s in in_scope_specs(
            registry, "post", operation="label_groups", module=lab, runner="engine"
        )
    }
    assert "judg.evidence_exists" in post_ids and "exec.plan_drift" not in post_ids
    filt = project.modules.require("filter-rows@0.1.1").manifest
    post_ids = {
        s.id
        for s in in_scope_specs(
            registry, "post", operation="filter_rows", module=filt, runner="operator"
        )
    }
    assert (
        "exec.plan_drift" in post_ids
        and "repro.env_unverified" in post_ids
        and "judg.evidence_exists" not in post_ids
    )


def test_action_param_sources(project: Project) -> None:
    action, _ = make_action(project, "01_filter", proposed={"min_value": 20})
    assert action.param_source == {"min_value": "agent"} and action.proposed_by == "agent"
    action, _ = make_action(project, "04_compare")
    assert action.param_source == {"replicate_unit": "default", "correction": "default"}
    assert action.proposed_by == "pipeline"
    assert SUMMARY_TABLE.cell("A", "mean_value") == (True, 74.31)
