"""L11 (the owner, 2026-10-07): a correction fork should carry its parent's outputs for
comparison. A pipeline step may bind `$parent.<step>.<output>`: in a forked run it resolves to
that output of the run the fork was opened from; in any other run to nothing, so the input is
optional on its module (lint)."""

from __future__ import annotations

import json

import pytest

from stringency import git
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.pipelines import Ref, load_pipeline
from stringency.project import Project
from tests.conftest import InitFn
from tests.test_run import MOCK, cli, confirmed

REPORT_INPUTS = (
    "inputs: {comparison: $steps.04_compare.comparison_table, labels: $steps.03_label.consensus}"
)
PARENT_INPUTS = (
    "inputs: {comparison: $steps.04_compare.comparison_table, labels: $steps.03_label.consensus, "
    "parent_comparison: $parent.04_compare.comparison_table}"
)
LABELS_LINE = "  labels: {type: consensus, format: json, hash: true}\n"


def with_parent_input(p: Project, *, optional: bool = True) -> None:
    """The toy report takes the parent run's comparison table as an optional input; commit."""
    root = p.method_root
    pipe = root / "pipelines" / "toy-engine.yml"
    text = pipe.read_text()
    assert REPORT_INPUTS in text
    pipe.write_text(text.replace(REPORT_INPUTS, PARENT_INPUTS))
    mod = root / "modules" / "toy-report" / "module.yml"
    opt = ", optional: true" if optional else ""
    mod.write_text(
        mod.read_text().replace(
            LABELS_LINE,
            LABELS_LINE + f"  parent_comparison: {{type: table, format: tsv, hash: true{opt}}}\n",
        )
    )
    git.commit_all(root, "the report reads the parent's comparison")


def run_json(p: Project) -> dict:
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    return json.loads(r.output)


def report_inputs(p: Project, run_id: str) -> dict[str, str]:
    return dict(
        json.loads(
            p.store.scalar(
                "SELECT inputs_json FROM actions WHERE run_id=? AND step_id='05_report'",
                (run_id,),
            )
        )
    )


def comparison_hash(p: Project, run_id: str) -> str:
    return str(
        p.store.scalar(
            "SELECT hash FROM artifacts WHERE run_id=? AND step_id='04_compare' AND "
            "name='comparison_table' AND status='produced' ORDER BY rowid DESC LIMIT 1",
            (run_id,),
        )
    )


def test_a_fork_binds_its_parents_output_and_a_first_run_binds_nothing(
    make_project: InitFn,
) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    with_parent_input(p)
    parent = run_json(p)["run_id"]
    # not a fork: the input resolves to nothing and the optional input is left out
    assert set(report_inputs(p, parent)) == {"comparison", "labels"}
    r = cli(
        p,
        "fork",
        "--from",
        parent,
        "--at",
        "04_compare",
        "--set",
        "04_compare.correction=bonferroni",
        "--reason",
        "compare corrections",
        "--json",
    )
    assert r.exit_code == 0, r.output
    child = json.loads(r.output)["run_id"]
    out = run_json(p)
    assert out["run_id"] == child and out["run_status"] == "completed"
    bound = report_inputs(p, child)
    assert set(bound) == {"comparison", "labels", "parent_comparison"}
    # the parent's table, not the child's own, which the fork re-ran with another correction
    assert bound["parent_comparison"].removeprefix("blake3:") == comparison_hash(p, parent)
    assert bound["comparison"].removeprefix("blake3:") == comparison_hash(p, child)
    assert comparison_hash(p, parent) != comparison_hash(p, child)
    # a fork of the fork binds its own parent, the fork, whose table the grandchild compares
    r = cli(
        p,
        "fork",
        "--from",
        child,
        "--at",
        "05_report",
        "--reason",
        "the report again",
        "--json",
    )
    assert r.exit_code == 0, r.output
    grandchild = json.loads(r.output)["run_id"]
    run_json(p)
    assert report_inputs(p, grandchild)["parent_comparison"].removeprefix(
        "blake3:"
    ) == comparison_hash(p, child)


def test_lint_refuses_a_required_parent_input_and_an_unknown_output(
    make_project: InitFn,
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    with_parent_input(p, optional=False)
    errors = "\n".join(str(e) for e in lint_path(p.method_root).errors)
    assert "binds the parent run's output" in errors and "must be optional" in errors
    pipe = p.method_root / "pipelines" / "toy-engine.yml"
    pipe.write_text(
        pipe.read_text().replace(
            "$parent.04_compare.comparison_table", "$parent.04_compare.no_such_output"
        )
    )
    errors = "\n".join(str(e) for e in lint_path(p.method_root).errors)
    assert "$parent.04_compare.no_such_output, which does not exist" in errors
    pipe.write_text(
        pipe.read_text().replace("$parent.04_compare.no_such_output", "$parent.09_none.table")
    )
    with pytest.raises((ConfigError, ValueError), match="unknown step 09_none of the parent run"):
        load_pipeline(pipe)


def test_the_reference_form() -> None:
    r = Ref.parse("$parent.04_cluster.batch_evidence")
    assert (r.kind, r.name, r.output, str(r)) == (
        "parent",
        "04_cluster",
        "batch_evidence",
        "$parent.04_cluster.batch_evidence",
    )
    with pytest.raises(ConfigError, match=r"\$parent needs <id>.<output>"):
        Ref.parse("$parent.04_cluster")
    with pytest.raises(ConfigError, match="a glob binds"):
        Ref.parse("$parent.04_*.x")
