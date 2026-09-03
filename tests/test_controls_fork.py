"""M10: controls (negative, positive, regression diff) and fork."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency import hashing
from stringency.controls import run_controls
from stringency.exit_codes import ConfigError, RefusedError
from stringency.fork import fork
from stringency.project import Project
from stringency.runloop import run_loop
from stringency.runs import load_run
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli


@pytest.fixture
def cproject(make_project: InitFn, monkeypatch: pytest.MonkeyPatch) -> Project:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / "unanimous.yml"))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", "direct")
    return p


def test_mock_refused_without_allow(cproject: Project) -> None:
    with pytest.raises(RefusedError, match="mock"):
        run_controls(cproject, "label-groups")


def test_negative_and_positive_controls_pass(cproject: Project) -> None:
    results = run_controls(cproject, "label-groups", allow_mock=True)
    by = {r.control: r for r in results}
    neg, pos = by["negative-shuffled-groups"], by["positive-known-labels"]
    assert neg.passed and neg.metrics["null_output"] is True and neg.metrics["abstain_rate"] == 1.0
    assert pos.passed and pos.metrics["agreement"] == 1.0 and pos.metrics["abstain_rate"] == 0.0
    rows = cproject.store.all("SELECT * FROM controls_runs ORDER BY rowid")
    assert [r["control_name"] for r in rows] == [
        "negative-shuffled-groups",
        "positive-known-labels",
    ]
    assert all(r["passed"] == 1 for r in rows)
    # control runs are isolated under controls/ and never the project's latest analysis run
    assert (cproject.root / "controls" / "label-groups" / "negative-shuffled-groups").exists()
    assert cproject.store.scalar("SELECT COUNT(*) FROM runs WHERE kind='control'") == 2
    from stringency.runs import latest_run

    assert latest_run(cproject.store) is None
    # the negative run went through the real gate machinery: judgments and holds exist
    assert (
        cproject.store.scalar("SELECT COUNT(*) FROM judgments WHERE run_id=?", (neg.run_id,)) == 9
    )
    assert (
        cproject.store.scalar(
            "SELECT COUNT(*) FROM holds WHERE run_id=? AND kind='self_uncertain'", (neg.run_id,)
        )
        == 3
    )


def test_regression_diff_exits_nonzero(cproject: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    r = cli(cproject, "controls", "run", "--module", "label-groups", "--allow-mock", env=MOCK)
    assert r.exit_code == 0, r.output
    # lower the mock's agreement: relabel C as sparse -> positive control agreement drops
    bad = Path(cproject.root) / "bad_mock.yml"
    bad.write_text(
        (HARNESS / "unanimous.yml").read_text().replace("label: variable", "label: sparse")
    )
    r = cli(
        cproject,
        "controls",
        "run",
        "--module",
        "label-groups",
        "--allow-mock",
        "--json",
        env={**MOCK, "STRINGENCY_MOCK_FIXTURE": str(bad)},
    )
    assert r.exit_code == 13, r.output
    res = {x["control"]: x for x in json.loads(r.output)["results"]}
    pos = res["positive-known-labels"]
    assert (
        pos["passed"] is False and pos["metrics"]["agreement"] < 1.0 and pos["regression"] is True
    )
    assert pos["previous"]["agreement"] == 1.0


def test_generator_refuses_holdout(cproject: Project) -> None:
    import yaml

    d = yaml.safe_load((cproject.root / "design.yml").read_text())
    groups = cproject.method_root / "controls" / "fixtures" / "groups.csv"
    d["holdout"] = [
        {"type": "frame", "blake3": hashing.hash_file(groups), "note": "never inspected"}
    ]
    (cproject.root / "design.yml").write_text(yaml.safe_dump(d))
    p = Project.load(cproject.root)
    with pytest.raises(RefusedError, match="holdout"):
        run_controls(p, "label-groups", allow_mock=True)


# -- fork ---------------------------------------------------------------------------------------


def _rows_digest(p: Project, run_id: str) -> str:
    parts = []
    for table in (
        "steps",
        "actions",
        "artifacts",
        "state_snapshots",
        "predicate_results",
        "consensus",
        "judgments",
    ):
        rows = p.store.all(f"SELECT * FROM {table} WHERE run_id=? ORDER BY rowid", (run_id,))
        parts.append([dict(r) for r in rows])
    return hashing.hash_json(parts)


def test_fork_reruns_from_step_and_leaves_parent_untouched(cproject: Project) -> None:
    r = cli(cproject, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    parent = json.loads(r.output)["run_id"]
    before = _rows_digest(cproject, parent)
    r = cli(
        cproject,
        "fork",
        "--from",
        parent,
        "--at",
        "02_summarize",
        "--set",
        "04_compare.correction=bonferroni",
        "--reason",
        "compare corrections",
        "--json",
    )
    assert r.exit_code == 0, r.output
    child = json.loads(r.output)["run_id"]
    run = cproject.store.one("SELECT * FROM runs WHERE run_id=?", (child,))
    assert run["parent_run_id"] == parent and run["fork_at_step"] == "02_summarize"
    assert json.loads(run["delta_json"])["params"] == {"04_compare": {"correction": "bonferroni"}}
    statuses = {
        s["step_id"]: s["status"]
        for s in cproject.store.all("SELECT step_id, status FROM steps WHERE run_id=?", (child,))
    }
    assert statuses == {
        "01_filter": "completed",
        "02_summarize": "pending",
        "03_label": "pending",
        "04_compare": "pending",
        "05_report": "pending",
    }
    snap = cproject.store.one(
        "SELECT summary_json FROM state_snapshots WHERE run_id=? AND step_id='run' ORDER BY rowid DESC LIMIT 1",
        (child,),
    )
    hist = json.loads(snap["summary_json"])["history"]
    assert (
        hist == [dict(h, inherited=True) for h in hist]
        and hist[0]["step"] == "01_filter"
        and hist[0]["inherited"] is True
    )
    # the child runs steps 2 onward only
    r = cli(cproject, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["run_id"] == child
    acts = [
        a["step_id"]
        for a in cproject.store.all(
            "SELECT step_id FROM actions WHERE run_id=? ORDER BY rowid", (child,)
        )
    ]
    assert acts == ["02_summarize", "03_label", "04_compare", "05_report"]
    params = json.loads(
        cproject.store.scalar(
            "SELECT params_json FROM actions WHERE run_id=? AND step_id='04_compare'", (child,)
        )
    )
    assert params["correction"] == "bonferroni"
    assert (
        cproject.store.scalar(
            "SELECT param_source_json FROM actions WHERE run_id=? AND step_id='04_compare'",
            (child,),
        )
        == '{"correction":"agent","replicate_unit":"default"}'
    )
    # the parent is unchanged
    assert _rows_digest(cproject, parent) == before
    assert cproject.store.scalar("SELECT status FROM runs WHERE run_id=?", (parent,)) == "completed"


def test_fork_validation(cproject: Project) -> None:
    r = cli(cproject, "run", "--json", env=MOCK)
    parent = json.loads(r.output)["run_id"]
    with pytest.raises(ConfigError, match="before --at"):
        fork(cproject, from_run=parent, at="03_label", sets=["01_filter.min_value=5"], reason="x")
    with pytest.raises(ConfigError, match="unknown step"):
        fork(cproject, from_run=parent, at="03_label", sets=["09_nope.x=1"], reason="x")
    # a fork's out-of-range change is still gated
    child = fork(
        cproject,
        from_run=parent,
        at="01_filter",
        sets=["01_filter.min_value=99"],
        reason="too high",
    )
    nx = run_loop(child)
    assert nx.kind == "blocked" and "param.out_of_range" in nx.message
    assert load_run(cproject, child.run_id).run["status"] == "blocked"
