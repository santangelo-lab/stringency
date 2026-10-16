"""Data egress assessment (backlog L1): component classes, the script scan, the fingerprint,
and the two ceiling predicates (must-fire and must-pass)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from stringency.egress import (
    EgressAssessment,
    assess,
    render_markdown,
    scan_module,
    scan_text,
)
from stringency.predicates.registry import registry
from stringency.project import Project
from tests.helpers import make_ctx


def _assess(project: Project, **kw: object) -> EgressAssessment:
    args: dict[str, object] = {
        "steps": project.pipeline.steps,
        "modules": {m.ref: m for m in project.modules.all()},
        "harness": "subagent",  # the CLI default; the test project binds mock
        "execution": project.config.execution,
        "max_class": None,
    }
    args.update(kw)
    return assess(**args)  # type: ignore[arg-type]


def _by_key(a: EgressAssessment) -> dict[str, int]:
    return {c.key: c.cls for c in a.components}


# -- components ------------------------------------------------------------------------


def test_toy_defaults_hosted_operator(project: Project) -> None:
    a = _assess(project)
    k = _by_key(a)
    assert k["harness"] == 3  # subagent: evidence tables to the operator's model
    assert k["operator.session"] == 3
    assert k["operator.steps"] == 4
    assert a.assessed_class == 4
    assert a.within is None and a.over == ()
    steps = next(c for c in a.components if c.key == "operator.steps").steps
    # 01_filter is `runner: operator`; 04_compare is `runner: engine`; 03_label is judgment
    assert any(s.startswith("01_filter") for s in steps)
    assert not any(s.startswith(("03_label", "04_compare")) for s in steps)


def test_harness_classes(project: Project) -> None:
    assert _by_key(_assess(project, harness="mock"))["harness"] == 0
    assert _by_key(_assess(project, harness="api"))["harness"] == 3
    assert _by_key(_assess(project, harness="openai-compatible"))["harness"] == 3


def test_no_harness_row_without_a_judgment_step(project: Project) -> None:
    steps = [s for s in project.pipeline.steps if s.id != "03_label"]
    assert "harness" not in _by_key(_assess(project, steps=steps))


def test_local_operator_and_mock_is_class_zero(project: Project) -> None:
    a = _assess(project, harness="mock", operator="none", max_class=0)
    assert a.assessed_class == 0
    assert a.within is True


def test_ceiling_exceeded_names_components(project: Project) -> None:
    a = _assess(project, harness="mock", max_class=2)
    assert a.within is False
    assert {c.key for c in a.over} == {"operator.session", "operator.steps"}


def test_undeclared_network_module_counts_as_four(project: Project, tmp_path: Path) -> None:
    mod = project.modules.require("summarize-groups@0.1.1")
    hits = scan_text("import requests\nrequests.get(u)\n", ".py", "pre.py")
    a = _assess(project, harness="mock", operator="none", scans={mod.ref: hits})
    row = next(c for c in a.components if c.key == f"module:{mod.ref}")
    assert row.cls == 4 and row.basis == "scanned, undeclared"
    assert row.evidence == ("pre.py:1 requests", "pre.py:2 requests")
    assert a.assessed_class == 4


# -- scan ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,suffix,hit",
    [
        ("import requests", ".py", "requests"),
        ("from urllib.request import urlopen", ".py", "urllib"),
        ("m = AutoModel.from_pretrained('x')", ".py", "model hub"),
        ("import anthropic", ".py", "LLM client"),
        ("res <- httr::GET(u)", ".r", "httr"),
        ("download.file(u, dest)", ".r", "download.file"),
        ("curl -sL $U > ref.gtf", ".sh", "curl"),
        ("  wget $U", ".sh", "wget"),
        ("nextflow run nf-core/rnaseq -r 3.14", ".sh", "nextflow run"),
        ("aws s3 cp x s3://b/", ".sh", "cloud copy"),
        ("REF = 'https://example.org/ref.fa'", ".py", "URL"),
    ],
)
def test_scan_hits(text: str, suffix: str, hit: str) -> None:
    hits = scan_text(text, suffix, "s")
    assert [h.pattern for h in hits] == [hit]


@pytest.mark.parametrize(
    "text,suffix",
    [
        ("# see https://example.org for the method", ".py"),
        ("import pandas as pd\ndf = pd.read_csv(path)", ".py"),
        ("x <- read.csv(path)  ", ".r"),
        ("echo done; cat a > b", ".sh"),
        ("// https://nextflow.io", ".nf"),
        ("recurl = 1", ".py"),
    ],
)
def test_scan_misses(text: str, suffix: str) -> None:
    assert scan_text(text, suffix, "s") == []


def test_scan_module_reads_scripts_and_skips_controls(tmp_path: Path) -> None:
    d = tmp_path / "m"
    (d / "controls").mkdir(parents=True)
    (d / "pre.py").write_text("import json\n")
    (d / "lib").mkdir()
    (d / "lib" / "fetch.R").write_text("download.file(u, d)\n")
    (d / "controls" / "gen.py").write_text("import requests\n")
    (d / "notes.md").write_text("curl https://x\n")
    assert [h.describe() for h in scan_module(d)] == ["lib/fetch.R:1 download.file"]


def test_toy_modules_do_not_reach_the_network(project: Project) -> None:
    for m in project.modules.all():
        assert scan_module(m.path) == [], m.ref


# -- fingerprint and report ------------------------------------------------------------


def test_fingerprint_stable_and_sensitive(project: Project) -> None:
    a1, a2 = _assess(project, max_class=4), _assess(project, max_class=4)
    assert a1.fingerprint == a2.fingerprint
    assert _assess(project, max_class=4, harness="mock").fingerprint != a1.fingerprint
    assert _assess(project, max_class=3).fingerprint != a1.fingerprint
    assert _assess(project, max_class=4, operator="local").fingerprint != a1.fingerprint
    # the previous ceiling is shown in the report but does not change the fingerprint
    assert _assess(project, max_class=4, previous_max_class=1).fingerprint == a1.fingerprint


def test_report_states_facts(project: Project) -> None:
    a = _assess(project, max_class=1, previous_max_class=0)
    text = render_markdown(a, project_id="P", assessed_at="2026-10-16T00:00:00Z")
    assert "ceiling: class 1 reference" in text
    assert "the last acknowledged report had class 0 none" in text
    assert "exceeds the ceiling: " in text
    assert "judgment harness subagent: class 3 derived" in text
    assert "not assessed:" in text
    j = a.to_json()
    assert j["assessed_class"] == 4 and j["within"] is False
    assert j["fingerprint"].startswith("blake3:")


# -- predicates ------------------------------------------------------------------------


def _ctx_with(project: Project, phase: str, a: EgressAssessment | None):  # type: ignore[no-untyped-def]
    ctx = make_ctx(project, "01_filter", phase=phase)
    return dataclasses.replace(ctx, project=dataclasses.replace(ctx.project, egress=a))


@pytest.mark.parametrize(
    "pid,phase",
    [("init.egress_exceeds_ceiling", "init"), ("prov.egress_exceeds_ceiling", "run_open")],
)
def test_egress_predicates_must_fire_and_pass(project: Project, pid: str, phase: str) -> None:
    spec = registry.get(pid)
    assert spec is not None and spec.in_phase(phase) and spec.invariant  # type: ignore[arg-type]
    over = spec.fn(_ctx_with(project, phase, _assess(project, max_class=0)))
    assert over.fired and "exceeds the project ceiling class 0 none" in (over.reason or "")
    assert {o["key"] for o in over.evidence["over"]} >= {"operator.steps"}
    assert not spec.fn(_ctx_with(project, phase, _assess(project, max_class=4))).fired
    assert not spec.fn(_ctx_with(project, phase, _assess(project))).fired  # no ceiling
    assert not spec.fn(_ctx_with(project, phase, None)).fired  # no assessment


def test_lint_warns_on_a_module_that_reaches_the_network(project: Project) -> None:
    from stringency.lint import LintReport, lint_module

    mod = project.modules.require("summarize-groups@0.1.1")
    (mod.path / "fetch.py").write_text("import requests\n")
    report = LintReport()
    lint_module(mod, report, plugin=project.plugin, policy=project.policy)
    assert report.ok
    assert any("reach the network but the module declares no egress" in w for w in report.warnings)
