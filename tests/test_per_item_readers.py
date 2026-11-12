"""The readers of a judgment step's trace under `batching: per_item` (L172, the review of PR
34), and a second attempt's dispatch (found in the same review)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stringency import git
from stringency.coverage import coverage_data, render_coverage
from stringency.harness.base import Invocation, Request, Sampling
from stringency.harness.mock import MockHarness
from stringency.judgment import check_responses, check_text, execute_judgment
from stringency.machine import StepStatus
from stringency.project import Project
from stringency.runs import RunContext, open_or_resume
from stringency.steps import propose
from tests.conftest import InitFn, accept_hold
from tests.test_judgment import HARNESS, run_to_label
from tests.test_per_item import _judge


def _rc_on_disk(make_project: InitFn, batching: str = "per_item") -> RunContext:
    """A toy project whose method's label-groups module declares `batching` on disk, so every
    reader that plans the step again (check, resettle, review) sees it; run up to the label."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    if batching != "all_items":
        mod = p.method_root / "modules" / "label-groups" / "module.yml"
        mod.write_text(mod.read_text().replace("batching: all_items", f"batching: {batching}"))
        git.commit_all(p.method_root, batching)
        p = Project.load(p.root)
    rc = open_or_resume(p)
    run_to_label(rc)
    return rc


def _label(rc: RunContext, monkeypatch: pytest.MonkeyPatch, fixture: str, family: str) -> Any:
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / fixture))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", family)
    prop = propose(rc, "03_label")
    assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
    return prop, execute_judgment(rc, prop)


# -- 1. the judge shown beside a call is the one that answered that item ----------------------


def test_judge_of_a_per_item_call_is_the_call_that_answered_the_item(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = MockHarness.invoke

    def invoke(
        self: MockHarness,
        prompt: str,
        schema: dict[str, Any],
        *,
        sampling: Sampling,
        request: Request,
    ) -> Invocation:
        inv = original(self, prompt, schema, sampling=sampling, request=request)
        if request.item == "A":
            inv.model_resolved = "other-model-9"
        return inv

    monkeypatch.setattr(MockHarness, "invoke", invoke)
    rc = _rc_on_disk(make_project)
    _, out = _label(rc, monkeypatch, "split.yml", "direct")
    assert out.status == StepStatus.HELD
    h = rc.store.one("SELECT * FROM holds WHERE step_id='03_label' AND item_id='A'")

    from stringency.review_render import render

    view = render(rc.project, h)
    assert [r.model for r in view.replicates] == ["other-model-9"] * 3
    assert "judge: other-model-9 via direct" in view.text

    from stringency.present import _judgments_section

    sec = _judgments_section(rc.project, rc.run_id, "03_label", "A")  # type: ignore[arg-type]
    assert sec is not None
    shown = json.dumps(sec)
    assert "other-model-9" in shown and "mock-model-1" not in shown
    # item B's calls name the mock's own model
    sec_b = _judgments_section(rc.project, rc.run_id, "03_label", None)  # type: ignore[arg-type]
    assert sec_b is not None and "mock-model-1" in json.dumps(sec_b)


# -- 2. distinct orderings mean the same under both batchings -----------------------------------


@pytest.mark.parametrize("batching", ["all_items", "per_item"])
def test_prompt_variants_counts_orderings_not_items(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch, batching: str
) -> None:
    rc, _, out = _judge(make_project, monkeypatch, "unanimous.yml", batching)
    assert out.status == StepStatus.COMPLETED
    j = next(x for x in coverage_data(rc)["judgment"] if x["step"] == "03_label")
    assert j["prompt_variants"] == 3


# -- 3. the check counts responses and replicates apart -----------------------------------------


def test_check_counts_responses_and_replicates(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _rc_on_disk(make_project)
    _, out = _label(rc, monkeypatch, "unanimous.yml", "dispatch")
    assert out.status == StepStatus.DISPATCHING
    ddir = rc.project.step_dir(rc.run_id, "03_label") / "dispatch"
    responses = []
    for n in range(1, 10):
        req = json.loads((ddir / f"req_{n}.json").read_text())
        responses.append(
            {
                "nonce": req["nonce"],
                "structured": {
                    "item_id": req["item"],
                    "label": None,
                    "confidence": "abstain",
                    "abstain": True,
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "rationale": "no call",
                },
                "reported": {"model": "m", "agent": "a", "tools_available": []},
            }
        )
    res = check_responses(rc, {"step_id": "03_label", "responses": responses})
    assert res["responses"] == 9 and len(res["replicates"]) == 3
    assert check_text(res).startswith("checked 9 response(s) from 3 replicate(s) for 03_label")


# -- 5. a per-item answer about another item says so --------------------------------------------


def test_per_item_answer_naming_another_item_is_invalid_with_its_cause(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc, prop, out = _judge(make_project, monkeypatch, "wrong_item.yml", "per_item")
    assert out.status == StepStatus.REJECTED
    star = rc.store.one(
        "SELECT * FROM judgments WHERE run_id=? AND step_id='03_label' AND schema_valid=0",
        (rc.run_id,),
    )
    assert star is not None and star["replicate"] == 2
    err = json.loads(star["extra_json"])["error"]
    assert "item A" in err and "answers item B" in err, err
    fired = {
        r["predicate_id"]
        for r in rc.store.all(
            "SELECT predicate_id FROM predicate_results WHERE action_id=? AND fired=1",
            (prop.action.action_id,),
        )
    }
    assert "judg.items_incomplete" not in fired and "judg.replicates_below_min" in fired
    # the retry carried the cause, and the retried call is on the trace
    invs = rc.store.all(
        "SELECT * FROM invocations WHERE run_id=? AND replicate=2 ORDER BY rowid", (rc.run_id,)
    )
    assert sum(1 for i in invs if json.loads(i["sampling_json"])["item"] == "A") == 2


# -- 6. a step's tokens: the attempt shown and every attempt apart ------------------------------


def test_step_tokens_show_the_attempt_and_every_attempt_apart(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    run_to_label(rc)
    _, out1 = _label(rc, monkeypatch, "invalid_third.yml", "direct")
    assert out1.status == StepStatus.REJECTED
    prop2, out2 = _label(rc, monkeypatch, "unanimous.yml", "direct")
    assert prop2.action.attempt == 2 and out2.status == StepStatus.COMPLETED, out2.message
    d = coverage_data(rc)
    j = next(x for x in d["judgment"] if x["step"] == "03_label")
    assert j["attempt"] == 2 and j["attempts"] == 2
    assert j["tokens"]["calls"] == 3  # attempt 2
    assert j["tokens_all_attempts"]["calls"] == 7  # attempt 1: two calls, then one and a retry
    assert d["judgment_tokens"]["calls"] == 7
    text = render_coverage(d)
    assert "judges, attempt 2: tokens" in text and "all 2 attempts: tokens" in text
    assert "judges over the run, every attempt:" in text


# -- 4. a second attempt dispatches afresh ----------------------------------------------


@pytest.mark.parametrize("batching", ["all_items", "per_item"])
def test_second_attempt_dispatches_fresh_requests(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch, batching: str
) -> None:
    rc = _rc_on_disk(make_project, batching)
    prop1, out = _label(rc, monkeypatch, "unanimous.yml", "dispatch")
    assert out.status == StepStatus.DISPATCHING
    ddir1 = rc.project.step_dir(rc.run_id, "03_label") / "dispatch"
    (ddir1 / "resp_2.json").write_text(
        json.dumps({"nonce": "WRONG", "structured": {}, "reported": {"model": "x"}})
    )
    out1 = execute_judgment(rc, prop1)
    assert out1.status == StepStatus.REJECTED
    first = sorted(p.name for p in ddir1.iterdir())

    prop2, out2 = _label(rc, monkeypatch, "unanimous.yml", "dispatch")
    assert prop2.action.attempt == 2 and out2.status == StepStatus.DISPATCHING, out2.message
    from stringency.runloop import next_step

    nx = next_step(rc)
    assert nx.kind == "dispatching"
    ddir2 = Path(nx.detail["dispatch_dir"])
    # attempt 2 is answered on its own requests: before this it collected attempt 1's
    # responses, every one failed the nonce check and the step was rejected again
    out3 = execute_judgment(rc, prop2)
    assert out3.status == StepStatus.COMPLETED, out3.message
    req = json.loads((ddir2 / "req_1.json").read_text())
    assert req["nonce"].startswith(prop2.action.action_id)
    assert ddir2 != ddir1 and nx.detail["requests"] == len(list(ddir1.glob("req_*.json")))
    # attempt 1's files stay where its invocation rows say they are
    assert sorted(p.name for p in ddir1.iterdir()) == first
    rows = rc.store.all(
        "SELECT i.request_path, a.attempt FROM invocations i JOIN actions a "
        "ON a.action_id = i.action_id WHERE i.run_id=? AND i.step_id='03_label'",
        (rc.run_id,),
    )
    for r in rows:
        body = json.loads(Path(r["request_path"]).read_text())
        assert body["nonce"].startswith(
            prop1.action.action_id if r["attempt"] == 1 else prop2.action.action_id
        )
