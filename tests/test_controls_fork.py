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
        == '{"correction":"fork","replicate_unit":"default"}'
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


# -- a fork inherits its parent's admitted parameters (design 2.6, backlog L27) ---------------


@pytest.fixture
def reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def _proposed_parent(p: Project) -> str:
    """A completed run whose 01_filter ran with min_value 9, proposed by the operator and
    accepted by a person at the `param.agent_proposed` hold (the pilot's ndim and
    cluster_method, in toy form). Every value below 10 in the toy table is below 8, so the
    filtered table and the judgment are the same as at the default."""
    from stringency.review import record_review

    r = cli(p, "propose", "01_filter", "--set", "min_value=9", "--reason", "nine", "--json")
    assert r.exit_code == 10, r.output
    run_id = json.loads(r.output)["run_id"]
    hold = p.store.one(
        "SELECT hold_id FROM holds WHERE run_id=? AND resolved_by_review IS NULL AND resolved_via IS NULL",
        (run_id,),
    )
    record_review(p, hold["hold_id"], "accept", reason="nine is right for this table")
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    return run_id


def _action(p: Project, run_id: str, step_id: str) -> dict[str, object]:
    row = p.store.one(
        "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (run_id, step_id),
    )
    assert row is not None, (run_id, step_id)
    return {
        "params": json.loads(row["params_json"]),
        "source": json.loads(row["param_source_json"]),
        "proposed_by": row["proposed_by"],
    }


def _holds(p: Project, run_id: str, step_id: str) -> int:
    n = p.store.scalar("SELECT COUNT(*) FROM holds WHERE run_id=? AND step_id=?", (run_id, step_id))
    return int(n or 0)


def test_fork_inherits_the_parents_admitted_parameters(cproject: Project, reviewer: None) -> None:
    parent = _proposed_parent(cproject)
    r = cli(
        cproject,
        "fork",
        "--from",
        parent,
        "--at",
        "01_filter",
        "--set",
        "04_compare.correction=bonferroni",
        "--reason",
        "compare corrections at the accepted filter",
        "--json",
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    child = out["run_id"]
    # the fork says what each re-run step will run with and where each value comes from
    assert out["params"]["01_filter"] == {"min_value": {"value": 9, "source": "inherited"}}
    assert out["params"]["04_compare"] == {
        "replicate_unit": {"value": "unit", "source": "default"},
        "correction": {"value": "bonferroni", "source": "fork"},
    }
    assert list(out["params"]) == cproject.pipeline.order()
    ev = cproject.store.one(
        "SELECT payload_json FROM run_events WHERE run_id=? AND event='fork'", (child,)
    )
    assert json.loads(ev["payload_json"])["params"] == out["params"]
    # the child runs to completion: the inherited value is neither reset to its default nor
    # asked again (it is not the agent's proposal in this run)
    r = cli(cproject, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    a = _action(cproject, child, "01_filter")
    assert a == {
        "params": {"min_value": 9},
        "source": {"min_value": "inherited"},
        "proposed_by": "inherited",
    }
    assert _holds(cproject, child, "01_filter") == 0
    a = _action(cproject, child, "04_compare")
    assert a["params"] == {"replicate_unit": "unit", "correction": "bonferroni"}
    assert a["source"] == {"replicate_unit": "default", "correction": "fork"}
    assert a["proposed_by"] == "fork"
    # the console's timeline names the fork's change as step.param=value
    from stringency.console import timeline

    titles = {s: cproject.pipeline.title(s) for s in cproject.pipeline.order()}
    texts = [e["text"] for run in timeline(cproject.store.conn, titles) for e in run["events"]]
    assert any("with 04_compare.correction=bonferroni" in t for t in texts), texts


def test_fork_inherits_through_a_parent_that_inherited(cproject: Project, reviewer: None) -> None:
    from stringency.fork import resolved_params

    parent = _proposed_parent(cproject)
    child = fork(
        cproject,
        from_run=parent,
        at="04_compare",
        sets=["04_compare.correction=bonferroni"],
        reason="corrections",
    )
    assert run_loop(child).kind == "completed"
    # the child inherited 01_filter as completed and holds no action for it ...
    assert (
        cproject.store.scalar(
            "SELECT COUNT(*) FROM actions WHERE run_id=? AND step_id='01_filter'", (child.run_id,)
        )
        == 0
    )
    # ... so a fork of the child at 01_filter reaches through it to the parent's value, and
    # takes the child's own fork decision at 04_compare as inherited
    table = resolved_params(cproject, child.run_id, "01_filter", {})
    assert table["01_filter"] == {"min_value": {"value": 9, "source": "inherited"}}
    assert table["04_compare"]["correction"] == {"value": "bonferroni", "source": "inherited"}
    grand = fork(cproject, from_run=child.run_id, at="01_filter", sets=[], reason="all again")
    assert run_loop(grand).kind == "completed"
    assert _action(cproject, grand.run_id, "01_filter")["params"] == {"min_value": 9}
    a = _action(cproject, grand.run_id, "04_compare")
    assert a["params"] == {"replicate_unit": "unit", "correction": "bonferroni"}
    assert a["source"] == {"replicate_unit": "default", "correction": "inherited"}
    assert a["proposed_by"] == "inherited"
    assert _holds(cproject, grand.run_id, "01_filter") == 0


def test_fork_check_lists_parameters_and_opens_no_run(cproject: Project, reviewer: None) -> None:
    parent = _proposed_parent(cproject)
    runs_before = cproject.store.scalar("SELECT COUNT(*) FROM runs")
    args = [
        "fork",
        "--from",
        parent,
        "--at",
        "01_filter",
        "--set",
        "04_compare.correction=bonferroni",
        "--check",
    ]
    r = cli(cproject, *args, "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["check"] is True and "run_id" not in out
    assert list(out["params"]) == cproject.pipeline.order()
    assert out["params"]["01_filter"] == {"min_value": {"value": 9, "source": "inherited"}}
    assert out["params"]["04_compare"]["correction"] == {"value": "bonferroni", "source": "fork"}
    r = cli(cproject, *args)
    assert "01_filter.min_value = 9  [inherited]" in r.output, r.output
    assert "04_compare.correction = 'bonferroni'  [fork]" in r.output
    assert cproject.store.scalar("SELECT COUNT(*) FROM runs") == runs_before
    # --check validates as fork does, and needs no reason
    r = cli(
        cproject,
        "fork",
        "--from",
        parent,
        "--at",
        "03_label",
        "--set",
        "01_filter.min_value=5",
        "--check",
    )
    assert r.exit_code != 0 and "before --at" in r.output


def test_propose_in_a_fork_starts_from_the_inherited_values(
    cproject: Project, reviewer: None
) -> None:
    parent = _proposed_parent(cproject)
    child = fork(
        cproject,
        from_run=parent,
        at="01_filter",
        sets=["04_compare.correction=bonferroni"],
        reason="by hand",
    )
    # the operator proposes 01_filter by hand without naming min_value: the parent's nine stands
    r = cli(cproject, "propose", "01_filter", "--json")
    assert r.exit_code == 0, r.output
    assert _action(cproject, child.run_id, "01_filter")["source"] == {"min_value": "inherited"}
    assert _holds(cproject, child.run_id, "01_filter") == 0
    r = cli(cproject, "run", "--until", "04_compare", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    # and a proposal at the fork's own step takes the fork's value as given
    a = _action(cproject, child.run_id, "04_compare")
    assert a["params"]["correction"] == "bonferroni" and a["source"]["correction"] == "fork"
