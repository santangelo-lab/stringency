"""Lane A item 5, the smaller fixes (2026-09-23): submit --failed, abandoned steps, withdrawn
holds, one hold for invalid replicates, env-manifest lint, extractor env, echo width."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency.exit_codes import ConfigError
from stringency.machine import EDGES, StepStatus
from stringency.operator_exec.submit import submit_failed
from stringency.operator_exec.tickets import job_spec
from stringency.project import Project
from stringency.review import queue, record_review
from stringency.runs import RunContext, abandon, open_or_resume
from stringency.steps import propose
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def test_edges_include_abandoned() -> None:
    assert len(EDGES) == 28
    assert (StepStatus.AWAITING_EXECUTION, StepStatus.ABANDONED) in EDGES


def test_submit_failed_closes_the_attempt_and_the_next_one_opens(
    confirmed_project: Project,
) -> None:
    rc = open_or_resume(confirmed_project)
    prop = propose(rc, "01_filter")
    assert prop.status == StepStatus.AWAITING_EXECUTION
    with pytest.raises(ConfigError, match="non-zero"):
        submit_failed(rc, prop.ticket or "", reason="oom", exit_code=0)
    out = submit_failed(rc, prop.ticket or "", reason="killed by the memory cap", exit_code=137)
    assert out.status == StepStatus.FAILED
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["exit_code"] == 137 and ex["runner"] == "operator"
    assert "killed by the memory cap" in ex["observed_params_json"] or "killed" in json.dumps(
        dict(ex)
    )
    ev = rc.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='01_filter' "
        "AND event='status:failed' ORDER BY seq DESC LIMIT 1",
        (rc.run_id,),
    ) or rc.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='01_filter' "
        "AND payload_json LIKE '%reported_by%' ORDER BY seq DESC LIMIT 1",
        (rc.run_id,),
    )
    assert ev is not None and json.loads(ev["payload_json"])["reported_by"] == "operator"
    prop2 = propose(rc, "01_filter")
    assert prop2.action.attempt == 2 and prop2.status == StepStatus.AWAITING_EXECUTION
    # through the CLI
    r = cli(confirmed_project, "submit", prop2.ticket or "", "--failed", "--reason", "disk full")
    assert r.exit_code == 13, r.output  # next reports the failed step
    assert "reported failed by the operator" in r.output
    _ = job_spec


def test_abandon_closes_open_steps_and_withdraws_holds(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    run_id = p.store.one("SELECT run_id FROM runs ORDER BY rowid DESC LIMIT 1")["run_id"]
    assert len(queue(p)) == 1
    abandon(p, run_id, "wrong fixture")
    assert (
        p.store.scalar("SELECT status FROM steps WHERE run_id=? AND step_id='03_label'", (run_id,))
        == "abandoned"
    )
    assert p.store.scalar("SELECT status FROM runs WHERE run_id=?", (run_id,)) == "abandoned"
    h = p.store.one("SELECT * FROM holds WHERE run_id=? AND step_id='03_label'", (run_id,))
    assert h["resolved_via"] == "withdrawn" and h["resolved_by_review"] is None
    assert queue(p) == []
    with pytest.raises(Exception, match="withdrawn"):
        record_review(p, h["hold_id"], "accept", replicate=1)


def test_reject_on_one_hold_withdraws_its_siblings(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split_two.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    holds = queue(p)
    assert [h["item_id"] for h in holds] == ["A", "B"]
    res = record_review(p, holds[0]["hold_id"], "reject", reason="the whole batch is off")
    assert res.step_status == "rejected"
    assert queue(p) == []  # attempt 1's other hold is withdrawn, not waiting
    other = p.store.one("SELECT * FROM holds WHERE hold_id=?", (holds[1]["hold_id"],))
    assert other["resolved_via"] == "withdrawn"
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 12, r.output  # rejected: attempt 2 is `propose 03_label`


def test_invalid_replicates_open_one_hold_for_the_step(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "invalid_third.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 12, r.output  # replicates_below_min blocks with two valid of three
    run_id = p.store.one("SELECT run_id FROM runs ORDER BY rowid DESC LIMIT 1")["run_id"]
    holds = p.store.all("SELECT * FROM holds WHERE run_id=? AND step_id='03_label'", (run_id,))
    assert (
        len(holds) == 1 and holds[0]["item_id"] is None and holds[0]["kind"] == "run_disagreement"
    )
    assert json.loads(holds[0]["context_json"])["invalid_replicates"] == [3]
    assert holds[0]["resolved_via"] == "withdrawn"  # the block closed the attempt
    assert queue(p) == []
    cons = p.store.all("SELECT * FROM consensus WHERE run_id=? AND step_id='03_label'", (run_id,))
    assert len(cons) == 3 and all(c["source"] == "agreed" for c in cons)


def test_lint_env_manifest(tmp_path: Path, method_repo: object) -> None:
    import shutil

    import yaml

    from stringency.lint import lint_path

    src = Path(getattr(method_repo, "path", None) or method_repo.root)
    repo = tmp_path / "m"
    shutil.copytree(src, repo)
    assert lint_path(repo).ok
    mf = repo / "envs" / "manifest.yml"
    doc = yaml.safe_load(mf.read_text())
    doc["environments"]["toy-py"]["sha256"] = "nothex"
    mf.write_text(yaml.safe_dump(doc))
    rep = lint_path(repo)
    assert any("sha256" in e for e in rep.errors)
    doc["environments"] = {"other": {"lock": "x"}}
    mf.write_text(yaml.safe_dump(doc))
    rep = lint_path(repo)
    assert any("module env toy-py has no entry" in e for e in rep.errors)
    mf.write_text("environments: [1, 2]\n")
    assert any("environments" in e for e in lint_path(repo).errors)


def test_extractor_env_follows_the_consuming_step(project: Project) -> None:
    assert project.env_for_input("groups") == "toy-py"
    assert project.env_for_input("nothing-binds-this") == project.env_names()[0]


def test_echo_lines_fit_in_100_columns(project: Project) -> None:
    for line in project.echo_path().read_text().splitlines():
        assert len(line) <= 100 or line.startswith(" "), line


def test_run_context_type_is_importable() -> None:
    assert RunContext is not None
