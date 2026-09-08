from pathlib import Path

import pytest
import yaml

from stringency.exit_codes import ConfigError
from stringency.project import InitRequest, Project, init_project
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations


def test_init_layout_and_records(project: Project) -> None:
    root = project.root
    for p in (
        "stringency.yml",
        "objective.yml",
        "design.yml",
        "inputs.yml",
        "method",
        "prov/run.db",
        "prov/justifications",
        "runs",
        "deliver",
        "controls",
        ".stringency",
        "echo.md",
    ):
        assert (root / p).exists(), p
    row = project.store.one("SELECT * FROM projects")
    assert row is not None
    assert row["pipeline_name"] == "toy"
    assert row["profile"] == "standard"
    hold = project.confirm_hold()
    assert hold is not None
    assert hold["kind"] == "confirm"
    assert hold["waits_on_role"] == "owner"
    assert hold["resolved_by_review"] is None
    echo = (root / "echo.md").read_text()
    assert "50 rows in 9 units across 3 groups" in echo
    assert "the replicate is the unit" in echo
    assert "A versus B" in echo


def test_init_records_method_sha_matching_tag(project: Project, method_repo: MethodRepo) -> None:
    assert project.config.method.sha == method_repo.sha
    assert project.config.method.tag == "v0.1.0"


def test_init_records_init_predicates(project: Project) -> None:
    rows = project.store.all(
        "SELECT predicate_id, fired FROM predicate_results WHERE run_id='init'"
    )
    ids = {r["predicate_id"] for r in rows}
    assert {
        "init.contrast_undeclared",
        "init.level_undeclared",
        "init.replication_unit_undeclared",
        "init.column_missing",
        "init.question_unsupported",
        "init.deliverable_unproduced",
        "init.reference_mismatch",
    } <= ids
    assert not any(r["fired"] for r in rows)


def test_reinit_refused(project: Project, make_project: InitFn) -> None:
    with pytest.raises(ConfigError, match="not empty"):
        make_project(path=project.root)


def test_wrong_input_hash_refused(tmp_path: Path, toy_data: Path, make_project: InitFn) -> None:
    decl = write_declarations(
        tmp_path / "bad",
        toy_data,
        inputs={
            "inputs": 1,
            "items": [
                {"name": "groups", "path": str(toy_data), "type": "frame", "blake3": "00" * 32}
            ],
        },
    )
    with pytest.raises(ConfigError, match="hash mismatch"):
        make_project(inputs=decl["inputs.yml"])
    assert not (tmp_path / "proj1").exists() or not any((tmp_path / "proj1").iterdir())


def test_open_strict_refused(make_project: InitFn) -> None:
    with pytest.raises(ConfigError, match="open with profile strict"):
        make_project(mode="open", profile="strict")


def test_non_pipeline_mode_refused(make_project: InitFn) -> None:
    with pytest.raises(ConfigError, match="reserved"):
        make_project(mode="staged")


@pytest.mark.parametrize(
    "field,patch,predicate",
    [
        ("objective", {"contrasts": [["treatment", "A", "B"]]}, "init.contrast_undeclared"),
        ("objective", {"contrasts": [["group", "A", "Z"]]}, "init.level_undeclared"),
        ("objective", {"replication_unit": "animal"}, "init.replication_unit_undeclared"),
        (
            "objective",
            {"question": "compare_groups", "deliverables": ["comparison_table", "heatmap"]},
            "init.deliverable_unproduced",
        ),
        ("design", {"batch": ["slide_id"]}, "init.column_missing"),
    ],
)
def test_init_predicates_must_fire(
    tmp_path: Path,
    toy_data: Path,
    make_project: InitFn,
    declarations: dict[str, Path],
    field: str,
    patch: dict,
    predicate: str,
) -> None:
    base = yaml.safe_load(declarations[f"{field}.yml"].read_text())
    base.update(patch)
    decl = write_declarations(tmp_path / "decl2", toy_data, **{field: base})
    with pytest.raises(ConfigError, match=predicate):
        make_project(**{field: decl[f"{field}.yml"]})


def test_init_question_unsupported_fires(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    # remove `answers` from the pipeline and commit, so the objective's question is unsupported
    pipe = method_repo.path / "pipelines" / "toy.yml"
    text = pipe.read_text().replace("answers: [compare_groups]", "answers: []")
    pipe.write_text(text)
    method_repo.commit("drop answers")
    from stringency import git

    git.tag(method_repo.path, "v0.1.1")
    with pytest.raises(ConfigError, match="init.question_unsupported"):
        init_project(
            InitRequest(
                path=tmp_path / "p",
                method=f"{method_repo.path}@v0.1.1",
                pipeline="toy",
                objective=declarations["objective.yml"],
                design=declarations["design.yml"],
                inputs=declarations["inputs.yml"],
                owner="t",
                reviewer="t",
                judgment_harness="mock",
                executor="local",
            )
        )


def test_unknown_question_refused(
    tmp_path: Path, toy_data: Path, make_project: InitFn, declarations: dict[str, Path]
) -> None:
    base = yaml.safe_load(declarations["objective.yml"].read_text())
    base["question"] = "find_niches"
    decl = write_declarations(tmp_path / "decl3", toy_data, objective=base)
    with pytest.raises(ConfigError, match="not in the plugin vocabulary"):
        make_project(objective=decl["objective.yml"])


def test_design_schema_enforced(tmp_path: Path, toy_data: Path, make_project: InitFn) -> None:
    decl = write_declarations(
        tmp_path / "decl4",
        toy_data,
        design={
            "design": 1,
            "units": {"observation": "row"},
            "factors": {},
            "replication_unit": "unit",
        },
    )
    with pytest.raises(ConfigError, match="plugin schema"):
        make_project(design=decl["design.yml"])


def test_editing_objective_reopens_confirm_hold(project: Project) -> None:
    first = project.confirm_hold()
    assert first is not None
    accept_hold(project.store, first["hold_id"])
    assert project.confirm_status() == "accepted"
    echo_before = project.echo_path().read_text()
    obj = yaml.safe_load((project.root / "objective.yml").read_text())
    obj["min_n_per_group"] = 3
    (project.root / "objective.yml").write_text(yaml.safe_dump(obj))
    reloaded = Project.load(project.root)
    assert reloaded.confirm_status() == "pending"
    second = reloaded.confirm_hold()
    assert second is not None and second["hold_id"] != first["hold_id"]
    assert reloaded.echo_path().read_text() != echo_before
    assert "at least 3 unit per group" in reloaded.echo_path().read_text()
    n = reloaded.store.scalar("SELECT COUNT(*) FROM holds WHERE kind='confirm'")
    assert n == 2


def test_confirm_status_accepted(confirmed_project: Project) -> None:
    assert confirmed_project.confirm_status() == "accepted"


def test_cli_init(tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path]) -> None:
    from typer.testing import CliRunner

    from stringency.cli.app import app

    r = CliRunner().invoke(
        app,
        [
            "init",
            str(tmp_path / "cli-proj"),
            "--method",
            method_repo.spec,
            "--pipeline",
            "toy",
            "--objective",
            str(declarations["objective.yml"]),
            "--design",
            str(declarations["design.yml"]),
            "--inputs",
            str(declarations["inputs.yml"]),
            "--owner",
            "t",
            "--judgment-harness",
            "mock",
            "--executor",
            "local",
        ],
    )
    assert r.exit_code == 10, r.output  # init leaves its confirm hold open (design 14.2)
    assert "held: hold" in r.output and "(confirm)" in r.output
    r2 = CliRunner().invoke(
        app,
        [
            "init",
            str(tmp_path / "cli-proj"),
            "--method",
            method_repo.spec,
            "--pipeline",
            "toy",
            "--objective",
            str(declarations["objective.yml"]),
            "--design",
            str(declarations["design.yml"]),
            "--inputs",
            str(declarations["inputs.yml"]),
            "--executor",
            "local",
        ],
    )
    assert r2.exit_code == 15
