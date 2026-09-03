"""M8: review verdicts, binding and rebind, via detection, --attest, override rates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stringency import git
from stringency.exit_codes import ConfigError, RefusedError
from stringency.project import Project
from stringency.review import queue, record_review, show
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def held_project(
    make_project: InitFn, fixture: str = "split.yml", **kw: object
) -> tuple[Project, dict[str, str]]:
    p = make_project(pipeline="toy-engine", execution="engine", **kw)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / fixture)}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    return p, env


def test_queue_and_show(make_project: InitFn) -> None:
    p, _ = held_project(make_project)
    holds = queue(p)
    assert len(holds) == 1 and holds[0]["kind"] == "run_disagreement"
    view = show(p, holds[0])
    assert "evidence row for item A" in view.text and "mean_value" in view.text
    assert "1: abundant (high)" in view.text and "3: uniform (medium)" in view.text
    r = cli(p, "review")
    assert r.exit_code == 0 and "run_disagreement" in r.output


def test_accept_item_hold_at_tty_and_run_continues(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    h = queue(p)[0]
    res = record_review(p, h["hold_id"], "accept", replicate=1)
    assert res.via == "tty" and res.step_status == "completed"
    cons = p.store.one("SELECT * FROM consensus WHERE item_id='A'")
    assert (
        cons["source"] == "accepted"
        and cons["label"] == "abundant"
        and cons["review_id"] == res.review_id
    )
    rev = p.store.one("SELECT * FROM reviews WHERE review_id=?", (res.review_id,))
    assert rev["bound_module_version"] == "label-groups@0.1.0" and rev[
        "bound_input_digest"
    ].startswith("blake3:")
    assert rev["chosen_replicate"] == 1 and rev["reviewer"] == "tester"
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["run_status"] == "completed"


def test_accept_item_needs_replicate_when_calls_differ(make_project: InitFn) -> None:
    p, _ = held_project(make_project)
    with pytest.raises(ConfigError, match="--replicate"):
        record_review(p, queue(p)[0]["hold_id"], "accept")


def test_override_out_of_vocabulary_refused(make_project: InitFn) -> None:
    p, _ = held_project(make_project)
    h = queue(p)[0]
    with pytest.raises(ConfigError, match="not in vocabulary"):
        record_review(p, h["hold_id"], "override", correction={"label": "plentiful"}, reason="typo")
    assert p.store.scalar("SELECT COUNT(*) FROM reviews") == 1  # only the confirm accept
    res = record_review(
        p, h["hold_id"], "override", correction={"label": "uniform"}, reason="sd is small"
    )
    cons = p.store.one("SELECT * FROM consensus WHERE item_id='A'")
    assert cons["source"] == "override" and cons["label"] == "uniform"
    assert (
        p.root / "prov" / "justifications" / f"{res.review_id}.md"
    ).read_text().strip() == "sd is small"


def test_reject_closes_attempt_and_next_reports(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    h = queue(p)[0]
    res = record_review(p, h["hold_id"], "reject", reason="the split is real; revise the prompt")
    assert res.step_status == "rejected"
    r = cli(p, "next", "--json")
    nx = json.loads(r.output)
    assert nx["kind"] == "rejected" and nx["step_id"] == "03_label"
    assert (
        p.store.scalar(
            "SELECT COUNT(*) FROM artifacts WHERE step_id='03_label' AND status='rejected'"
        )
        == 2
    )
    r = cli(p, "run", env=env)
    assert r.exit_code == 12


def test_defer_keeps_hold(make_project: InitFn) -> None:
    p, _ = held_project(make_project)
    h = queue(p)[0]
    res = record_review(p, h["hold_id"], "defer")
    assert res.step_status is None
    assert len(queue(p)) == 1
    assert (
        p.store.scalar("SELECT verdict FROM reviews WHERE review_id=?", (res.review_id,)) == "defer"
    )


def test_rebind_auto_resolves_identical_rerun(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    h = queue(p)[0]
    first = record_review(p, h["hold_id"], "accept", replicate=1)
    cli(p, "run", env=env)  # completes the run
    n_reviews = p.store.scalar("SELECT COUNT(*) FROM reviews")
    # a second run with the same method: the same item disagreement rebinds to the prior accept
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    run2 = json.loads(r.output)["run_id"]
    h2 = p.store.one("SELECT * FROM holds WHERE run_id=? AND step_id='03_label'", (run2,))
    assert h2["resolved_via"] == "rebind" and h2["resolved_by_review"] == first.review_id
    assert (
        p.store.scalar("SELECT COUNT(*) FROM reviews") == n_reviews
    )  # no new prompt to the reviewer
    cons = p.store.one("SELECT * FROM consensus WHERE run_id=? AND item_id='A'", (run2,))
    assert cons["source"] == "accepted" and cons["label"] == "abundant"


def test_bumping_module_version_defeats_rebind(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    record_review(p, queue(p)[0]["hold_id"], "accept", replicate=1)
    cli(p, "run", env=env)
    for f in ("module.yml",):
        path = p.method_root / "modules" / "label-groups" / f
        path.write_text(path.read_text().replace("version: 0.1.0", "version: 0.1.1"))
    pipe = p.method_root / "pipelines" / "toy-engine.yml"
    pipe.write_text(pipe.read_text().replace("label-groups@0.1.0", "label-groups@0.1.1"))
    git.commit_all(p.method_root, "prompt revision: bump label-groups")
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    h2 = queue(p)[0]
    assert h2["bound_module_version"] == "label-groups@0.1.1" and h2["resolved_by_review"] is None


def test_attest_refused_under_strict_and_recorded_under_standard(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: None)
    p, _ = held_project(make_project, profile="strict")
    h = queue(p)[0]
    with pytest.raises(RefusedError, match="relayed"):
        record_review(p, h["hold_id"], "accept", replicate=1, attest=True)
    with pytest.raises(RefusedError, match="terminal"):
        record_review(p, h["hold_id"], "accept", replicate=1)
    r = cli(
        p, "review", "--verdict", "accept", "--hold", h["hold_id"], "--replicate", "1", "--attest"
    )
    assert r.exit_code == 16
    p2, _ = held_project(make_project, profile="standard")
    h2 = queue(p2)[0]
    res = record_review(p2, h2["hold_id"], "accept", replicate=1, attest=True)
    assert res.via == "relayed"
    assert (
        p2.store.scalar("SELECT via FROM reviews WHERE review_id=?", (res.review_id,)) == "relayed"
    )


def test_reviewer_identity_checked(make_project: InitFn, monkeypatch: pytest.MonkeyPatch) -> None:
    p, _ = held_project(make_project)
    monkeypatch.setattr("stringency.review.current_user", lambda: "someone_else")
    with pytest.raises(RefusedError, match="waits on reviewer"):
        record_review(p, queue(p)[0]["hold_id"], "accept", replicate=1)


def test_flag_hold_pre_phase_accept_makes_admissible(make_project: InitFn) -> None:
    # a pre-gate flag: toy.filter_after_summary fires when filter follows summarize; build that via a fork-like
    # pipeline is heavy, so use the strict-profile env_unverified post flag instead (operator runner)
    p = make_project(profile="strict")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    from stringency.operator_exec.submit import submit
    from stringency.operator_exec.tickets import job_spec
    from stringency.runs import open_or_resume
    from stringency.steps import propose
    from tests.test_steps import play_agent

    rc = open_or_resume(p)
    prop = propose(rc, "01_filter")
    outputs, log = play_agent(job_spec(prop, None))
    out = submit(rc, prop.ticket or "", outputs, [log])
    assert out.status == "held"
    h = queue(p)[0]
    assert h["kind"] == "flag"
    view = show(p, h)
    assert "repro.env_unverified" in view.text
    with pytest.raises(ConfigError, match="needs --reason"):
        record_review(p, h["hold_id"], "accept")
    res = record_review(p, h["hold_id"], "accept", reason="toy scripts have no container")
    assert res.step_status == "completed"


def test_status_overrides_rate(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    record_review(
        p, queue(p)[0]["hold_id"], "override", correction={"label": "uniform"}, reason="x"
    )
    r = cli(p, "status", "--overrides", "--json")
    rates = json.loads(r.output)["modules"]
    assert rates == [
        {
            "module": "label-groups@0.1.0",
            "reviews": 1,
            "accept": 0,
            "override": 1,
            "reject": 0,
            "override_rate": 1.0,
            "rejection_rate": 0.0,
        }
    ]
    r = cli(p, "status", "--overrides", "--module", "label-groups")
    assert "override 1 (100%)" in r.output


def test_confirm_hold_via_review_cli(project: Project) -> None:
    h = project.confirm_hold()
    r = cli(project, "review", "--show")
    assert "Echo-back" in r.output
    r = cli(
        project,
        "review",
        "--verdict",
        "accept",
        "--hold",
        h["hold_id"],
        "--reason",
        "matches the experiment",
    )
    assert r.exit_code == 0, r.output
    assert project.confirm_status() == "accepted"
    _ = Path
