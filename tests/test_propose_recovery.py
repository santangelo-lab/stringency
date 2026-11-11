"""L107: a step left `proposed` by an engine interrupted after the proposal's commit is
recovered by evaluating the same recorded Action again, at each of the three places the
interruption can fall. L94: the operator withdraws a proposal held on its pre-gate flags."""

from __future__ import annotations

import json

import pytest

import stringency.steps as steps_mod
from stringency.exit_codes import RefusedError
from stringency.machine import StepStatus
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.steps import propose, recover_proposed, withdraw_proposal
from tests.conftest import InitFn
from tests.test_run import MOCK, cli, confirmed

STEP = "01_filter"


class Interrupted(RuntimeError):
    pass


def status(p: Project) -> str:
    return str(p.store.scalar("SELECT status FROM steps WHERE step_id = ?", (STEP,)))


def open_hold_ids(p: Project) -> list[str]:
    return [
        str(r["hold_id"])
        for r in p.store.all(
            "SELECT hold_id FROM holds WHERE step_id = ? AND resolved_by_review IS NULL "
            "AND resolved_via IS NULL",
            (STEP,),
        )
    ]


def flagging_proposal(p: Project) -> None:
    """An agent's value for a decision point: `param.agent_proposed` flags it."""
    rc = open_or_resume(p, new=True)
    propose(rc, STEP, {"min_value": 12}, rationale="twelve")


def n_results(p: Project) -> int:
    """The pre-gate rows of the step's proposals (the init predicates' rows are not its)."""
    return int(
        p.store.scalar(
            "SELECT COUNT(*) FROM predicate_results WHERE phase = 'pre' AND action_id IN "
            "(SELECT action_id FROM actions WHERE step_id = ?)",
            (STEP,),
        )
    )


def events(p: Project) -> list[str]:
    return [
        str(r["event"])
        for r in p.store.all(
            "SELECT event FROM step_events WHERE step_id = ? ORDER BY seq", (STEP,)
        )
    ]


def test_interrupted_before_any_result(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")

    def boom(*a: object, **k: object) -> None:
        raise Interrupted

    with monkeypatch.context() as m:
        m.setattr(steps_mod, "evaluate", boom)
        with pytest.raises(Interrupted):
            flagging_proposal(p)
    assert status(p) == "proposed"
    assert n_results(p) == 0
    # a second proposal is refused and says how the first one is finished
    rc = open_or_resume(p)
    with pytest.raises(RefusedError, match="gate did not finish"):
        propose(rc, STEP, {"min_value": 9}, rationale="nine")
    assert p.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id = ?", (STEP,)) == 1
    prop = recover_proposed(rc, STEP)
    assert prop.status == StepStatus.HELD and status(p) == "held"
    assert prop.action.parameters["min_value"] == 12 and prop.action.attempt == 1
    ev = p.store.one("SELECT payload_json FROM step_events WHERE event = 'gate_recovered'")
    assert json.loads(ev["payload_json"])["interrupted_results"] == 0
    assert len(open_hold_ids(p)) == len(prop.holds) >= 1


def test_interrupted_after_some_results(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    real = steps_mod.evaluate

    def partial(ctx, **kw):  # type: ignore[no-untyped-def]
        from stringency.gate import in_scope_specs

        specs = in_scope_specs(
            kw["registry"],
            ctx.phase,
            operation=ctx.action.operation,
            module=kw["module"],
            runner=kw["runner"],
        )
        real(ctx, **{**kw, "only": specs[:2]})
        raise Interrupted

    with monkeypatch.context() as m:
        m.setattr(steps_mod, "evaluate", partial)
        with pytest.raises(Interrupted):
            flagging_proposal(p)
    assert status(p) == "proposed"
    assert n_results(p) == 2
    r = cli(p, "run", "--json", env=MOCK)  # `run` recovers it and reports the hold
    assert r.exit_code == 10, r.output
    assert status(p) == "held"
    ev = json.loads(
        p.store.one("SELECT payload_json FROM step_events WHERE event = 'gate_recovered'")[
            "payload_json"
        ]
    )
    assert ev["interrupted_results"] == 2
    # the complete pass follows the event: every in-scope predicate once more, the two again
    assert n_results(p) > 4
    twice = p.store.scalar(
        "SELECT COUNT(*) FROM (SELECT predicate_id FROM predicate_results WHERE phase = 'pre' "
        "AND action_id IN (SELECT action_id FROM actions WHERE step_id = ?) "
        "GROUP BY predicate_id HAVING COUNT(*) = 2)",
        (STEP,),
    )
    assert twice == 2
    assert "gate_recovered" in events(p) and events(p).index("gate_recovered") < events(p).index(
        "status:held"
    )


def test_interrupted_after_the_holds_opened(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    real = steps_mod.transition

    def no_settle(store, run_id, step_id, to, **kw):  # type: ignore[no-untyped-def]
        if to == StepStatus.HELD:
            raise Interrupted
        return real(store, run_id, step_id, to, **kw)

    with monkeypatch.context() as m:
        m.setattr(steps_mod, "transition", no_settle)
        with pytest.raises(Interrupted):
            flagging_proposal(p)
    assert status(p) == "proposed"
    before = open_hold_ids(p)
    assert before  # the hold exists, the step never reached `held`
    r = cli(p, "propose", STEP, "--json")  # bare: finish the interrupted gate
    assert r.exit_code == 10, r.output
    assert status(p) == "held"
    assert open_hold_ids(p) == before  # the same hold, not a second one
    assert p.store.scalar("SELECT COUNT(*) FROM holds WHERE step_id = ?", (STEP,)) == len(before)
    assert p.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id = ?", (STEP,)) == 1
    # nothing executed before admission
    assert p.store.scalar("SELECT COUNT(*) FROM executions") == 0


def test_recovery_of_a_clean_proposal_runs_it(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")

    def boom(*a: object, **k: object) -> None:
        raise Interrupted

    with monkeypatch.context() as m:
        m.setattr(steps_mod, "evaluate", boom)
        assert cli(p, "run", env=MOCK).exit_code != 0
    assert status(p) == "proposed"
    r = cli(p, "run", "--until", STEP, "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    assert status(p) == "completed"
    assert p.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id = ?", (STEP,)) == 1


def test_withdraw_a_held_proposal(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "propose", STEP, "--set", "min_value=12", "--reason", "twelve", "--new", "--json")
    assert r.exit_code == 10, r.output
    held = open_hold_ids(p)
    assert status(p) == "held" and held
    # a held step still cannot be proposed over
    assert cli(p, "propose", STEP, "--set", "min_value=9", "--reason", "nine").exit_code != 0
    r = cli(p, "propose", STEP, "--withdraw", "--set", "min_value=9")
    assert r.exit_code != 0 and status(p) == "held"
    r = cli(p, "propose", STEP, "--withdraw", "--reason", "the reason misquoted", "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["status"] == "withdrawn" and out["withdrawn"]["holds"] == held
    assert status(p) == "withdrawn" and open_hold_ids(p) == []
    rows = p.store.all("SELECT * FROM holds WHERE step_id = ?", (STEP,))
    assert {r["resolved_via"] for r in rows} == {"withdrawn"}
    assert all(r["resolved_by_review"] is None for r in rows)
    assert p.store.scalar("SELECT COUNT(*) FROM reviews") == 1  # the confirm hold's, no other
    ev = events(p)
    assert (
        ev.index("proposal_withdrawn") < ev.index("hold_withdrawn") < ev.index("status:withdrawn")
    )
    # a withdrawn hold takes no verdict
    assert (
        cli(p, "review", "--hold", held[0], "--verdict", "accept", "--reason", "x").exit_code != 0
    )
    # the next proposal is attempt 2; both actions are in the trace
    r = cli(p, "propose", STEP, "--set", "min_value=9", "--reason", "nine", "--json")
    assert r.exit_code == 10, r.output
    attempts = [
        r["attempt"]
        for r in p.store.all(
            "SELECT attempt FROM actions WHERE step_id = ? ORDER BY rowid", (STEP,)
        )
    ]
    assert attempts == [1, 2] and status(p) == "held"
    assert open_hold_ids(p) and set(open_hold_ids(p)).isdisjoint(held)


def test_run_after_a_withdrawal_proposes_the_step_again(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "propose", STEP, "--set", "min_value=12", "--reason", "twelve", "--new", "--json")
    assert r.exit_code == 10, r.output
    assert cli(p, "propose", STEP, "--withdraw").exit_code == 0
    nx = json.loads(cli(p, "next", "--json").output)
    assert nx["kind"] == "runnable" and nx["step_id"] == STEP
    # the run is not blocked or held by a withdrawn step; `run` proposes it at its defaults
    assert p.store.scalar("SELECT status FROM runs ORDER BY rowid DESC LIMIT 1") == "running"
    r = cli(p, "run", "--until", STEP, "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    assert status(p) == "completed"


def test_withdraw_refuses_what_is_not_a_held_proposal(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    rc = open_or_resume(p, new=True)
    with pytest.raises(RefusedError, match="no held proposal"):
        withdraw_proposal(rc, STEP)
    # a judgment held on its items after it ran is a person's to decide
    split = {
        **MOCK,
        "STRINGENCY_MOCK_FIXTURE": MOCK["STRINGENCY_MOCK_FIXTURE"].replace("unanimous", "split"),
    }
    assert cli(p, "run", env=split).exit_code == 10
    rc = open_or_resume(p)
    assert str(p.store.scalar("SELECT status FROM steps WHERE step_id = '03_label'")) == "held"
    with pytest.raises(RefusedError, match="held on what it produced"):
        withdraw_proposal(rc, "03_label")
    assert cli(p, "propose", "03_label", "--withdraw").exit_code != 0
