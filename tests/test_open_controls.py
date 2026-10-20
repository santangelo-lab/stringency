"""Open mode S4, controls for deterministic tools (spec/plans/open_mode_plan.md 2.6): a positive
control with `expect.equals` against a truth table, a negative control with `expect.count`, the
explicit `expect.completed`, a tool's control run as a one-step synthetic pipeline from a
pipeline project and from an open project, a perturbed truth failing and regressing,
`controls.current_for`, and `plot-groups` chaining on the comparison output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency.controls import current_for, load_control
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import MOCK, cli


def test_toy_tools_have_controls_and_lint_warns_without_one(method_repo: MethodRepo) -> None:
    report = lint_path(method_repo.path)
    assert report.ok, report.render()
    assert not any("labelled untested" in w for w in report.warnings)
    spec = load_control(
        method_repo.path / "modules/compare-groups/controls/positive-known-differences.yml"
    )
    assert spec.params == {"replicate_unit": "unit", "correction": "bh"}
    assert spec.expect["equals"]["columns"] == ["n_a", "n_b", "diff", "p_adj"]
    # drop the positive control of an open tool: lint warns, in the label's words
    for f in (method_repo.path / "modules/plot-groups/controls").glob("*.yml"):
        f.unlink()
    report = lint_path(method_repo.path)
    assert report.ok and any(
        "plot-groups@0.1.0: lists open with no positive control" in w for w in report.warnings
    )
    # the spec's shape is checked at load
    bad = method_repo.path / "modules/plot-groups/controls/bad.yml"
    bad.write_text(
        "control: 1\nname: bad\nkind: positive\nfixture:\n  input: {type: table, blake3: '00'}\n"
        "  truth: {path: t.tsv, key: k}\nexpect: {equals: {output: x}}\n"
    )
    with pytest.raises(ConfigError, match="equals needs output and columns"):
        load_control(bad)


def test_tool_controls_run_from_a_pipeline_project(make_project: InitFn) -> None:
    """From `toy-engine`, compare-groups is step 04, but a tool is controlled alone (one step on
    the fixture, not the fixture after the filter), so the same truth table holds from every
    project; the tool's controls score the table against the truth and the shuffled count."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "controls", "run", "--module", "compare-groups", "--allow-mock", "--json", env=MOCK)
    assert r.exit_code == 0, r.output + str(r.stderr)
    res = {x["control"]: x for x in json.loads(r.output)["results"]}
    pos, neg = res["positive-known-differences"], res["negative-shuffled-groups"]
    assert pos["passed"] and pos["metrics"]["rows_matching"] == 3 == pos["metrics"]["rows_compared"]
    assert pos["metrics"]["missing_keys"] == [] and pos["metrics"]["max_abs_diff"] <= 0.01
    assert neg["passed"] and neg["metrics"]["count"] == 0 and neg["metrics"]["rows"] == 3
    assert pos["metrics"]["env_digest"]  # the environment it ran under is in the metrics
    # the control's parameters were admitted as defaults: no hold opened for them
    assert p.store.scalar("SELECT COUNT(*) FROM holds WHERE run_id=?", (pos["run_id"],)) == 0
    action = p.store.one(
        "SELECT * FROM actions WHERE run_id=? AND step_id='01_compare-groups'", (pos["run_id"],)
    )
    assert json.loads(action["params_json"]) == {"replicate_unit": "unit", "correction": "bh"}
    # plot-groups is in no pipeline step and lists open: a one-step synthetic run
    r = cli(p, "controls", "run", "--module", "plot-groups", "--allow-mock", "--json", env=MOCK)
    assert r.exit_code == 0, r.output + str(r.stderr)
    draw = json.loads(r.output)["results"][0]
    assert draw["passed"] and draw["metrics"]["step_status"] == "completed"
    steps = p.store.all("SELECT step_id FROM steps WHERE run_id=?", (draw["run_id"],))
    assert [s["step_id"] for s in steps] == ["01_plot-groups"]
    svg = p.store.one(
        "SELECT path FROM artifacts WHERE run_id=? AND name='figure'", (draw["run_id"],)
    )
    assert Path(svg["path"]).read_text().startswith("<svg")


def test_tool_controls_run_from_an_open_project_and_current_for(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    tool = q.tool("compare-groups")
    env_digest = q.executor().env_digest("toy-py")
    assert current_for(q.store, tool, env_digest)["status"] == "none"
    r = cli(q, "controls", "run", "--module", "compare-groups", "--allow-mock", "--json", env=MOCK)
    assert r.exit_code == 0, r.output + str(r.stderr)
    res = {x["control"]: x for x in json.loads(r.output)["results"]}
    assert res["positive-known-differences"]["passed"] and res["negative-shuffled-groups"]["passed"]
    run_id = res["positive-known-differences"]["run_id"]
    assert [
        s["step_id"] for s in q.store.all("SELECT step_id FROM steps WHERE run_id=?", (run_id,))
    ] == ["01_compare-groups"]
    assert q.store.scalar("SELECT status FROM runs WHERE run_id=?", (run_id,)) == "completed"
    # control runs never become the open project's question run
    from stringency.runs import latest_run

    assert latest_run(q.store) is None
    cur = current_for(q.store, tool, env_digest)
    assert (
        cur["status"] == "current"
        and cur["last_passing"]["control"] == "positive-known-differences"
    )
    assert current_for(q.store, tool, "another-digest")["status"] == "stale"
    assert current_for(q.store, tool, None)["status"] == "stale"
    # tools list shows the passing control now
    payload = json.loads(cli(q, "tools", "list", "--json").output)
    assert (
        payload["tools"][0]["controls"]["last_passing"]["control_name"]
        == "positive-known-differences"
    )
    # a perturbed truth: the control fails and is a regression against the last passing run
    truth = q.method_root / "controls/fixtures/compare_truth.tsv"
    truth.write_text(truth.read_text().replace("59.22", "12.00"))
    from stringency import git

    git.commit_all(q.method_root, "perturb the truth")  # a dirty checkout would not open a run
    r = cli(q, "controls", "run", "--module", "compare-groups", "--allow-mock", "--json", env=MOCK)
    assert r.exit_code == 13, r.output
    pos = {x["control"]: x for x in json.loads(r.output)["results"]}["positive-known-differences"]
    assert (
        pos["passed"] is False
        and pos["metrics"]["rows_matching"] == 2
        and pos["regression"] is True
    )
    assert pos["previous"]["rows_matching"] == 3


def test_plot_groups_chains_on_the_comparison(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    assert [m.manifest.name for m in q.tools()] == ["compare-groups", "plot-groups"]
    cli(q, "ask", "show me the differences")
    r = cli(q, "call", "plot-groups", "--json")
    assert r.exit_code == 15 and "comparison (table) of plot-groups is unbound" in str(r.stderr)
    r = cli(q, "call", "compare-groups", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    r = cli(q, "call", "plot-groups", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["step_id"] == "02_plot-groups" and out["inputs"]["comparison"].endswith(
        "comparison_table.tsv"
    )
    assert (
        out["artifacts"][0]["kind"] == "figure"
        and Path(out["artifacts"][0]["path"]).suffix == ".svg"
    )
    rc = load_run(q, out["run_id"])
    assert rc.pipeline.step("02_plot-groups").predecessors() == ["01_compare-groups"]
