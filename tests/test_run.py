"""M7: the run loop, exit codes, next/status JSON schemas, every 7.1 transition."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stringency import git
from stringency.cli.app import app
from stringency.machine import EDGES, IllegalTransition, StepStatus, transition
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.schemas import validate
from tests.conftest import InitFn, accept_hold
from tests.test_steps import play_agent

HARNESS = Path(__file__).parent / "fixtures" / "harness"
SCHEMAS = Path(__file__).parent / "fixtures" / "schemas"
runner = CliRunner()


def cli(project: Project, *args: str, env: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    cwd = os.getcwd()
    os.chdir(project.root)
    try:
        return runner.invoke(app, list(args), env=env)
    finally:
        os.chdir(cwd)


def confirmed(make_project: InitFn, **kw: object) -> Project:
    p = make_project(**kw)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    return p


MOCK = {
    "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "unanimous.yml"),
    "STRINGENCY_MOCK_FAMILY": "direct",
}
MOCK_DISPATCH = {**MOCK, "STRINGENCY_MOCK_FAMILY": "dispatch"}


def test_run_before_confirm_exits_10_naming_owner(project: Project) -> None:
    r = cli(project, "run")
    assert r.exit_code == 10, r.output
    assert "waits on owner tester" in (r.output + str(r.stderr))


def test_all_engine_pipeline_completes_through_direct_mock(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["kind"] == "completed" and out["run_status"] == "completed"
    assert (p.root / "runs" / out["run_id"] / "summary.md").exists()
    steps = p.store.all("SELECT status FROM steps WHERE run_id=?", (out["run_id"],))
    assert all(s["status"] == "completed" for s in steps) and len(steps) == 5
    # a second run opens a new run since the last is closed
    r2 = cli(p, "run", "--json", env=MOCK)
    assert r2.exit_code == 0 and json.loads(r2.output)["run_id"] != out["run_id"]


def test_operator_pipeline_with_dispatch_mock(make_project: InitFn) -> None:
    """01 and 02 operator-run (exit 21 each), 03 judgment dispatched (exit 20), 04 engine-run,
    05 operator-run (exit 21), then completion (exit 0)."""
    p = confirmed(make_project)

    def run_json(expect: int) -> dict:
        r = cli(p, "run", "--json", env=MOCK_DISPATCH)
        assert r.exit_code == expect, r.output
        return json.loads(r.output)

    def submit_json(spec: dict, names: list[str]) -> dict:
        outputs, log = play_agent(spec)
        args = ["submit", spec["ticket"]]
        for n in names:
            args += ["--outputs", f"{n}={outputs[n]}"]
        args += ["--evidence", str(log), "--json"]
        r = cli(p, *args, env=MOCK_DISPATCH)
        assert r.exit_code == 0, r.output
        return json.loads(r.output)

    nx = run_json(21)
    assert nx["kind"] == "awaiting_execution" and nx["step_id"] == "01_filter"
    spec = nx["job_spec"]
    # running again without submitting repeats the ticket and does not advance
    assert run_json(21)["job_spec"]["ticket"] == spec["ticket"]
    assert submit_json(spec, ["object"])["status"] == "completed"

    nx = run_json(21)
    assert nx["step_id"] == "02_summarize"
    submit_json(nx["job_spec"], ["table"])

    nx = run_json(20)
    assert nx["kind"] == "dispatching" and nx["requests"] == 3
    ddir = Path(nx["dispatch_dir"])
    assert len(list(ddir.glob("req_*.json"))) == 3
    assert p.store.scalar("SELECT COUNT(*) FROM invocations") == 0

    # the mock plays the subagents on collect; 04_compare is engine-run; 05_report awaits execution
    nx = run_json(21)
    assert nx["step_id"] == "05_report"
    assert p.store.scalar("SELECT COUNT(*) FROM invocations") == 3
    assert p.store.scalar("SELECT status FROM steps WHERE step_id='04_compare'") == "completed"
    sj = submit_json(nx["job_spec"], ["report", "group_labels"])
    assert sj["status"] == "completed" and sj["next"]["kind"] == "completed"
    run_id = sj["run_id"]
    assert p.store.scalar("SELECT status FROM runs WHERE run_id=?", (run_id,)) == "completed"
    assert (p.root / "runs" / run_id / "summary.md").exists()
    # the run is closed, so the next `run` opens a fresh one and stops at the first ticket
    nx = run_json(21)
    assert nx["run_id"] != run_id
    ex = {
        r["step_id"]: r["runner"]
        for r in p.store.all(
            "SELECT a.step_id, e.runner FROM executions e JOIN actions a ON a.action_id = e.action_id"
        )
    }
    assert ex == {
        "01_filter": "operator",
        "02_summarize": "operator",
        "03_label": "engine",
        "04_compare": "engine",
        "05_report": "operator",
    }


def test_next_json_matches_schema_and_reports_range(make_project: InitFn) -> None:
    p = confirmed(make_project)
    cli(p, "run", env=MOCK)  # opens the run and stops at the ticket for 01_filter
    r = cli(p, "next", "--json")
    assert r.exit_code == 0
    nx = json.loads(r.output)
    assert validate(nx, json.loads((SCHEMAS / "next.json").read_text())) == []
    assert nx["kind"] == "awaiting_execution"
    # a fresh project: the runnable plan for 01_filter
    p2 = confirmed(make_project, pipeline="toy-engine", execution="engine")
    rc = open_or_resume(p2)
    from stringency.runloop import next_step

    nx2 = {**next_step(rc).to_json(), "run_id": rc.run_id}
    assert validate(nx2, json.loads((SCHEMAS / "next.json").read_text())) == []
    assert nx2["kind"] == "runnable" and nx2["plan"]["parameters"]["min_value"]["range"] == [0, 40]
    assert nx2["plan"]["parameters"]["min_value"]["decision_point"] is True


def test_held_judgment_exits_10_twice_without_reinvoking(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    assert "run_disagreement" in r.output and "stringency review" in r.output
    n = p.store.scalar("SELECT COUNT(*) FROM invocations")
    r = cli(p, "run", env=env)
    assert r.exit_code == 10
    assert p.store.scalar("SELECT COUNT(*) FROM invocations") == n
    assert p.store.scalar("SELECT status FROM steps WHERE step_id='04_compare'") == "pending"


def test_blocked_pre_gate_exits_11_and_next_names_predicate(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    pipe = p.method_root / "pipelines" / "toy-engine.yml"
    pipe.write_text(
        pipe.read_text().replace("correction: {default: bh,", "correction: {default: none,")
    )
    git.commit_all(p.method_root, "no correction")
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 11, r.output
    r = cli(p, "next", "--json")
    nx = json.loads(r.output)
    assert nx["kind"] == "blocked" and nx["step_id"] == "04_compare"
    assert [x["predicate_id"] for x in nx["predicates"]] == ["toy.no_correction"]
    r = cli(p, "status", "--json")
    assert json.loads(r.output)["run"]["status"] == "blocked"


def test_dirty_tree_exits_14_and_allow_dirty_records_reason(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    pipe = p.method_root / "pipelines" / "toy-engine.yml"
    pipe.write_text(pipe.read_text() + "\n# edited without commit\n")
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 14, r.output
    assert p.store.scalar("SELECT COUNT(*) FROM runs") == 0
    r = cli(p, "run", "--allow-dirty", "deliberately testing dirty runs", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run = p.store.one("SELECT * FROM runs")
    assert run["git_dirty"] == 1 and run["allow_dirty_reason"] == "deliberately testing dirty runs"


def test_status_json_schema_and_holds(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    cli(p, "run", env={**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")})
    r = cli(p, "status", "--json")
    st = json.loads(r.output)
    assert validate(st, json.loads((SCHEMAS / "status.json").read_text())) == []
    assert st["run"]["status"] == "held" and st["holds"][0]["who"] == "tester"
    r = cli(p, "status")
    assert "waits on reviewer tester" in r.output


def test_abandon(make_project: InitFn) -> None:
    p = confirmed(make_project)
    cli(p, "run", env=MOCK)
    run_id = p.store.scalar("SELECT run_id FROM runs")
    r = cli(p, "abandon", "--run", run_id, "--reason", "wrong threshold")
    assert r.exit_code == 0
    assert p.store.scalar("SELECT status FROM runs") == "abandoned"
    r = cli(p, "abandon", "--run", run_id, "--reason", "again")
    assert r.exit_code == 16


def test_every_transition_in_7_1(project: Project) -> None:
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
    for i, (frm, to) in enumerate(sorted(EDGES)):
        sid = f"s{i}"
        store.create_step(
            {
                "run_id": run_id,
                "step_id": sid,
                "module": "m",
                "module_version": "1",
                "operation": "op",
                "status": str(frm),
            }
        )
        transition(store, run_id, sid, to)
        assert store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (run_id, sid)
        ) == str(to)
        ev = store.one(
            "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? ORDER BY seq DESC LIMIT 1",
            (run_id, sid),
        )
        assert json.loads(ev["payload_json"])["from"] == str(frm)
    # and a forbidden edge raises without writing
    store.create_step(
        {
            "run_id": run_id,
            "step_id": "bad",
            "module": "m",
            "module_version": "1",
            "operation": "op",
        }
    )
    with pytest.raises(IllegalTransition):
        transition(store, run_id, "bad", StepStatus.COMPLETED)
    assert store.scalar("SELECT status FROM steps WHERE step_id='bad'") == "pending"
    assert len(EDGES) == 21
