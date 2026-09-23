"""K7 (design 7.1, 8.4): an item hold's verdict reaches the consensus output the next step
binds, and the post-phase gate is evaluated on the decided consensus once the item holds settle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency import hashing
from stringency.coverage import coverage_data
from stringency.project import Project
from stringency.review import queue, record_review
from stringency.runs import load_run
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def held(make_project: InitFn, fixture: str) -> tuple[Project, dict[str, str], str]:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / fixture)}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    run_id = p.store.one("SELECT run_id FROM runs ORDER BY rowid DESC LIMIT 1")["run_id"]
    return p, env, str(run_id)


def consensus_artifacts(p: Project, run_id: str) -> list[dict[str, object]]:
    return [
        dict(r)
        for r in p.store.all(
            "SELECT * FROM artifacts WHERE run_id=? AND step_id='03_label' AND name='consensus' "
            "ORDER BY rowid",
            (run_id,),
        )
    ]


def test_item_verdict_rewrites_consensus_output_and_next_step_binds_it(
    make_project: InitFn,
) -> None:
    p, env, run_id = held(make_project, "split.yml")
    before = consensus_artifacts(p, run_id)
    assert len(before) == 1
    stale = json.loads(Path(str(before[0]["path"])).read_text())
    a = next(i for i in stale["items"] if i["item_id"] == "A")
    assert a["source"] == "unresolved" and a["label"] is None

    h = queue(p)[0]
    res = record_review(p, h["hold_id"], "accept", replicate=1)
    assert res.step_status == "completed"

    after = consensus_artifacts(p, run_id)
    assert len(after) == 2
    assert after[0]["status"] == "superseded" and after[1]["status"] == "produced"
    path = str(after[1]["path"])
    assert after[1]["hash"] == hashing.hash_path(Path(path))
    decided = json.loads(Path(path).read_text())
    a = next(i for i in decided["items"] if i["item_id"] == "A")
    assert a["source"] == "accepted" and a["label"] == "abundant"
    assert a["review_id"] == res.review_id and a["hold_id"] == h["hold_id"]
    assert [i["item_id"] for i in decided["items"]] == [i["item_id"] for i in stale["items"]]
    assert all(i["source"] != "unresolved" for i in decided["items"])

    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["run_status"] == "completed"
    report_action = p.store.one(
        "SELECT inputs_json FROM actions WHERE run_id=? AND step_id='05_report' "
        "ORDER BY attempt DESC LIMIT 1",
        (run_id,),
    )
    assert str(after[1]["hash"]) in report_action["inputs_json"]
    assert str(before[0]["hash"]) not in report_action["inputs_json"]


def test_flag_is_deferred_while_item_holds_are_open(make_project: InitFn) -> None:
    p, env, run_id = held(make_project, "split_and_flag.yml")
    open_holds = p.store.all(
        "SELECT * FROM holds WHERE run_id=? AND step_id='03_label' AND resolved_by_review IS NULL",
        (run_id,),
    )
    assert [h["kind"] for h in open_holds] == ["run_disagreement"]
    held_event = p.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='03_label' "
        "AND event='status:held' ORDER BY seq DESC LIMIT 1",
        (run_id,),
    ) or p.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='03_label' "
        "AND payload_json LIKE '%deferred_flags%' ORDER BY seq DESC LIMIT 1",
        (run_id,),
    )
    assert held_event is not None
    assert "judg.confidence_consistent@1" in json.loads(held_event["payload_json"]).get(
        "deferred_flags", []
    )

    item = next(h for h in queue(p) if h["kind"] == "run_disagreement")
    res = record_review(p, item["hold_id"], "accept", replicate=1)
    assert res.step_status == "held"
    flags = p.store.all(
        "SELECT * FROM holds WHERE run_id=? AND step_id='03_label' AND kind='flag'", (run_id,)
    )
    assert len(flags) == 1 and flags[0]["resolved_by_review"] is None
    assert json.loads(flags[0]["context_json"])["predicate"] == "judg.confidence_consistent@1"
    # the post gate ran twice for the one action; coverage counts the flag once
    n = p.store.scalar(
        "SELECT COUNT(*) FROM predicate_results pr JOIN actions a ON a.action_id=pr.action_id "
        "WHERE a.run_id=? AND a.step_id='03_label' AND pr.predicate_id='judg.confidence_consistent'",
        (run_id,),
    )
    assert n == 2
    assert coverage_data(load_run(p, run_id))["gate"]["fired"]["flag"] == 1
    # the rewritten consensus carries the verdict
    latest = consensus_artifacts(p, run_id)[-1]
    a = next(
        i for i in json.loads(Path(str(latest["path"])).read_text())["items"] if i["item_id"] == "A"
    )
    assert a["source"] == "accepted" and a["label"] == "abundant"

    res2 = record_review(p, flags[0]["hold_id"], "accept", reason="context, not counter-evidence")
    assert res2.step_status == "completed"
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["run_status"] == "completed"
