"""Table-driven lint tests: one broken method repo per error class in design 13."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from stringency.lint import lint_path
from stringency_toy import METHOD_TEMPLATE
from tests.conftest import MethodRepo

Breaker = Callable[[Path], None]


def _edit_yaml(path: Path, fn: Callable[[dict], None]) -> None:
    data = yaml.safe_load(path.read_text())
    fn(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _edit_json(path: Path, fn: Callable[[dict], None]) -> None:
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def contract_not_1(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(contract=2))


def manifest_bad_field(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(colour="blue"))


def op_not_in_vocab(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(operation="explode_rows"))


def gate_unresolved(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(gates=["qc.nonexistent@1"]))


def gate_wrong_version(m: Path) -> None:
    _edit_yaml(
        m / "modules/filter-rows/module.yml", lambda d: d.update(gates=["obj.feasibility@9"])
    )


def judgment_no_prompt(m: Path) -> None:
    (m / "modules/label-groups/prompt.md").unlink()


def judgment_no_schema(m: Path) -> None:
    (m / "modules/label-groups/schema.json").unlink()


def judgment_no_block(m: Path) -> None:
    _edit_yaml(m / "modules/label-groups/module.yml", lambda d: d.pop("judgment"))


def schema_weakened(m: Path) -> None:
    def fn(d: dict) -> None:
        d["required"].remove("abstain")
        d["properties"]["confidence"] = {"enum": ["high", "medium", "low", "abstain", "certain"]}

    _edit_json(m / "modules/label-groups/schema.json", fn)


def schema_no_implication(m: Path) -> None:
    _edit_json(m / "modules/label-groups/schema.json", lambda d: d.pop("if"))


def replicates_low(m: Path) -> None:
    _edit_yaml(m / "modules/label-groups/module.yml", lambda d: d["judgment"].update(replicates=2))


def no_negative_control(m: Path) -> None:
    (m / "modules/label-groups/controls/negative-shuffled-groups.yml").unlink()


def no_positive_control(m: Path) -> None:
    (m / "modules/label-groups/controls/positive-known-labels.yml").unlink()


def stochastic_no_seed(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(stochastic=True))


def seed_not_in_schema(m: Path) -> None:
    _edit_yaml(
        m / "modules/filter-rows/module.yml", lambda d: d.update(stochastic=True, seed_param="seed")
    )


def prompt_undeclared_var(m: Path) -> None:
    p = m / "modules/label-groups/prompt.md"
    p.write_text(p.read_text() + "\nMatrix: {{ matrix }}\n")


def prompt_unused_var(m: Path) -> None:
    _edit_yaml(
        m / "modules/label-groups/module.yml", lambda d: d["prompt"]["vars"].append("context")
    )


def script_missing(m: Path) -> None:
    (m / "modules/filter-rows/pre.py").unlink()


def pipeline_bad_module_version(m: Path) -> None:
    _edit_yaml(m / "pipelines/toy.yml", lambda d: d["steps"][0].update(module="filter-rows@9.9.9"))


def pipeline_missing_module(m: Path) -> None:
    _edit_yaml(m / "pipelines/toy.yml", lambda d: d["steps"][0].update(module="nope@1.0.0"))


def pipeline_dangling_output(m: Path) -> None:
    _edit_yaml(
        m / "pipelines/toy.yml",
        lambda d: d["steps"][1]["inputs"].update(object="$steps.01_filter.matrix"),
    )


def pipeline_params_fail_schema(m: Path) -> None:
    _edit_yaml(
        m / "pipelines/toy.yml",
        lambda d: d["steps"][0]["params"].update(min_value={"default": "ten"}),
    )


def pipeline_unknown_param(m: Path) -> None:
    _edit_yaml(
        m / "pipelines/toy.yml", lambda d: d["steps"][0]["params"].update(max_value={"default": 5})
    )


def module_mode_unsupported(m: Path) -> None:
    _edit_yaml(m / "modules/filter-rows/module.yml", lambda d: d.update(modes=["pipeline", "open"]))


def vocabulary_unknown(m: Path) -> None:
    _edit_yaml(m / "modules/label-groups/module.yml", lambda d: d.update(vocabulary="cell_types@1"))


def report_consumed(m: Path) -> None:
    def fn(d: dict) -> None:
        d["steps"].append(
            {
                "id": "06_after",
                "module": "summarize-groups@0.1.1",
                "inputs": {"object": "$steps.05_report.report"},
            }
        )

    _edit_yaml(m / "pipelines/toy.yml", fn)


def evidence_not_input_without_pre(m: Path) -> None:
    # label-groups has no pre.* script, so every evidence name must be an input
    _edit_yaml(
        m / "modules/label-groups/module.yml",
        lambda d: d["judgment"].update(evidence=["summary", "guide"]),
    )


def required_input_unwired(m: Path) -> None:
    _edit_yaml(
        m / "modules/filter-rows/module.yml",
        lambda d: d["inputs"].update(reference={"type": "frame", "format": "csv"}),
    )


ERROR_CASES: list[tuple[str, Breaker, str]] = [
    (
        "evidence_not_input_without_pre",
        evidence_not_input_without_pre,
        "judgment.evidence guide is not an input",
    ),
    ("required_input_unwired", required_input_unwired, "leaves input reference of"),
    ("contract_not_1", contract_not_1, "contract must be 1"),
    ("manifest_bad_field", manifest_bad_field, "colour"),
    ("op_not_in_vocab", op_not_in_vocab, "operation explode_rows is not in"),
    ("gate_unresolved", gate_unresolved, "qc.nonexistent@1 does not resolve"),
    ("gate_wrong_version", gate_wrong_version, "obj.feasibility@9 does not resolve"),
    ("judgment_no_prompt", judgment_no_prompt, "requires prompt.md"),
    ("judgment_no_schema", judgment_no_schema, "requires schema.json"),
    ("judgment_no_block", judgment_no_block, "requires the judgment block"),
    ("schema_weakened", schema_weakened, "does not include the base judgment schema"),
    ("schema_no_implication", schema_no_implication, "abstain implication"),
    ("replicates_low", replicates_low, "below the policy minimum"),
    ("no_negative_control", no_negative_control, "lacks a negative control"),
    ("no_positive_control", no_positive_control, "lacks a positive control"),
    ("stochastic_no_seed", stochastic_no_seed, "requires seed_param"),
    (
        "seed_not_in_schema",
        seed_not_in_schema,
        "seed_param seed is missing from params.schema.json",
    ),
    ("prompt_undeclared_var", prompt_undeclared_var, "undeclared variable matrix"),
    (
        "prompt_unused_var",
        prompt_unused_var,
        "declares variable context that the template never uses",
    ),
    ("script_missing", script_missing, "no pre.* script"),
    ("pipeline_bad_module_version", pipeline_bad_module_version, "the repo has filter-rows@0.1.1"),
    ("pipeline_missing_module", pipeline_missing_module, "not in the repo"),
    ("pipeline_dangling_output", pipeline_dangling_output, "which does not exist"),
    ("pipeline_params_fail_schema", pipeline_params_fail_schema, "params fail"),
    ("pipeline_unknown_param", pipeline_unknown_param, "declares parameter max_value, unknown"),
    ("module_mode_unsupported", module_mode_unsupported, "mode open is not supported"),
    ("vocabulary_unknown", vocabulary_unknown, "vocabulary cell_types@1 is not provided"),
    ("report_consumed", report_consumed, "report outputs cannot be inputs"),
]


@pytest.fixture
def method_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "method"
    shutil.copytree(METHOD_TEMPLATE, dest)
    return dest


def test_toy_method_passes_lint(method_copy: Path) -> None:
    report = lint_path(method_copy)
    assert report.ok, report.render()
    assert any("no planted control" in w for w in report.warnings)


@pytest.mark.parametrize("name,breaker,expected", ERROR_CASES, ids=[c[0] for c in ERROR_CASES])
def test_lint_error_classes(method_copy: Path, name: str, breaker: Breaker, expected: str) -> None:
    breaker(method_copy)
    report = lint_path(method_copy)
    assert not report.ok, f"{name}: expected an error"
    assert any(expected in e for e in report.errors), f"{name}: {report.errors}"


def test_optional_input_may_stay_unwired(method_copy: Path) -> None:
    """A module input marked optional needs no pipeline wiring; the script sees no entry for it."""
    _edit_yaml(
        method_copy / "modules/filter-rows/module.yml",
        lambda d: d["inputs"].update(
            reference={"type": "frame", "format": "csv", "optional": True}
        ),
    )
    report = lint_path(method_copy)
    assert report.ok, report.render()


def test_pre_script_may_produce_evidence_that_is_not_an_input(method_copy: Path) -> None:
    """With a pre.* script the judgment may declare evidence tables the script writes (design 3.5
    step 2), such as a guide table beside the items table."""
    (method_copy / "modules/label-groups/pre.py").write_text("#!/usr/bin/env python3\n")
    _edit_yaml(
        method_copy / "modules/label-groups/module.yml",
        lambda d: d["judgment"].update(evidence=["summary", "guide"]),
    )
    report = lint_path(method_copy)
    assert report.ok, report.render()


def test_lint_single_module_dir(method_copy: Path) -> None:
    report = lint_path(method_copy / "modules" / "label-groups")
    assert report.ok, report.render()


def test_warning_decision_points_empty(method_copy: Path) -> None:
    _edit_yaml(
        method_copy / "modules/compare-groups/module.yml", lambda d: d.update(decision_points=[])
    )
    report = lint_path(method_copy)
    assert report.ok
    assert any("decision_points is empty" in w for w in report.warnings)


def test_warning_in_scope_predicate_unlisted(method_copy: Path) -> None:
    _edit_yaml(
        method_copy / "modules/compare-groups/module.yml",
        lambda d: d.update(gates=["obj.feasibility@1"]),
    )
    report = lint_path(method_copy)
    assert report.ok
    assert any("toy.replication_unit@1 is not listed" in w for w in report.warnings)


def test_warning_holdout_fixture(method_copy: Path) -> None:
    from stringency.config import Design

    h = yaml.safe_load(
        (method_copy / "modules/label-groups/controls/positive-known-labels.yml").read_text()
    )
    design = Design.model_validate(
        {
            "design": 1,
            "units": {"observation": "row", "sample": "unit"},
            "factors": {},
            "replication_unit": "unit",
            "holdout": [{"type": "frame", "blake3": h["fixture"]["input"]["blake3"]}],
        }
    )
    report = lint_path(method_copy, design=design)
    assert any("design.holdout" in w for w in report.warnings)


def test_cli_lint_and_plugins_list(method_copy: Path) -> None:
    from typer.testing import CliRunner

    from stringency.cli.app import app

    r = CliRunner().invoke(app, ["lint", str(method_copy)])
    assert r.exit_code == 0, r.output
    (method_copy / "modules/label-groups/controls/negative-shuffled-groups.yml").unlink()
    r = CliRunner().invoke(app, ["lint", str(method_copy)])
    assert r.exit_code == 15
    assert "lacks a negative control" in r.output
    r = CliRunner().invoke(app, ["plugins", "list"])
    assert r.exit_code == 0
    assert "stringency-toy" in r.output and "toy.replication_unit" in r.output
    assert "min_n_per_group=2" in r.output


def test_cli_lint_accepts_method_spec_with_tag(method_repo: MethodRepo) -> None:
    """I6: `lint <repo>@<tag>` clones the tag into a temporary directory, as `init` does."""
    from typer.testing import CliRunner

    from stringency.cli.app import app
    from stringency.git import tag

    r = CliRunner().invoke(app, ["lint", method_repo.spec])
    assert r.exit_code == 0, r.output
    assert "no policy.yml" not in r.output
    # break the tree after the tag: the new tag fails, the old tag still lints clean
    (method_repo.path / "modules/label-groups/controls/negative-shuffled-groups.yml").unlink()
    method_repo.commit("drop the negative control")
    tag(method_repo.path, "v0.1.1")
    r = CliRunner().invoke(app, ["lint", f"{method_repo.path}@v0.1.1"])
    assert r.exit_code == 15 and "lacks a negative control" in r.output
    r = CliRunner().invoke(app, ["lint", method_repo.spec])
    assert r.exit_code == 0, r.output
    r = CliRunner().invoke(app, ["lint", f"{method_repo.path}@nope"])
    assert r.exit_code == 15 and "could not clone" in (r.output + str(r.stderr))


def test_warning_untitled_steps_when_pipeline_has_a_skill(method_copy: Path) -> None:
    assert not any("no title" in w for w in lint_path(method_copy).warnings)
    (method_copy / "skills").mkdir()
    (method_copy / "skills" / "toy.yml").write_text("pipeline: toy\n")
    pf = method_copy / "pipelines" / "toy.yml"
    pf.write_text(pf.read_text().replace("    title: Label the groups\n", ""))
    report = lint_path(method_copy)
    assert report.ok
    assert any(
        "skills/toy.yml exists but steps have no title: 03_label" in w for w in report.warnings
    )
    # every step titled: no warning
    pf.write_text(
        pf.read_text().replace(
            "  - id: 03_label\n", "  - id: 03_label\n    title: Label the groups\n"
        )
    )
    assert not any("no title" in w for w in lint_path(method_copy).warnings)
