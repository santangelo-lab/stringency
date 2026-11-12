"""Backlog L172: under `batching: per_item` a request carries its replicate and its item apart.

Three items by three replicates is nine requests and three replicates, never nine replicates;
the same answers give the same consensus under `per_item` and `all_items`, whichever harness
family collects them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stringency.coverage import coverage_data, render_coverage
from stringency.exit_codes import RefusedError
from stringency.judgment import execute_judgment
from stringency.machine import StepStatus
from stringency.runloop import dispatch_target
from stringency.runs import RunContext, open_or_resume
from stringency.steps import Proposal, propose
from tests.conftest import InitFn, accept_hold
from tests.test_judgment import HARNESS, run_to_label

ITEMS = ("A", "B", "C")


def _rc(make_project: InitFn) -> RunContext:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    run_to_label(rc)
    return rc


def _propose(
    rc: RunContext, monkeypatch: pytest.MonkeyPatch, fixture: str, batching: str, family: str
) -> Proposal:
    """Propose the toy's judgment step with its module's batching set to `batching`."""
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / fixture))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", family)
    prop = propose(rc, "03_label")
    assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
    m = prop.plan.module.manifest
    assert m.judgment is not None
    patched = m.model_copy(
        update={"judgment": m.judgment.model_copy(update={"batching": batching})}
    )
    object.__setattr__(prop.plan.module, "manifest", patched)
    return prop


def _consensus(rc: RunContext) -> dict[str, dict[str, Any]]:
    return {
        r["item_id"]: {
            "label": r["label"],
            "source": r["source"],
            "replicate_labels": json.loads(r["replicate_labels_json"]),
            "replicate_confidence": json.loads(r["replicate_confidence_json"]),
        }
        for r in rc.store.all(
            "SELECT * FROM consensus WHERE run_id=? AND step_id='03_label'", (rc.run_id,)
        )
    }


def _judge(
    make_project: InitFn,
    monkeypatch: pytest.MonkeyPatch,
    fixture: str,
    batching: str,
    family: str = "direct",
) -> tuple[RunContext, Proposal, Any]:
    rc = _rc(make_project)
    prop = _propose(rc, monkeypatch, fixture, batching, family)
    out = execute_judgment(rc, prop)
    if family == "dispatch":
        assert out.status == StepStatus.DISPATCHING, out.message
        out = execute_judgment(rc, prop)
    return rc, prop, out


def test_per_item_numbers_replicates_by_the_module(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nine requests, three replicates: no `judg.items_incomplete`, no invalid replicate."""
    rc, prop, out = _judge(make_project, monkeypatch, "unanimous.yml", "per_item")
    assert out.status == StepStatus.COMPLETED, out.message
    invs = rc.store.all(
        "SELECT * FROM invocations WHERE run_id=? AND step_id='03_label' ORDER BY rowid",
        (rc.run_id,),
    )
    assert len(invs) == 9
    assert sorted({i["replicate"] for i in invs}) == [1, 2, 3]
    assert len({i["nonce"] for i in invs}) == 9
    asked = [(i["replicate"], json.loads(i["sampling_json"])["item"]) for i in invs]
    assert sorted(asked) == [(r, it) for r in (1, 2, 3) for it in ITEMS]
    rows = rc.store.all(
        "SELECT replicate, item_id FROM judgments WHERE run_id=? AND step_id='03_label'",
        (rc.run_id,),
    )
    assert sorted((r["replicate"], r["item_id"]) for r in rows) == sorted(asked)
    fired = rc.store.all(
        "SELECT predicate_id FROM predicate_results WHERE action_id=? AND fired=1",
        (prop.action.action_id,),
    )
    assert "judg.items_incomplete" not in {f["predicate_id"] for f in fired}
    # each request's prompt asks about its own item and shows that item's row alone
    for inv in invs:
        prompt = rc.store.message(inv["prompt_hash"]) or ""
        item = json.loads(inv["sampling_json"])["item"]
        assert f"Assign each of these items a label: {item}." in prompt
        others = [x for x in ITEMS if x != item]
        assert not any(f"\n{x}\t" in prompt for x in others), (item, prompt)
    # the judgments output reads as an all_items one: three replicates of three items
    lines = [json.loads(x) for x in prop.plan.output_paths["judgments"].read_text().splitlines()]
    assert sorted({x["replicate"] for x in lines}) == [1, 2, 3] and len(lines) == 9


@pytest.mark.parametrize("family", ["direct", "dispatch"])
@pytest.mark.parametrize("fixture", ["unanimous.yml", "split.yml", "one_abstain.yml"])
def test_per_item_and_all_items_give_the_same_consensus(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch, fixture: str, family: str
) -> None:
    """The same answers (a mock rule names the module's replicate) decide alike."""
    rc_all, _, out_all = _judge(make_project, monkeypatch, fixture, "all_items", family)
    rc_per, _, out_per = _judge(make_project, monkeypatch, fixture, "per_item", family)
    assert out_per.status == out_all.status, (out_per.message, out_all.message)
    assert _consensus(rc_per) == _consensus(rc_all)
    holds = "SELECT kind, item_id, reason FROM holds WHERE run_id=? AND step_id='03_label' ORDER BY item_id"
    assert [dict(h) for h in rc_per.store.all(holds, (rc_per.run_id,))] == [
        dict(h) for h in rc_all.store.all(holds, (rc_all.run_id,))
    ]
    cov_all = next(j for j in coverage_data(rc_all)["judgment"] if j["step"] == "03_label")
    cov_per = next(j for j in coverage_data(rc_per)["judgment"] if j["step"] == "03_label")
    assert cov_per["replicates"] == cov_all["replicates"] == 3
    assert cov_per["items"] == cov_all["items"] == 3


def test_per_item_dispatch_files_carry_replicate_and_item(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    rc = _rc(make_project)
    prop = _propose(rc, monkeypatch, "unanimous.yml", "per_item", "dispatch")
    out = execute_judgment(rc, prop)
    assert out.status == StepStatus.DISPATCHING
    ddir = rc.project.step_dir(rc.run_id, "03_label") / "dispatch"
    manifest = json.loads((ddir / "manifest.json").read_text())
    assert manifest["replicates"] == 3
    assert len(manifest["requests"]) == len(manifest["responses"]) == 9
    reqs = [json.loads((ddir / f"req_{n}.json").read_text()) for n in range(1, 10)]
    assert [(r["replicate"], r["item"]) for r in reqs] == [
        (rep, it) for rep in (1, 2, 3) for it in ITEMS
    ]
    assert [r["nonce"] for r in reqs] == [f"{prop.action.action_id}-{n}" for n in range(1, 10)]
    # `run --responses` expects one response per request, not per replicate
    with pytest.raises(RefusedError, match="expects 9"):
        dispatch_target(rc, {"step_id": "03_label", "responses": [{}] * 3})
    ddir_ok, paths = dispatch_target(rc, {"step_id": "03_label", "responses": [{}] * 9})
    assert ddir_ok == ddir and [p.name for p in paths] == [f"resp_{n}.json" for n in range(1, 10)]


def test_per_item_one_bad_response_invalidates_its_replicate(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One item's response with a wrong nonce makes its replicate invalid, as one wrong response
    does under all_items; the trace names the item."""
    rc = _rc(make_project)
    prop = _propose(rc, monkeypatch, "unanimous.yml", "per_item", "dispatch")
    execute_judgment(rc, prop)
    ddir = rc.project.step_dir(rc.run_id, "03_label") / "dispatch"
    bad = json.loads((ddir / "req_5.json").read_text())  # replicate 2, item B
    assert (bad["replicate"], bad["item"]) == (2, "B")
    Path(ddir / "resp_5.json").write_text(
        json.dumps({"nonce": "WRONG", "structured": {}, "reported": {"model": "x"}})
    )
    out = execute_judgment(rc, prop)
    assert out.status == StepStatus.REJECTED
    assert out.gate is not None and "judg.replicates_below_min" in [
        r.spec.id for r in out.gate.blocked
    ]
    star = rc.store.one(
        "SELECT * FROM judgments WHERE run_id=? AND step_id='03_label' AND schema_valid=0",
        (rc.run_id,),
    )
    assert star["replicate"] == 2 and star["item_id"] == "*"
    assert "item B" in json.loads(star["extra_json"])["error"]
    assert (
        rc.store.scalar(
            "SELECT COUNT(*) FROM judgments WHERE run_id=? AND step_id='03_label' AND replicate=2 "
            "AND schema_valid=1",
            (rc.run_id,),
        )
        == 0
    )


def test_coverage_counts_judges_tokens(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L193: the judgment block sums tokens in and out per step and for the run."""
    rc, _, out = _judge(make_project, monkeypatch, "unanimous.yml", "per_item")
    assert out.status == StepStatus.COMPLETED
    invs = rc.store.all(
        "SELECT tokens_in, tokens_out FROM invocations WHERE run_id=?", (rc.run_id,)
    )
    d = coverage_data(rc)
    j = next(x for x in d["judgment"] if x["step"] == "03_label")
    want = {
        "calls": 9,
        "tokens_in": sum(i["tokens_in"] for i in invs),
        "tokens_out": sum(i["tokens_out"] for i in invs),
        "calls_without_tokens_in": 0,
        "calls_without_tokens_out": 0,
    }
    assert j["tokens"] == want and d["judgment_tokens"] == want
    assert want["tokens_in"] > 0
    text = render_coverage(d)
    assert f"tokens {want['tokens_in']} in, {want['tokens_out']} out over 9 calls" in text


def test_per_item_item_hold_reviewed_and_resettled(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per_item module on disk: the split item holds, a person accepts replicate 1's call, and
    the consensus is rebuilt from the trace (`replicates_from_trace`) as under all_items."""
    from stringency import git
    from stringency.project import Project
    from stringency.review import queue, record_review
    from tests.test_run import MOCK, cli

    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    mod = p.method_root / "modules" / "label-groups" / "module.yml"
    mod.write_text(mod.read_text().replace("batching: all_items", "batching: per_item"))
    git.commit_all(p.method_root, "per_item")
    p = Project.load(p.root)
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    assert p.store.scalar("SELECT COUNT(*) FROM invocations WHERE step_id='03_label'") == 9
    holds = queue(p)
    assert [(h["kind"], h["item_id"]) for h in holds] == [("run_disagreement", "A")]
    res = record_review(p, holds[0]["hold_id"], "accept", replicate=1)
    assert res.step_status == "completed"
    path = p.store.one(
        "SELECT path FROM artifacts WHERE step_id='03_label' AND name='consensus' "
        "AND status='produced' ORDER BY rowid DESC LIMIT 1"
    )["path"]
    a = next(i for i in json.loads(Path(path).read_text())["items"] if i["item_id"] == "A")
    assert a["source"] == "accepted" and a["label"] == "abundant" and a["chosen_replicate"] == 1
    assert a["replicate_labels"] == ["abundant", "abundant", "uniform"]


def test_coverage_shows_missing_token_counts_as_missing(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L193: the dispatch mock's subagents report no usage, as the subagent harness's usually
    do; the totals read as not reported, never as zero."""
    rc, _, out = _judge(make_project, monkeypatch, "unanimous.yml", "all_items", "dispatch")
    assert out.status == StepStatus.COMPLETED
    d = coverage_data(rc)
    none = {
        "calls": 3,
        "tokens_in": None,
        "tokens_out": None,
        "calls_without_tokens_in": 3,
        "calls_without_tokens_out": 3,
    }
    assert d["judgment_tokens"] == none
    assert next(x for x in d["judgment"] if x["step"] == "03_label")["tokens"] == none
    assert "tokens not reported by any of 3 calls" in render_coverage(d)


def test_judge_tokens_partial_and_per_step() -> None:
    """Some calls reported and some did not: the sum is over those that did, and the count of
    the others is carried beside it."""
    import sqlite3

    from stringency.coverage import judge_tokens, tokens_text

    class _Store:
        def __init__(self) -> None:
            self.db = sqlite3.connect(":memory:")
            self.db.row_factory = sqlite3.Row
            self.db.execute(
                "CREATE TABLE invocations (run_id TEXT, step_id TEXT, tokens_in INTEGER, "
                "tokens_out INTEGER)"
            )

        def one(self, sql: str, params: tuple[Any, ...]) -> Any:
            return self.db.execute(sql, params).fetchone()

    st = _Store()
    st.db.executemany(
        "INSERT INTO invocations VALUES (?, ?, ?, ?)",
        [
            ("r", "a", 100, 10),
            ("r", "a", None, None),
            ("r", "b", 50, None),
            ("other", "a", 999, 999),
        ],
    )
    a = judge_tokens(st, "r", "a")
    assert a == {
        "calls": 2,
        "tokens_in": 100,
        "tokens_out": 10,
        "calls_without_tokens_in": 1,
        "calls_without_tokens_out": 1,
    }
    assert tokens_text(a) == (
        "tokens 100 in, 10 out over 2 calls; 1 of them reported no count, so the totals are partial"
    )
    run = judge_tokens(st, "r")
    assert (run["calls"], run["tokens_in"], run["tokens_out"]) == (3, 150, 10)
    assert (run["calls_without_tokens_in"], run["calls_without_tokens_out"]) == (1, 2)
    assert "1 reported no input count and 2 no output count" in tokens_text(run)
    b = judge_tokens(st, "r", "b")
    assert tokens_text(b) == (
        "tokens 50 in, none reported out over 1 call; 0 reported no input count and 1 no "
        "output count, so the totals are partial"
    )
    assert judge_tokens(st, "none") == {
        "calls": 0,
        "tokens_in": None,
        "tokens_out": None,
        "calls_without_tokens_in": 0,
        "calls_without_tokens_out": 0,
    }
