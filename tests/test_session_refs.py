"""Every operator session that changes a project is named in its trace (2026-11-12). A study
runs over several sessions: a later session resumes a run an earlier one opened. The run
records the opening session (`runs.operator_session_ref`); before this, a later session that
carried the run on (`run`, `propose`, `deliver`) without a relayed review left no reference,
so an eval bundle could not link its transcript to the trace."""

from __future__ import annotations

import json
from typing import Any

import pytest

from stringency.db.store import Store
from stringency.project import Project
from stringency.review import queue, record_review
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli


def session(ref: str) -> dict[str, str]:
    return {
        "STRINGENCY_OPERATOR": "claude-science",
        "STRINGENCY_OPERATOR_VERSION": "1.2.3",
        "STRINGENCY_SESSION_REF": ref,
    }


def session_events(p: Project) -> list[dict[str, Any]]:
    return [
        {"run_id": r["run_id"], **json.loads(r["payload_json"])}
        for r in p.store.all(
            "SELECT run_id, payload_json FROM run_events WHERE event = 'session' ORDER BY seq"
        )
    ]


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def test_a_later_session_that_resumes_a_run_is_recorded(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    split = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}

    # session A opens the run, which holds
    r = cli(p, "run", env={**split, **session("cs:A")})
    assert r.exit_code == 10, r.output
    run_id = str(p.store.scalar("SELECT run_id FROM runs"))
    assert p.store.scalar("SELECT operator_session_ref FROM runs") == "cs:A"
    assert session_events(p) == []  # the opening session is the run's own column

    # the person decides at a terminal, with no session reference: nothing to record
    h = queue(p)[0]
    record_review(p, h["hold_id"], "accept", replicate=1)
    assert session_events(p) == []

    # session B, a day later, carries the same run on and delivers it
    r = cli(p, "run", "--deliver", "--json", env={**split, **session("cs:B")})
    assert r.exit_code == 0, r.output
    assert p.store.scalar("SELECT status FROM runs") == "completed"
    assert session_events(p) == [
        {"run_id": run_id, "session_ref": "cs:B", "harness": "claude-science", "version": "1.2.3"}
    ]
    # recorded in the trace before the change it made to the run
    seqs = {
        r["event"]: r["seq"]
        for r in p.store.all(
            "SELECT event, MIN(seq) AS seq FROM run_events WHERE run_id = ? GROUP BY event",
            (run_id,),
        )
    }
    assert seqs["session"] < seqs["delivered"]

    # the same session again records nothing new; session A returning is recorded again
    assert cli(p, "deliver", env=session("cs:B")).exit_code == 0
    assert [e["session_ref"] for e in session_events(p)] == ["cs:B"]
    assert cli(p, "deliver", env=session("cs:A")).exit_code == 0
    assert [e["session_ref"] for e in session_events(p)] == ["cs:B", "cs:A"]
    # a reading verb records nothing
    assert cli(p, "status", "--json", env=session("cs:C")).exit_code == 0
    assert [e["session_ref"] for e in session_events(p)] == ["cs:B", "cs:A"]

    # `status --json` names both sessions, each with the run it worked on
    st = json.loads(cli(p, "status", "--json").output)
    by_ref = {s["session_ref"]: s for s in st["sessions"]}
    assert set(by_ref) == {"cs:A", "cs:B"}
    assert by_ref["cs:B"]["runs"] == [run_id] and by_ref["cs:B"]["harness"] == "claude-science"
    assert by_ref["cs:B"]["version"] == "1.2.3"
    assert by_ref["cs:A"]["runs"] == [run_id]


def test_a_session_whose_change_is_rolled_back_is_noted_again(make_project: InitFn) -> None:
    """The store remembers which session it noted per run; a rollback forgets it, since the
    `session` event went with the transaction."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    assert cli(p, "run", env={**MOCK, **session("cs:A")}).exit_code == 0
    run_id = str(p.store.scalar("SELECT run_id FROM runs"))
    store = p.store
    with pytest.MonkeyPatch.context() as mp:
        for k, v in session("cs:B").items():
            mp.setenv(k, v)
        with pytest.raises(RuntimeError), store.transaction():
            store.run_event(run_id, "probe", {})
            raise RuntimeError("the change failed")
        assert session_events(p) == []
        store.run_event(run_id, "probe", {})
    assert [e["session_ref"] for e in session_events(p)] == ["cs:B"]


def test_another_process_s_session_is_seen_when_the_first_returns(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two processes on one trace (a long background `run` beside another session): X, then
    Y in another store, then X again in the first. X's return is recorded, so X's later work
    is not read as Y's (the review of #37: a per-store cache missed Y's event)."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    assert cli(p, "run", env={**MOCK, **session("cs:X")}).exit_code == 0
    run_id = str(p.store.scalar("SELECT run_id FROM runs"))
    first, second = p.store, Store.open(p.store.path)
    try:
        for ref, store in (("cs:X", first), ("cs:Y", second), ("cs:X", first)):
            for k, v in session(ref).items():
                monkeypatch.setenv(k, v)
            store.run_event(run_id, "probe", {})
    finally:
        second.close()
    assert [e["session_ref"] for e in session_events(p)] == ["cs:Y", "cs:X"]


def test_a_policy_reviewer_s_writes_record_no_session_event(make_project: InitFn) -> None:
    """`review --policy` runs under the policy process's own reference, which its review row
    records; noting it as a session too gave two `session` events per hold (the policy's,
    then the operator's on the next command)."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    op = session("cs:O")
    r = cli(p, "propose", "01_filter", "--set", "min_value=12", "--reason", "a floor", env=op)
    assert r.exit_code in (10, 11), r.output
    [h] = queue(p)
    r = cli(
        p,
        "review",
        "--verdict",
        "accept",
        "--hold",
        h["hold_id"],
        "--policy",
        "observe",
        "--reason",
        "observe: every hold is accepted",
        env={"STRINGENCY_SESSION_REF": "policy:observe:rep1"},
    )
    assert r.exit_code == 0, r.output
    assert (
        p.store.scalar(
            "SELECT operator_session_ref FROM reviews WHERE hold_id = ?", (h["hold_id"],)
        )
        == "policy:observe:rep1"
    )
    assert cli(p, "run", env={**MOCK, **op}).exit_code == 0
    assert session_events(p) == []


def test_present_records_its_presentation_and_no_session_event(make_project: InitFn) -> None:
    """`present` is a reading verb: it writes the `presented` mark, which carries the session
    itself, and no `session` event; `status --json` names the session from that mark."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    assert cli(p, "run", "--deliver", env={**MOCK, **session("cs:A")}).exit_code == 0
    before = p.store.scalar("SELECT COUNT(*) FROM run_events")
    r = cli(p, "present", "--json", env=session("cs:C"))
    assert r.exit_code == 0, r.output
    assert session_events(p) == []
    new = p.store.all(
        "SELECT event, payload_json FROM run_events WHERE rowid > 0 ORDER BY run_id, seq"
    )
    added = [x for x in new][before:]
    assert [x["event"] for x in added] == ["presented"]
    assert json.loads(added[0]["payload_json"])["session_ref"] == "cs:C"
    refs = {s["session_ref"] for s in json.loads(cli(p, "status", "--json").output)["sessions"]}
    assert refs == {"cs:A", "cs:C"}
