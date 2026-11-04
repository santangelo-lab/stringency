"""The method-repo template: lint clean, and its two example environments' lockfiles exist
where the manifest says (the beta-tester package, M3)."""

from __future__ import annotations

from pathlib import Path

import yaml

from stringency.lint import lint_path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "method-repo"


def test_template_lints_clean_and_names_its_example_environments() -> None:
    report = lint_path(TEMPLATE)
    assert not report.errors and not report.warnings, report.render()
    envs = yaml.safe_load((TEMPLATE / "envs" / "manifest.yml").read_text())["environments"]
    assert set(envs) == {"example-py", "example-r"}
    for spec in envs.values():
        assert (TEMPLATE / spec["lock"]).is_file()
    assert (TEMPLATE / "envs" / "example-py" / "pyproject.toml").is_file()
    assert (
        TEMPLATE / "envs" / "example-r" / ".Rprofile"
    ).read_text().strip() == 'source("renv/activate.R")'
    assert (TEMPLATE / "envs" / "example-r" / "renv" / "activate.R").is_file()
