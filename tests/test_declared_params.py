"""Design 2.5 (2026-10-14, backlog L24): parameters declared in objective.yml are checked at
init, listed in the echo-back, taken as given when the step runs, and never proposed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency.exit_codes import ConfigError
from stringency.project import Project
from tests.conftest import InitFn, accept_hold, write_declarations
from tests.test_run import HARNESS, MOCK, cli

OBJECTIVE = {
    "objective": 1,
    "id": "toy_ab",
    "question": "compare_groups",
    "contrasts": [["group", "A", "B"]],
    "replication_unit": "unit",
    "min_n_per_group": 2,
    "deliverables": ["comparison_table", "group_labels"],
    "domain": {},
}


def _declared(make_project: InitFn, tmp_path: Path, toy_data: Path, params: dict) -> Project:  # type: ignore[type-arg]
    decl = write_declarations(
        tmp_path / "decl-params", toy_data, objective={**OBJECTIVE, "params": params}
    )
    return make_project(pipeline="toy-engine", execution="engine", objective=decl["objective.yml"])


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRINGENCY_MOCK_FIXTURE", str(HARNESS / "unanimous.yml"))
    monkeypatch.setenv("STRINGENCY_MOCK_FAMILY", "direct")


def test_declared_parameter_is_echoed_taken_as_given_and_not_asked(
    make_project: InitFn, tmp_path: Path, toy_data: Path, mock_env: None
) -> None:
    p = _declared(make_project, tmp_path, toy_data, {"01_filter": {"min_value": 9}})
    echo = " ".join(p.echo_path().read_text().split())
    assert "Parameters declared, taken as given" in echo and "01_filter: min_value = 9" in echo
    assert p.inherited_confirmation() is None
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    row = p.store.one("SELECT * FROM actions WHERE run_id=? AND step_id='01_filter'", (run_id,))
    assert json.loads(row["params_json"]) == {"min_value": 9}
    assert json.loads(row["param_source_json"]) == {"min_value": "declared"}
    assert row["proposed_by"] == "declared"
    assert (
        p.store.scalar(
            "SELECT COUNT(*) FROM holds WHERE run_id=? AND step_id='01_filter'", (run_id,)
        )
        == 0
    )
    # a fork keeps the declaration's label
    r = cli(p, "fork", "--from", run_id, "--at", "01_filter", "--check", "--json")
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["params"]["01_filter"] == {
        "min_value": {"value": 9, "source": "declared"}
    }
    # a manual proposal starts from the declared value and may override it (then it is the agent's)
    r = cli(p, "fork", "--from", run_id, "--at", "01_filter", "--reason", "by hand", "--json")
    child = json.loads(r.output)["run_id"]
    r = cli(p, "propose", "01_filter", "--set", "min_value=12", "--reason", "twelve", "--json")
    assert r.exit_code == 10, (
        r.output
    )  # param.agent_proposed: the agent departed from the declaration
    row = p.store.one("SELECT * FROM actions WHERE run_id=? AND step_id='01_filter'", (child,))
    assert json.loads(row["param_source_json"]) == {"min_value": "agent"}


def test_declared_parameter_must_exist(
    make_project: InitFn, tmp_path: Path, toy_data: Path
) -> None:
    with pytest.raises(ConfigError, match="no step 09_nope"):
        _declared(make_project, tmp_path, toy_data, {"09_nope": {"x": 1}})
    with pytest.raises(ConfigError, match="declares no parameter max_value"):
        _declared(make_project, tmp_path, toy_data, {"01_filter": {"max_value": 1}})


def test_declare_check_refuses_an_unknown_declared_parameter(
    make_project: InitFn,
    tmp_path: Path,
    toy_data: Path,
    method_repo,  # type: ignore[no-untyped-def]
) -> None:
    from stringency.project import InitRequest, check_declarations

    decl = write_declarations(
        tmp_path / "decl-bad",
        toy_data,
        objective={**OBJECTIVE, "params": {"01_filter": {"nope": 1}}},
    )
    req = InitRequest(
        path=tmp_path / "never",
        method=method_repo.spec,
        pipeline="toy-engine",
        objective=decl["objective.yml"],
        design=decl["design.yml"],
        inputs=decl["inputs.yml"],
        owner="tester",
        reviewer="tester",
        judgment_harness="mock",
        execution="engine",
        executor="local",
    )
    with pytest.raises(ConfigError, match="declares no parameter nope"):
        check_declarations(req)
    assert not (tmp_path / "never").exists()
