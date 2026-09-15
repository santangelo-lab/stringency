"""M9: deliver, coverage report, methods paragraph."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from stringency.deliver import deliver
from stringency.exit_codes import ConfigError, HeldError, RefusedError
from stringency.project import Project
from stringency.review import queue, record_review
from stringency.runs import load_run
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli

GOLDEN = Path(__file__).parent / "golden"


def completed_project(make_project: InitFn, fixture: str = "unanimous.yml") -> tuple[Project, str]:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / fixture)}
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    return p, json.loads(r.output)["run_id"]


def normalise(text: str) -> str:
    text = re.sub(r"[0-9A-HJKMNP-TV-Z]{26}", "<ULID>", text)
    text = re.sub(r"\b[0-9a-f]{64}\b", "<HASH64>", text)
    text = re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", text)
    text = re.sub(r"commit [0-9a-f]{7}", "commit <SHA7>", text)
    text = re.sub(r"\b[0-9a-f]{12}\b", "<HASH12>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", "<DATE>", text)
    return text


def test_deliver_writes_reports_and_index(
    make_project: InitFn, request: pytest.FixtureRequest
) -> None:
    p, run_id = completed_project(make_project)
    rc = load_run(p, run_id)
    d = deliver(rc)
    assert (
        (d.path / "coverage.md").exists()
        and (d.path / "methods.md").exists()
        and (d.path / "index.json").exists()
    )
    index = json.loads((d.path / "index.json").read_text())
    names = {(f["step_id"], f["output"]) for f in index["files"]}
    assert names == {
        ("05_report", "report"),
        ("05_report", "group_labels"),
        ("04_compare", "comparison_table"),
        ("03_label", "consensus"),
    } - {("03_label", "consensus")}
    for f in index["files"]:
        assert (d.path / f["file"]).exists() and (d.path / f["sidecar"]).exists()
    assert p.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 1
    assert (
        p.store.scalar("SELECT COUNT(*) FROM artifacts WHERE run_id=? AND is_final=1", (run_id,))
        == 3
    )
    # uncovered decision points computed by hand from the toy manifests: filter_rows.min_value is covered by
    # toy.filter_after_summary (filter_rows.*); compare_groups.replicate_unit and .correction by the toy predicates
    cov = json.loads((d.path / "coverage.json").read_text())
    assert cov["gate"]["uncovered_decision_points"] == []
    assert cov["gate"]["ungated_steps"] == []
    assert cov["steps"]["completed"] == 5
    assert cov["execution"]["engine_run"] == 5 and cov["execution"]["operator_run"] == 0
    assert cov["reproducibility"]["invocations"]["via"] == ["direct"]
    assert d.coverage.rstrip().endswith("not checked: anything not listed above")
    # methods paragraph against the golden file
    golden = GOLDEN / "methods_toy_engine.md"
    got = normalise(d.methods)
    if request.config.getoption("--update-golden"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(got)
    assert got == golden.read_text()
    # summary.md (design 12.1 amendment): engine-rendered, against its golden
    assert index["summary"]["file"] == "summary.md"
    summary = (d.path / "summary.md").read_text()
    assert summary == d.summary
    golden_s = GOLDEN / "summary_toy_engine.md"
    got_s = normalise(summary)
    if request.config.getoption("--update-golden"):
        golden_s.write_text(got_s)
    assert got_s == golden_s.read_text()
    assert summary.rstrip().endswith("not checked: anything not listed above")


def test_summary_names_flags_and_changed_parameters(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(
        p, "propose", "01_filter", "--set", "min_value=12", "--reason", "test", "--json", env=env
    )
    assert r.exit_code == 0, r.output
    cli(p, "run", env=env)
    record_review(
        p, queue(p)[0]["hold_id"], "override", correction={"label": "uniform"}, reason="sd is small"
    )
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    d = deliver(load_run(p, json.loads(r.output)["run_id"]))
    assert "- Filter low-value rows (step 01_filter): min_value set to 12." in d.summary
    assert "- Compare the groups (step 04_compare): at defaults." in d.summary
    assert (
        "one in disagreement; reviews: none accepted, one corrected, none unresolved." in d.summary
    )
    assert "- toy.run_disagreement" not in d.summary  # item holds are judgments, not flags
    assert "## What was analyzed\n\n50 rows in 9 units across 3 groups (input groups)" in d.summary


def test_uncovered_decision_point_is_computed(make_project: InitFn) -> None:
    # remove the covering predicates from scope by widening the decision points of summarize (none) -> add one
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    from stringency import git

    mod = p.method_root / "modules" / "summarize-groups"
    (mod / "params.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"trim": {"type": "number", "default": 0}},
                "additionalProperties": False,
            }
        )
    )
    (mod / "module.yml").write_text(
        (mod / "module.yml").read_text().replace("decision_points: []", "decision_points: [trim]")
    )
    git.commit_all(p.method_root, "trim parameter")
    p = Project.load(p.root)  # the CLI loads the project fresh; the fixture's module index is stale
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    rc = load_run(p, json.loads(r.output)["run_id"])
    d = deliver(rc)
    assert "02_summarize.trim" in d.coverage
    cov = json.loads((d.path / "coverage.json").read_text())
    assert cov["gate"]["uncovered_decision_points"] == ["02_summarize.trim"]


def test_deliver_refuses_missing_deliverable(make_project: InitFn) -> None:
    p, run_id = completed_project(make_project)
    rc = load_run(p, run_id)
    # quarantine the comparison table so the deliverable is absent
    aid = p.store.scalar(
        "SELECT artifact_id FROM artifacts WHERE run_id=? AND name='comparison_table'", (run_id,)
    )
    p.store.set_artifact_flag(aid, "status", "rejected")
    with pytest.raises(ConfigError, match="comparison_table"):
        deliver(rc)
    r = cli(p, "deliver")
    assert r.exit_code == 15


def test_deliver_refuses_orphan(make_project: InitFn) -> None:
    p, run_id = completed_project(make_project)
    rc = load_run(p, run_id)
    art = p.store.one("SELECT * FROM artifacts WHERE run_id=? AND name='report'", (run_id,))
    Path(art["sidecar_path"]).unlink()  # a file placed by hand has no sidecar
    with pytest.raises(RefusedError, match="prov.orphan_artifact"):
        deliver(rc)


def test_deliver_on_held_run_exits_10(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    cli(p, "run", env=env)
    run_id = p.store.scalar("SELECT run_id FROM runs")
    with pytest.raises(HeldError):
        deliver(load_run(p, run_id))
    r = cli(p, "deliver")
    assert r.exit_code == 10


def test_coverage_lists_flags_and_reviews(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    cli(p, "run", env=env)
    record_review(
        p, queue(p)[0]["hold_id"], "override", correction={"label": "uniform"}, reason="sd is small"
    )
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    d = deliver(load_run(p, json.loads(r.output)["run_id"]))
    assert "1 run_disagreement" in d.coverage and "1 override" in d.coverage
    assert "were resolved by reviewer tester (0 accepted, 1 corrected)" in d.methods
