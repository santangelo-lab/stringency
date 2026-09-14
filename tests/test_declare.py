"""Agent-drafted declarations and chained projects (spec/declarations-and-objectives.md, H1 to
H3): `declare --check`, `init --drafted-by --brief`, and `derived_from` on an input item."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from stringency import hashing
from stringency.cli.app import app
from stringency.deliver import deliver
from stringency.exit_codes import ConfigError
from stringency.project import InitRequest, check_declarations, init_project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations
from tests.test_run import MOCK, cli

runner = CliRunner()


def _declare_args(decl_dir: Path, method_repo: MethodRepo, pipeline: str = "toy") -> list[str]:
    return [
        "declare",
        str(decl_dir),
        "--check",
        "--method",
        method_repo.spec,
        "--pipeline",
        pipeline,
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
    ]


def test_declare_check_prints_echo_and_creates_nothing(
    method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    decl_dir = declarations["design.yml"].parent
    before = sorted(p.name for p in decl_dir.iterdir())
    r = runner.invoke(app, _declare_args(decl_dir, method_repo))
    assert r.exit_code == 0, r.output
    assert "# Echo-back" in r.output and "A versus B" in r.output
    assert "declarations check out" in r.output and "Nothing was created" in r.output
    assert sorted(p.name for p in decl_dir.iterdir()) == before  # no project, no scratch
    r = runner.invoke(app, [*_declare_args(decl_dir, method_repo), "--json"])
    out = json.loads(r.output)
    assert out["schema"] == "stringency.declare/1"
    assert set(out["hashes"]) == {"design.yml", "objective.yml", "inputs.yml"}
    assert out["inputs"]["groups"] == hashing.hash_file(
        Path(yaml.safe_load(declarations["inputs.yml"].read_text())["items"][0]["path"])
    )
    ids = {p["predicate_id"] for p in out["predicates"]}
    assert "init.contrast_undeclared" in ids and "init.column_missing" in ids
    assert not any(p["fired"] for p in out["predicates"])
    assert out["method_sha"] == method_repo.sha


def test_declare_check_names_the_failure(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    # a contrast on a level the design does not declare: an init predicate fires
    files = write_declarations(
        tmp_path / "bad1",
        toy_data,
        objective={
            "objective": 1,
            "id": "toy_ab",
            "question": "compare_groups",
            "contrasts": [["group", "A", "Z"]],
            "replication_unit": "unit",
            "min_n_per_group": 2,
            "deliverables": ["comparison_table", "group_labels"],
            "domain": {},
        },
    )
    r = runner.invoke(app, _declare_args(files["design.yml"].parent, method_repo))
    assert r.exit_code == 15
    assert "init.level_undeclared" in (r.output + str(r.stderr))
    # a wrong input hash is refused before any predicate runs
    inputs = yaml.safe_load(files["inputs.yml"].read_text())
    inputs["items"][0]["blake3"] = "0" * 64
    files["inputs.yml"].write_text(yaml.safe_dump(inputs))
    r = runner.invoke(app, _declare_args(files["design.yml"].parent, method_repo))
    assert r.exit_code == 15 and "hash mismatch" in (r.output + str(r.stderr))
    # a question the plugin does not know
    inputs["items"][0]["blake3"] = hashing.hash_file(toy_data)
    files["inputs.yml"].write_text(yaml.safe_dump(inputs))
    obj = yaml.safe_load(files["objective.yml"].read_text())
    obj["question"] = "find_biomarkers"
    obj["contrasts"] = [["group", "A", "B"]]
    files["objective.yml"].write_text(yaml.safe_dump(obj))
    r = runner.invoke(app, _declare_args(files["design.yml"].parent, method_repo))
    assert r.exit_code == 15 and "not in the plugin vocabulary" in (r.output + str(r.stderr))
    # without --check the verb refuses
    r = runner.invoke(
        app,
        [
            "declare",
            str(files["design.yml"].parent),
            "--method",
            method_repo.spec,
            "--pipeline",
            "toy",
        ],
    )
    assert r.exit_code == 15


def test_check_declarations_api_matches_init(
    method_repo: MethodRepo, declarations: dict[str, Path], make_project: InitFn
) -> None:
    req = InitRequest(
        path=declarations["design.yml"].parent / "unused",
        method=method_repo.spec,
        pipeline="toy",
        objective=declarations["objective.yml"],
        design=declarations["design.yml"],
        inputs=declarations["inputs.yml"],
        judgment_harness="mock",
        executor="local",
    )
    check = check_declarations(req)
    p = make_project()
    assert check.hashes == p.declaration_hashes()
    assert check.echo == p.echo_path().read_text()
    assert not (declarations["design.yml"].parent / "unused").exists()


def test_init_records_drafter_and_brief(
    tmp_path: Path,
    method_repo: MethodRepo,
    declarations: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text("Compare groups A and B of the toy data; the unit is the replicate.\n")
    monkeypatch.setenv("STRINGENCY_OPERATOR", "claude-science")
    monkeypatch.setenv("STRINGENCY_SESSION_REF", "frame-42")
    r = runner.invoke(
        app,
        [
            "init",
            str(tmp_path / "drafted"),
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
            "tester",
            "--judgment-harness",
            "mock",
            "--executor",
            "local",
            "--drafted-by",
            "agent",
            "--brief",
            str(brief),
            "--json",
        ],
    )
    assert r.exit_code == 10, r.output  # the confirm hold is open
    out = json.loads(r.output)
    assert out["declarations"] == {
        "drafted_by": "agent",
        "harness": "claude-science",
        "session_ref": "frame-42",
        "brief": "brief.md",
    }
    from stringency.project import Project

    p = Project.load(tmp_path / "drafted")
    assert (p.root / "brief.md").read_text() == brief.read_text()
    cfg = yaml.safe_load((p.root / "stringency.yml").read_text())
    assert cfg["declarations"]["drafted_by"] == "agent"
    ctx = json.loads(p.confirm_hold()["context_json"])
    assert ctx["drafted_by"] == "agent" and ctx["brief"] == "brief.md"
    assert ctx["brief_blake3"] == hashing.hash_file(brief)
    # the default is a person, with no brief, and the hold context says so
    p2 = init_project(
        InitRequest(
            path=tmp_path / "byhand",
            method=method_repo.spec,
            pipeline="toy",
            objective=declarations["objective.yml"],
            design=declarations["design.yml"],
            inputs=declarations["inputs.yml"],
            owner="tester",
            judgment_harness="mock",
            executor="local",
        )
    )
    assert p2.config.declarations is not None and p2.config.declarations.drafted_by == "person"
    assert "brief" not in json.loads(p2.confirm_hold()["context_json"])
    with pytest.raises(ConfigError, match="person or agent"):
        init_project(
            InitRequest(
                path=tmp_path / "robot",
                method=method_repo.spec,
                pipeline="toy",
                objective=declarations["objective.yml"],
                design=declarations["design.yml"],
                inputs=declarations["inputs.yml"],
                judgment_harness="mock",
                executor="local",
                drafted_by="robot",
            )
        )


PROCESS_OBJECTIVE = {
    "objective": 1,
    "id": "toy_process",
    "question": "process_rows",
    "contrasts": [],
    "replication_unit": "unit",
    "min_n_per_group": 2,
    "deliverables": ["object"],
    "domain": {},
}


def test_chained_projects_through_derived_from(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    """Option 1 of the objectives note: a processing project delivers the filtered frame; a
    downstream project binds it with `derived_from`, which init verifies against the sidecar."""
    up_files = write_declarations(tmp_path / "up", toy_data, objective=PROCESS_OBJECTIVE)
    up = make_project(
        pipeline="toy-process",
        execution="engine",
        objective=up_files["objective.yml"],
        design=up_files["design.yml"],
        inputs=up_files["inputs.yml"],
    )
    assert "process_rows with no contrast declared" in up.echo_path().read_text()
    accept_hold(up.store, up.confirm_hold()["hold_id"])
    r = cli(up, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    d = deliver(load_run(up, run_id))
    delivered = d.path / "01_filter.object.csv"
    assert delivered.exists() and (d.path / "01_filter.object.csv.stringency.json").exists()

    down_inputs = {
        "inputs": 1,
        "items": [
            {
                "name": "groups",
                "path": str(delivered),
                "type": "frame",
                "blake3": hashing.hash_file(delivered),
                "source": "delivered by the processing project",
                "derived_from": {
                    "run_id": run_id,
                    "step_id": "01_filter",
                    "output": "object",
                    "project": str(up.root),
                },
            }
        ],
    }
    down_files = write_declarations(tmp_path / "down", toy_data, inputs=down_inputs)
    down = make_project(
        pipeline="toy-engine",
        execution="engine",
        objective=down_files["objective.yml"],
        design=down_files["design.yml"],
        inputs=down_files["inputs.yml"],
    )
    assert down.inputs.items[0].derived_from is not None
    assert down.inputs.items[0].derived_from.run_id == run_id
    accept_hold(down.store, down.confirm_hold()["hold_id"])
    r = cli(down, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    down_run = json.loads(r.output)["run_id"]
    captures = json.loads(
        down.store.scalar(
            "SELECT payload_json FROM run_events WHERE run_id=? AND event='captures'", (down_run,)
        )
    )
    assert captures["derived_from"] == [
        {
            "input": "groups",
            "run_id": run_id,
            "step_id": "01_filter",
            "output": "object",
            "project": str(up.root),
        }
    ]
    d2 = deliver(load_run(down, down_run))
    methods = (d2.path / "methods.md").read_text()
    assert (
        f"Input groups was delivered by stringency run {run_id} (step 01_filter, output object)."
        in methods
    )

    # tampering: a derived_from that names another run, or a file with no sidecar, is refused
    bad = dict(down_inputs)
    bad["items"] = [dict(down_inputs["items"][0])]
    bad["items"][0]["derived_from"] = {
        **down_inputs["items"][0]["derived_from"],
        "run_id": "01NOTTHATRUN00000000000000",
    }
    bad_files = write_declarations(tmp_path / "bad", toy_data, inputs=bad)
    with pytest.raises(ConfigError, match="sidecar names run"):
        make_project(
            pipeline="toy-engine",
            execution="engine",
            objective=bad_files["objective.yml"],
            design=bad_files["design.yml"],
            inputs=bad_files["inputs.yml"],
        )
    orphan = dict(down_inputs)
    orphan["items"] = [dict(down_inputs["items"][0])]
    orphan["items"][0]["path"] = str(toy_data)
    orphan["items"][0]["blake3"] = hashing.hash_file(toy_data)
    orphan_files = write_declarations(tmp_path / "orphan", toy_data, inputs=orphan)
    with pytest.raises(ConfigError, match="no sidecar"):
        make_project(
            pipeline="toy-engine",
            execution="engine",
            objective=orphan_files["objective.yml"],
            design=orphan_files["design.yml"],
            inputs=orphan_files["inputs.yml"],
        )


def test_plugins_list_json_exposes_what_the_declare_skill_needs() -> None:
    r = runner.invoke(app, ["plugins", "list", "--json"])
    assert r.exit_code == 0, r.output
    toy = next(p for p in json.loads(r.output)["plugins"] if p["name"] == "stringency-toy")
    assert toy["questions"] == ["compare_groups", "process_rows"]
    assert toy["design_schema"]["required"] == ["design", "units", "factors", "replication_unit"]
    assert "abundant" in toy["vocabulary_terms"]["group_labels@1"]
    assert toy["object_types"] == ["frame"]
    assert toy["defaults"] == {"min_n_per_group": 2}
