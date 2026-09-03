"""M6: judgment module execution through the direct mock and the dispatch mock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency.exit_codes import ConfigError
from stringency.judgment import execute_judgment
from stringency.machine import StepStatus
from stringency.runs import RunContext, open_or_resume
from stringency.steps import execute_engine, propose
from tests.conftest import InitFn, accept_hold

HARNESS = Path(__file__).parent / "fixtures" / "harness"


@pytest.fixture
def engine_rc(make_project: InitFn) -> RunContext:
    p = make_project(pipeline="toy-engine", execution="engine")
    h = p.confirm_hold()
    accept_hold(p.store, h["hold_id"])
    return open_or_resume(p)


def run_to_label(rc: RunContext) -> None:
    for sid in ("01_filter", "02_summarize"):
        prop = propose(rc, sid)
        assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
        out = execute_engine(rc, prop)
        assert out.status == StepStatus.COMPLETED, out.message


def label(rc: RunContext, fixture: str, monkeypatch: pytest.MonkeyPatch, family: str = "direct"):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / fixture))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", family)
    prop = propose(rc, "03_label")
    assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
    return prop, execute_judgment(rc, prop)


def test_unanimous_direct_completes(engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "unanimous.yml", monkeypatch)
    assert out.status == StepStatus.COMPLETED, out.message
    store = engine_rc.store
    cons = {
        r["item_id"]: r
        for r in store.all(
            "SELECT * FROM consensus WHERE run_id=? AND step_id='03_label'", (engine_rc.run_id,)
        )
    }
    assert {k: v["label"] for k, v in cons.items()} == {
        "A": "abundant",
        "B": "sparse",
        "C": "variable",
    }
    assert all(v["source"] == "agreed" for v in cons.values())
    invs = store.all(
        "SELECT * FROM invocations WHERE run_id=? AND step_id='03_label'", (engine_rc.run_id,)
    )
    assert len(invs) == 3 and all(
        i["via"] == "direct" and i["isolation"] == "enforced" and i["schema_valid"] for i in invs
    )
    assert all(i["model_resolved"] == "mock-model-1" and i["bit_reproducible"] == 0 for i in invs)
    assert (
        store.scalar(
            "SELECT COUNT(*) FROM judgments WHERE run_id=? AND step_id='03_label'",
            (engine_rc.run_id,),
        )
        == 9
    )
    # prompt stored once, content-addressed, and contains only declared variables
    prompt = store.message(invs[0]["prompt_hash"])
    assert prompt is not None and "abundant" in prompt and "mean_value" in prompt
    assert "row_id" not in prompt and "value\n" not in prompt  # matrix column names absent
    outs = store.all(
        "SELECT name FROM artifacts WHERE run_id=? AND step_id='03_label'", (engine_rc.run_id,)
    )
    assert {o["name"] for o in outs} == {"judgments", "consensus"}
    cj = json.loads(
        Path(
            engine_rc.project.step_dir(engine_rc.run_id, "03_label") / "consensus.json"
        ).read_text()
    )
    assert cj["items"][0]["source"] == "agreed"


def test_dispatch_mock_writes_requests_then_collects(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "unanimous.yml", monkeypatch, family="dispatch")
    assert out.status == StepStatus.DISPATCHING
    ddir = engine_rc.project.step_dir(engine_rc.run_id, "03_label") / "dispatch"
    reqs = sorted(ddir.glob("req_*.json"))
    assert len(reqs) == 3 and (ddir / "manifest.json").exists()
    req1 = json.loads(reqs[0].read_text())
    assert req1["nonce"] == f"{prop.action.action_id}-1" and "nonce" in req1["prompt"]
    assert not list(ddir.glob("resp_*.json"))
    assert engine_rc.store.scalar("SELECT COUNT(*) FROM invocations") == 0
    # second run: the mock plays the subagents and the engine collects
    out2 = execute_judgment(engine_rc, prop)
    assert out2.status == StepStatus.COMPLETED, out2.message
    invs = engine_rc.store.all("SELECT * FROM invocations WHERE step_id='03_label'")
    assert len(invs) == 3
    assert all(
        i["via"] == "subagent" and i["isolation"] == "as_reported" and i["nonce_ok"] == 1
        for i in invs
    )
    assert all(json.loads(i["reported_json"])["saw_conversation"] is False for i in invs)
    # requests are never rewritten
    assert json.loads(reqs[0].read_text()) == req1


def test_dispatch_wrong_nonce_marks_replicate_invalid(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "unanimous.yml", monkeypatch, family="dispatch")
    ddir = engine_rc.project.step_dir(engine_rc.run_id, "03_label") / "dispatch"
    (ddir / "resp_2.json").write_text(
        json.dumps({"nonce": "WRONG", "structured": {"items": []}, "reported": {"model": "x"}})
    )
    out2 = execute_judgment(engine_rc, prop)
    # one invalid replicate: below the policy minimum of 3 valid -> rejected by judg.replicates_below_min,
    # and run_disagreement holds would follow if it were not
    assert out2.status == StepStatus.REJECTED
    assert out2.gate is not None and "judg.replicates_below_min" in [
        r.spec.id for r in out2.gate.blocked
    ]
    inv2 = engine_rc.store.one("SELECT * FROM invocations WHERE replicate=2")
    assert inv2["nonce_ok"] == 0 and inv2["schema_valid"] == 0


def test_two_of_three_holds_run_disagreement(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "split.yml", monkeypatch)
    assert out.status == StepStatus.HELD
    holds = engine_rc.store.all(
        "SELECT * FROM holds WHERE step_id='03_label' AND resolved_by_review IS NULL"
    )
    assert len(holds) == 1 and holds[0]["kind"] == "run_disagreement" and holds[0]["item_id"] == "A"
    assert holds[0]["waits_on_role"] == "reviewer"
    cons = engine_rc.store.one("SELECT * FROM consensus WHERE item_id='A'")
    assert cons["source"] == "unresolved" and cons["label"] is None
    assert json.loads(cons["replicate_labels_json"]) == ["abundant", "abundant", "uniform"]


def test_one_abstention_standard_holds_relaxed_completes(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    for profile, expected in (("standard", StepStatus.HELD), ("exploratory", StepStatus.COMPLETED)):
        p = make_project(pipeline="toy-engine", execution="engine", profile=profile)
        accept_hold(p.store, p.confirm_hold()["hold_id"])
        rc = open_or_resume(p)
        run_to_label(rc)
        prop, out = label(rc, "one_abstain.yml", monkeypatch)
        assert out.status == expected, (profile, out.message)
        if expected == StepStatus.HELD:
            h = rc.store.one(
                "SELECT * FROM holds WHERE step_id='03_label' AND resolved_by_review IS NULL"
            )
            assert h["kind"] == "self_uncertain" and h["item_id"] == "A"
        else:
            c = rc.store.one("SELECT * FROM consensus WHERE item_id='A'")
            assert c["source"] == "agreed" and c["label"] == "abundant"


@pytest.mark.parametrize(
    "fixture,predicate",
    [
        ("bad_number.yml", "judg.numeric_claims_match"),
        ("bad_vocab.yml", "judg.vocabulary_resolves"),
        ("bad_ref.yml", "judg.evidence_exists"),
    ],
)
def test_post_gate_blocks(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch, fixture: str, predicate: str
) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, fixture, monkeypatch)
    assert out.status == StepStatus.REJECTED, out.message
    assert out.gate is not None and predicate in [r.spec.id for r in out.gate.blocked]
    assert (
        engine_rc.store.scalar(
            "SELECT COUNT(*) FROM artifacts WHERE step_id='03_label' AND status='rejected'"
        )
        == 2
    )


def test_invalid_replicate_after_retry(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "invalid_third.yml", monkeypatch)
    invs = engine_rc.store.all("SELECT * FROM invocations WHERE replicate=3 ORDER BY rowid")
    assert len(invs) == 2 and all(i["schema_valid"] == 0 for i in invs)  # one retry, both invalid
    assert (
        engine_rc.store.scalar(
            "SELECT COUNT(*) FROM judgments WHERE replicate=3 AND schema_valid=0"
        )
        == 1
    )
    # 2 valid replicates < replicates_min 3 -> blocked; the hold would be run_disagreement otherwise
    assert out.status == StepStatus.REJECTED
    assert out.gate is not None and "judg.replicates_below_min" in [
        r.spec.id for r in out.gate.blocked
    ]


def test_undeclared_template_variable_fails_before_invocation(
    engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_to_label(engine_rc)
    tmpl = engine_rc.project.modules.require("label-groups@0.1.0").path / "prompt.md"
    tmpl.write_text(tmpl.read_text() + "\n{{ matrix }}\n")
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / "unanimous.yml"))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", "direct")
    prop = propose(engine_rc, "03_label")
    with pytest.raises(ConfigError, match="undeclared"):
        execute_judgment(engine_rc, prop)
    assert engine_rc.store.scalar("SELECT COUNT(*) FROM invocations") == 0


def test_report_step_numeric_claims(engine_rc: RunContext, monkeypatch: pytest.MonkeyPatch) -> None:
    run_to_label(engine_rc)
    prop, out = label(engine_rc, "unanimous.yml", monkeypatch)
    assert out.status == StepStatus.COMPLETED
    for sid in ("04_compare", "05_report"):
        prop = propose(engine_rc, sid)
        assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
        out = execute_engine(engine_rc, prop)
        assert out.status == StepStatus.COMPLETED, out.message
    report = (engine_rc.project.step_dir(engine_rc.run_id, "05_report") / "report.md").read_text()
    assert "abundant" in report and "sparse" in report
    row = engine_rc.store.one(
        "SELECT fired FROM predicate_results WHERE action_id=? AND predicate_id='judg.numeric_claims_match'",
        (prop.action.action_id,),
    )
    assert row is not None and row["fired"] == 0
    assert engine_rc.run["status"] == "completed"
