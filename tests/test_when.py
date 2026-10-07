"""L13: conditional steps (`when:`), design 3.1 and 7.1 as amended 2026-10-07.

The toy-engine pipeline with `03_label` made conditional on `01_filter.min_value`, and the report's
`labels` input made optional, so either branch completes.
"""

from __future__ import annotations

import json

import pytest

from stringency import git
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.pipelines import load_pipeline
from stringency.project import Project
from tests.conftest import InitFn
from tests.test_run import MOCK, cli, confirmed

WHEN_LINE = "    module: label-groups@0.1.1\n"


def conditional(p: Project, when: str = "{step: 01_filter, param: min_value, equals: 10}") -> None:
    """Make 03_label conditional and the report's labels optional; commit."""
    root = p.method_root
    pipe = root / "pipelines" / "toy-engine.yml"
    text = pipe.read_text()
    assert WHEN_LINE in text
    pipe.write_text(text.replace(WHEN_LINE, WHEN_LINE + f"    when: {when}\n"))
    mod = root / "modules" / "toy-report" / "module.yml"
    mod.write_text(
        mod.read_text().replace(
            "labels: {type: consensus, format: json, hash: true}",
            "labels: {type: consensus, format: json, hash: true, optional: true}",
        )
    )
    script = root / "modules" / "toy-report" / "pre.py"
    script.write_text(
        script.read_text().replace(
            'with open(job["inputs"]["labels"]) as f:\n    consensus = json.load(f)\n',
            'consensus = {}\nif "labels" in job["inputs"]:\n'
            '    with open(job["inputs"]["labels"]) as f:\n        consensus = json.load(f)\n',
        )
    )
    git.commit_all(root, "03_label conditional on min_value")


def statuses(p: Project, run_id: str) -> dict[str, str]:
    return {
        r["step_id"]: r["status"]
        for r in p.store.all("SELECT step_id, status FROM steps WHERE run_id=?", (run_id,))
    }


def run_json(p: Project, *args: str, expect: int = 0) -> dict:
    r = cli(p, "run", "--json", *args, env=MOCK)
    assert r.exit_code == expect, r.output
    return json.loads(r.output)


def test_condition_true_runs_the_step(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    conditional(p)
    out = run_json(p)
    assert out["kind"] == "completed" and out["run_status"] == "completed"
    assert "skipped_steps" not in out
    assert set(statuses(p, out["run_id"]).values()) == {"completed"}


def test_condition_false_skips_and_successor_omits_the_optional_input(
    make_project: InitFn,
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    conditional(p, "{step: 01_filter, param: min_value, not_equals: 10}")
    # stop before the conditional step: `next` reports the skip and writes nothing
    out = run_json(p, "--until", "02_summarize")
    run_id = out["run_id"]
    r = cli(p, "next", "--json")
    nx = json.loads(r.output)
    assert nx["kind"] == "runnable" and nx["step_id"] == "03_label"
    assert nx["skip"] == {
        "when": {"step": "01_filter", "param": "min_value", "not_equals": 10},
        "actual": 10,
        "reason": "skipped: min_value was 10",
    }
    assert statuses(p, run_id)["03_label"] == "pending"
    # a person cannot propose it by hand either
    r = cli(p, "propose", "03_label")
    assert r.exit_code == 16 and "min_value was 10" in str(r.stderr)
    out = run_json(p)
    assert out["kind"] == "completed" and out["run_status"] == "completed"
    assert out["skipped_steps"] == ["03_label"]
    assert out["completed_steps"] == ["04_compare", "05_report"]
    assert out["plain"].startswith(
        "Completed: Filter low-value rows, Summarize each group, Compare the groups, "
        "Write the report. Skipped: Label the groups."
    )
    st = statuses(p, run_id)
    assert st["03_label"] == "skipped" and st["05_report"] == "completed"
    ev = p.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='03_label' "
        "AND event='status:skipped'",
        (run_id,),
    )
    payload = json.loads(ev["payload_json"])
    assert payload["from"] == "pending" and payload["reason"] == "skipped: min_value was 10"
    assert p.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id='03_label'") == 0
    inputs = json.loads(
        p.store.scalar(
            "SELECT inputs_json FROM actions WHERE run_id=? AND step_id='05_report'", (run_id,)
        )
    )
    assert set(inputs) == {"comparison"}
    # the reports name the skipped step
    r = cli(p, "deliver", "--json")
    assert r.exit_code == 0, r.output
    ddir = p.root / "deliver" / run_id
    summary = (ddir / "summary.md").read_text()
    assert "- Label the groups (step 03_label): skipped: min_value was 10." in summary
    coverage = (ddir / "coverage.md").read_text()
    assert ", 1 skipped" in coverage
    assert "not evaluated: 03_label (skipped: min_value was 10)" in coverage
    methods = (ddir / "methods.md").read_text()
    assert "Label the groups (step 03_label) was not run: min_value was 10." in methods


def test_fork_flips_the_branch_and_inherits_a_skip(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    conditional(p)
    parent = run_json(p)["run_id"]
    # a fork that changes the parameter skips the step
    r = cli(
        p,
        "fork",
        "--from",
        parent,
        "--at",
        "01_filter",
        "--set",
        "01_filter.min_value=12",
        "--reason",
        "try a higher floor",
        "--json",
    )
    assert r.exit_code == 0, r.output
    child = json.loads(r.output)["run_id"]
    out = run_json(p)
    assert out["run_id"] == child and out["run_status"] == "completed"
    assert statuses(p, child)["03_label"] == "skipped"
    assert statuses(p, parent)["03_label"] == "completed"
    # a fork after the skipped step inherits it as skipped, with the parent's reason
    r = cli(
        p,
        "fork",
        "--from",
        child,
        "--at",
        "04_compare",
        "--set",
        "04_compare.correction=bonferroni",
        "--reason",
        "compare corrections",
        "--json",
    )
    assert r.exit_code == 0, r.output
    grandchild = json.loads(r.output)["run_id"]
    st = statuses(p, grandchild)
    assert st["01_filter"] == "completed" and st["03_label"] == "skipped"
    ev = p.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='03_label' "
        "AND event='status:skipped'",
        (grandchild,),
    )
    payload = json.loads(ev["payload_json"])
    assert payload["inherited_from"] == child
    assert payload["reason"] == "skipped: min_value was 12"
    out = run_json(p)
    assert out["run_id"] == grandchild and out["run_status"] == "completed"
    # forking back at the filter with the default restores the branch
    r = cli(
        p,
        "fork",
        "--from",
        grandchild,
        "--at",
        "01_filter",
        "--set",
        "01_filter.min_value=10",
        "--reason",
        "back to the default",
        "--json",
    )
    fourth = json.loads(r.output)["run_id"]
    out = run_json(p)
    assert out["run_id"] == fourth and "skipped_steps" not in out
    assert statuses(p, fourth)["03_label"] == "completed"


def test_when_on_an_inherited_reference_reads_the_parent_action(make_project: InitFn) -> None:
    """The referenced step was inherited by a fork, so its action lives in the parent run."""
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    conditional(p, "{step: 01_filter, param: min_value, not_equals: 10}")
    parent = run_json(p)["run_id"]
    r = cli(p, "fork", "--from", parent, "--at", "02_summarize", "--reason", "rerun", "--json")
    child = json.loads(r.output)["run_id"]
    run_json(p)
    assert statuses(p, child)["03_label"] == "skipped"


def test_lint_refuses_a_required_input_on_a_skippable_step(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    root = p.method_root
    pipe = root / "pipelines" / "toy-engine.yml"
    pipe.write_text(
        pipe.read_text().replace(
            WHEN_LINE, WHEN_LINE + "    when: {step: 01_filter, param: min_value, equals: 10}\n"
        )
    )
    report = lint_path(root)
    assert any(
        "step 05_report input labels binds only outputs of a conditional step (03_label)" in e
        for e in report.errors
    ), report.render()
    # an undeclared parameter is an error too
    pipe.write_text(pipe.read_text().replace("param: min_value", "param: max_value"))
    report = lint_path(root)
    assert any("when asks about max_value" in e for e in report.errors), report.render()


def test_pipeline_refuses_a_when_on_a_non_ancestor_or_with_two_conditions(
    make_project: InitFn,
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    pipe = p.method_root / "pipelines" / "toy-engine.yml"
    base = pipe.read_text()
    # 04_compare does not depend on 03_label
    pipe.write_text(
        base.replace(
            "    module: compare-groups@0.1.0\n",
            "    module: compare-groups@0.1.0\n    when: {step: 03_label, param: x, equals: 1}\n",
        )
    )
    with pytest.raises(ConfigError, match="not an ancestor"):
        load_pipeline(pipe)
    pipe.write_text(
        base.replace(
            WHEN_LINE,
            WHEN_LINE
            + "    when: {step: 01_filter, param: min_value, equals: 10, not_equals: 5}\n",
        )
    )
    with pytest.raises(ConfigError, match="exactly one of equals or not_equals"):
        load_pipeline(pipe)


def test_page_and_board_show_the_skip(make_project: InitFn) -> None:
    from stringency.board import project_entry
    from tests.test_review_serve import TOKEN, _serve, _tables, get

    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    conditional(p, "{step: 01_filter, param: min_value, not_equals: 10}")
    run_json(p)
    entry = project_entry(p.root)
    assert entry["steps_done"] == entry["steps_total"] == 5
    for base in _serve(p):
        status, body = get(f"{base}/p/0?t={TOKEN}")
        assert status == 200
        by = dict(_tables(body)[0][1:])
        assert by["Label the groups"] == "skipped: min_value was 10"
        assert by["Write the report"] == "completed"
