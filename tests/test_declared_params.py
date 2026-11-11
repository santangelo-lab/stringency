"""Design 2.5 (2026-10-14, backlog L24): parameters declared in objective.yml are checked at
init, listed in the echo-back, taken as given when the step runs, and never proposed. A value
the step's own gate would block is refused at init with that gate's reason (L168, 2026-11-10)."""

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


def test_a_declared_value_the_step_would_block_is_refused_at_init(
    make_project: InitFn, tmp_path: Path, toy_data: Path
) -> None:
    """L168: the DE test replicate of 2026-11-10 declared a fixed parameter's value, `init`
    accepted it, the owner confirmed, two steps ran over 100,000 cells and the third blocked.
    The same predicates' conditions and reasons, read at `init`; nothing is bound."""

    def refused(params: dict, **kw: object) -> str:  # type: ignore[type-arg]
        decl = write_declarations(
            tmp_path / f"decl-{len(list(tmp_path.iterdir()))}",
            toy_data,
            objective={**OBJECTIVE, "params": params},
        )
        with pytest.raises(ConfigError) as e:
            make_project(
                pipeline="toy-engine", execution="engine", objective=decl["objective.yml"], **kw
            )
        return str(e.value)

    # out of range, and outside the options: param.out_of_range's reason
    said = refused({"01_filter": {"min_value": 99}})
    assert "objective params: the step would block this declared value" in said
    assert (
        "step 01_filter, parameter min_value: a proposed value is outside the declared range "
        "or options (declared 99, range [0.0, 40.0]; param.out_of_range)" in said
    )
    assert "nothing was bound" in said
    said = refused({"01_filter": {"min_value": 99}, "04_compare": {"correction": "holm"}})
    assert "these declared values" in said
    assert "step 04_compare, parameter correction" in said and "options ['bh'," in said
    # in range, of the wrong type: param.schema_invalid's reason
    said = refused({"01_filter": {"min_value": "12"}})
    assert "a parameter fails the module's schema: " in said and "param.schema_invalid" in said
    # under `params: locked` any declared value off the default: param.locked_changed's reason
    said = refused({"01_filter": {"min_value": 12}}, profile="strict")
    assert (
        "step 01_filter, parameter min_value: parameters are locked under this profile "
        "(default 10, declared 12; param.locked_changed)" in said
    )
    # no project directory survives a refusal
    assert not [d for d in tmp_path.iterdir() if d.name.startswith("proj")]


def test_a_declared_value_the_step_would_only_flag_is_left_to_the_step(
    make_project: InitFn, tmp_path: Path, toy_data: Path
) -> None:
    """Out of range under `params: free` is a flag at the step (design 6.5), so `init` admits
    it; the default declared under `strict` is no change; an in-range value is as before."""
    for n, (params, profile) in enumerate(
        [
            ({"01_filter": {"min_value": 99}}, "exploratory"),
            ({"01_filter": {"min_value": 10}}, "strict"),
            ({"01_filter": {"min_value": 12}, "04_compare": {"correction": "none"}}, "standard"),
        ]
    ):
        decl = write_declarations(
            tmp_path / f"ok-{n}", toy_data, objective={**OBJECTIVE, "params": params}
        )
        p = make_project(
            pipeline="toy-engine",
            execution="engine",
            objective=decl["objective.yml"],
            profile=profile,
        )
        assert "Parameters declared, taken as given" in p.echo_path().read_text()


def test_a_declared_change_to_a_fixed_parameter_is_refused_at_init_and_by_declare_check(
    tmp_path: Path,
    toy_data: Path,
    method_repo,  # type: ignore[no-untyped-def]
) -> None:
    """A parameter with no range and no options is fixed: `param.locked_changed` blocks any
    other value under every profile, and `declare --check` says so as `init` does."""
    import yaml
    from typer.testing import CliRunner

    from stringency import git
    from stringency.cli.app import app
    from stringency.project import InitRequest, check_declarations, init_project
    from tests.conftest import MethodRepo

    pipe = method_repo.path / "pipelines" / "toy-engine.yml"
    doc = yaml.safe_load(pipe.read_text())
    doc["steps"][3]["params"]["correction"] = {"default": "bh"}
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    sha = method_repo.commit("correction is fixed")
    git.tag(method_repo.path, "v0.1.1")
    repo = MethodRepo(method_repo.path, "v0.1.1", sha)

    def request(name: str, value: str) -> InitRequest:
        decl = write_declarations(
            tmp_path / f"decl-{name}",
            toy_data,
            objective={**OBJECTIVE, "params": {"04_compare": {"correction": value}}},
        )
        return InitRequest(
            path=tmp_path / name,
            method=repo.spec,
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

    want = (
        "step 04_compare, parameter correction: a fixed parameter differs from its default "
        "(default 'bh', declared 'bonferroni'; param.locked_changed)"
    )
    with pytest.raises(ConfigError, match="the step would block") as e:
        init_project(request("fixed", "bonferroni"))
    assert want in str(e.value) and not (tmp_path / "fixed").exists()
    with pytest.raises(ConfigError) as e:
        check_declarations(request("checked", "bonferroni"))
    assert want in str(e.value)
    r = CliRunner().invoke(
        app,
        [
            "declare",
            str(tmp_path / "decl-checked"),
            "--check",
            "--method",
            repo.spec,
            "--pipeline",
            "toy-engine",
            "--judgment-harness",
            "mock",
            "--execution",
            "engine",
            "--executor",
            "local",
        ],
    )
    assert r.exit_code == 15, r.output
    assert "param.locked_changed" in (r.output + str(r.stderr))
    # the default itself, declared, is no change
    assert init_project(request("same", "bh")).objective.params == {
        "04_compare": {"correction": "bh"}
    }
