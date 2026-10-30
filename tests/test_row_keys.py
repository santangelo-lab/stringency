"""L138 (the row key) and L142 (the numeral check's exemptions), 2026-10-29.

A table whose first column repeats is keyed by the shortest unique prefix of its columns, so
every row is addressable as `<k1>|<k2>`; a module output may declare its key; an answer's
`--cite` and a proposal's `--cite` resolve the joined key; a block on a citation says the key
form and the keys nearest the miss; a judgment reference resolves a two-column key. A numeral
that is not a measurement (a design level, a key value, a parameter value of the cited step, a
numeral of the question, a year, a count of animals) is left unchecked and listed in the
qualifier; each class has a must-fire and a must-pass case."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from stringency import git
from stringency.answers import parse_cite
from stringency.citations import _find_row
from stringency.config import Design, Factor
from stringency.exit_codes import ConfigError
from stringency.predicates import GateContext, registry
from stringency.predicates.context import EvidenceTable, OutputBundle, OutputInfo
from stringency.project import Project
from stringency.prompting import evidence_suffix
from stringency.review_render import _table_lines
from stringency.tables import load_table, row_keys
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.helpers import judgment, make_ctx, replicate
from tests.test_open_answers import _answer
from tests.test_open_init import delivered_process, open_project
from tests.test_run import cli

STRATIFIED = (
    "cluster\tstratum\tcell_type\tpct\n"
    "1\tdomain_1\tenterocyte\t16.561\n"
    "1\tdomain_2\tenterocyte\t61.031\n"
    "9\tdomain_1\tenterocyte\t0.308\n"
    "9\tdomain_2\tenterocyte\t36.68\n"
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


# -- the key -----------------------------------------------------------------------------------


def test_a_stratified_table_is_keyed_by_two_columns_and_keeps_every_row(tmp_path: Path) -> None:
    t = load_table(_write(tmp_path, "comp.tsv", STRATIFIED), "comp")
    assert t.key_columns == ("cluster", "stratum") and t.key_column == "cluster|stratum"
    assert list(t.rows) == ["1|domain_1", "1|domain_2", "9|domain_1", "9|domain_2"]
    # key values stay text as read; the other cells are coerced
    assert t.rows["9|domain_2"] == {
        "cluster": "9",
        "stratum": "domain_2",
        "cell_type": "enterocyte",
        "pct": 36.68,
    }
    assert t.note is None


def test_a_per_replicate_table_is_keyed_by_replicate_and_pair(tmp_path: Path) -> None:
    text = "replicate,pair,distance\nr1,1,4.5\nr1,2,3.0\nr2,1,5.25\nr2,2,2.0\n"
    t = load_table(_write(tmp_path, "pairs.csv", text), "pairs")
    assert t.key_column == "replicate|pair"
    assert list(t.rows) == ["r1|1", "r1|2", "r2|1", "r2|2"]
    assert t.rows["r2|1"]["distance"] == 5.25


def test_a_unique_first_column_keeps_its_keys(tmp_path: Path) -> None:
    text = "group,n,mean\nA,3,74.31\nB,3,15.09\n007,2,1.5\n"
    t = load_table(_write(tmp_path, "g.csv", text), "g")
    assert t.key_column == "group" and t.key_columns == ("group",)
    assert list(t.rows) == ["A", "B", "007"]
    assert t.rows["007"]["group"] == "007" and t.rows["A"]["n"] == 3


def test_rows_repeated_in_full_are_numbered(tmp_path: Path) -> None:
    text = "a,b\n1,x\n1,x\n2,y\n1,x\n"
    t = load_table(_write(tmp_path, "d.csv", text), "d")
    assert t.key_column == "a|b"
    assert list(t.rows) == ["1|x", "1|x#2", "2|y", "1|x#3"]
    assert t.note is not None and "2 row(s) repeat another row in full" in t.note


def test_a_declared_key_replaces_the_prefix_rule(tmp_path: Path) -> None:
    p = _write(tmp_path, "comp.tsv", STRATIFIED)
    t = load_table(p, "comp", key=["stratum", "cluster"])
    assert t.key_column == "stratum|cluster" and "domain_2|9" in t.rows
    with pytest.raises(ConfigError, match="not in the table"):
        load_table(p, "comp", key=["domain"])
    # a declared key that repeats numbers the repeat
    t = load_table(p, "comp", key=["cluster"])
    assert list(t.rows) == ["1", "1#2", "9", "9#2"] and "repeats on 2 row(s)" in (t.note or "")
    cols, keys, _ = row_keys(["a", "b"], [{"a": "1", "b": "x"}, {"a": "2", "b": "x"}])
    assert cols == ["a"] and keys == ["1", "2"]


def test_the_cite_parse_takes_a_joined_key() -> None:
    aid = "01M64C3ASTVHB09FAGK3RTRPZK"
    c = parse_cite(f"{aid}:1|domain_2:pct")
    assert (c.artifact_id, c.row, c.column) == (aid, "1|domain_2", "pct")
    assert parse_cite(f"{aid}:1|domain_2").column is None
    with pytest.raises(ConfigError, match=r"<k1>\|<k2>"):
        parse_cite("not-an-id:1|2")


def test_a_proposal_citation_resolves_the_joined_key_never_a_part_by_position() -> None:
    rows = [
        {"cluster": "1", "stratum": "d1", "pct": "16.5"},
        {"cluster": "1", "stratum": "d2", "pct": "61.0"},
        {"cluster": "9", "stratum": "d1", "pct": "0.3"},
    ]
    assert _find_row(rows, "1|d2") == rows[1]
    assert _find_row(rows, "1") is None  # once the first row by position
    assert _find_row(rows, "3") == rows[2]  # a position still resolves when it names no key
    unique = [{"group": "A", "n": "3"}, {"group": "B", "n": "4"}]
    assert _find_row(unique, "B") == unique[1]


# -- the judgment's citation ------------------------------------------------------------------


def test_a_judgment_reference_resolves_a_two_column_key(project: Project, tmp_path: Path) -> None:
    table = load_table(_write(tmp_path, "comp.tsv", STRATIFIED), "comp")

    def ctx(row: str) -> GateContext:
        ref = {"table": "comp", "row": row, "column": "pct", "value": 36.68}
        bundle = OutputBundle(
            outputs={"judgments": OutputInfo("judgments", "judgments", "x", "blake3:00")},
            replicates=(replicate([judgment("A", "abundant", supporting=[ref])]),),
            replicate_valid=(True,),
            evidence_tables={"comp": table},
            items=("A",),
        )
        return make_ctx(project, "03_label", phase="post", output=bundle)

    spec = registry.get("judg.evidence_exists")
    assert spec is not None
    assert spec.fn(ctx("9|domain_2")).fired is False
    assert spec.fn(ctx("9")).fired is True
    # the request says how the row is named, only for a table keyed by more than one column
    criteria = project.policy.confidence_criteria
    text = evidence_suffix(criteria, None, {"comp": table.key_columns, "summary": ("group",)})
    assert "In comp, the key is the values of cluster, stratum joined with `|`" in text
    assert "summary" not in text
    assert evidence_suffix(criteria, None, {"summary": ("group",)}) == evidence_suffix(criteria)
    # the hold packet leads such a row with its key
    lines = _table_lines(
        {"comp": {"9|domain_2": dict(table.rows["9|domain_2"])}}, "evidence table", {"comp": table}
    )
    assert lines[0] == "evidence table comp (row key cluster|stratum):"
    assert lines[1].startswith("  [9|domain_2] cluster=9")


# -- answers -----------------------------------------------------------------------------------


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    return q


def _stratified_exec(q: Project, tmp_path: Path, question: str) -> tuple[str, str]:
    qid = json.loads(cli(q, "ask", question, "--json").output)["question_id"]
    script = tmp_path / "strat.py"
    script.write_text(
        "import json, sys\njob = json.load(sys.stdin)\n"
        f"open(job['outputs']['comp'], 'w').write({STRATIFIED!r})\n"
    )
    r = cli(q, "exec", str(script), "--out", "comp=table", "--allow-local", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    return qid, json.loads(r.output)["artifacts"][0]["artifact_id"]


def test_an_answer_cites_a_row_of_a_stratified_table_and_a_miss_says_the_key_form(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    qid, aid = _stratified_exec(q, tmp_path, "How does cluster 9 change in domain_2?")
    text = tmp_path / "a.md"
    # a citation without a row takes every row, none lost
    out = json.loads(_answer(q, qid, "No numbers here.", aid, path=text).output)
    assert sorted(out["cells"][aid]) == ["1|domain_1", "1|domain_2", "9|domain_1", "9|domain_2"]
    # the joined key resolves; the cluster id 9 is a key value, left unchecked and named
    r = _answer(q, qid, "Cluster 9 is 36.68 percent.", f"{aid}:9|domain_2:pct", path=text)
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["cells"] == {aid: {"9|domain_2": {"pct": 36.68}}}
    assert out["numerals"]["not_checked"] == [{"numeral": "9", "class": "key"}]
    assert (out["numerals"]["matched"], out["numerals"]["total"]) == (1, 1)
    assert out["qualifier"].endswith("| numerals not checked: 9")
    assert out["provenance"]["keys"] == {aid: "cluster|stratum"}
    answer_id = out["answer_id"]
    # the first column alone names no row: blocked, with the key form and the nearest keys
    r = _answer(q, qid, "Cluster 1 is 61.031 percent.", f"{aid}:1:pct", path=text)
    assert r.exit_code == 12, r.output
    out = json.loads(r.output)
    assert out["missing"] == [f"{aid}:1"]
    assert out["cite_help"] == [
        {
            "cite": f"{aid}:1",
            "table": "comp",
            "key_columns": ["cluster", "stratum"],
            "form": "<id>:<cluster>|<stratum>[:<column>]",
            "near": ["1|domain_1", "1|domain_2", "9|domain_1", "9|domain_2"],
        }
    ]
    blocked = next(b for b in out["blocked"] if "ans.cited_missing" in b)
    assert "rows of comp are cited as <id>:<cluster>|<stratum>[:<column>]" in blocked
    # present heads the cited rows with the joined key
    shown = json.loads(cli(q, "present", "--answer", answer_id, "--json").output)
    sec = next(s for s in shown["sections"] if s["title"] == "comp (cited rows)")
    assert sec["columns"][0] == "cluster|stratum" and sec["rows"][0][0] == "9|domain_2"
    details = cli(q, "present", "--answer", answer_id, "--details").output
    assert "numerals not checked: 9" in details


def test_a_key_declared_in_module_yml_is_the_key_an_answer_cites(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    mfile = method_repo.path / "modules" / "compare-groups" / "module.yml"
    m = yaml.safe_load(mfile.read_text())
    m["outputs"]["comparison_table"]["key"] = ["contrast", "n_a"]
    mfile.write_text(yaml.safe_dump(m, sort_keys=False))
    sha = method_repo.commit("declare the comparison table's key")
    git.tag(method_repo.path, "v0.1.1")
    repo = MethodRepo(method_repo.path, "v0.1.1", sha)
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    qid = json.loads(cli(q, "ask", "Which group is higher?", "--json").output)["question_id"]
    r = cli(q, "call", "compare-groups", "--question", qid, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    aid = json.loads(r.output)["artifacts"][0]["artifact_id"]
    cells = json.loads(_answer(q, qid, "None.", aid, path=tmp_path / "a.md").output)["cells"]
    keys = sorted(cells[aid])
    assert keys and all(k.count("|") == 1 for k in keys), keys
    k = next(k for k in keys if k.startswith("A_vs_B|"))
    r = _answer(q, qid, "A and B differ.", f"{aid}:{k}:diff", path=tmp_path / "a.md")
    assert r.exit_code == 0, r.output
    r = _answer(q, qid, "A and B differ.", f"{aid}:A_vs_B:diff", path=tmp_path / "a.md")
    assert r.exit_code == 12
    assert json.loads(r.output)["cite_help"][0]["form"] == "<id>:<contrast>|<n_a>[:<column>]"


def test_lint_reads_a_declared_key(tmp_path: Path, method_repo: MethodRepo) -> None:
    from stringency.lint import LintReport, lint_module
    from stringency.modules import ModuleIndex

    mfile = method_repo.path / "modules" / "compare-groups" / "module.yml"
    m = yaml.safe_load(mfile.read_text())
    m["outputs"]["comparison_table"]["key"] = ["contrast", "contrast"]
    m["inputs"]["object"]["key"] = ["group"]
    mfile.write_text(yaml.safe_dump(m, sort_keys=False))
    module = ModuleIndex(method_repo.path).require("compare-groups@0.1.1")
    report = LintReport()
    lint_module(module, report, plugin=None, policy=None)
    assert any("outputs.comparison_table.key must name" in e for e in report.errors)
    assert any("inputs.object.key is read on outputs only" in w for w in report.warnings)


# -- L142: the numeral check's exemption classes -----------------------------------------------

CITED = EvidenceTable(
    name="comp",
    key_column="cluster|stratum",
    columns=("cluster", "stratum", "pct"),
    rows={"9|domain_2": {"pct": 36.68}},
    key_columns=("cluster", "stratum"),
)


def _numeral_ctx(project: Project, text: str, **sources: object) -> GateContext:
    from stringency.actions import Action

    action = Action(
        action_id="ANSWER",
        run_id="RUN",
        step_id="answer",
        attempt=0,
        operation="answer",
        module="answer",
        parameters={},
        param_source={},
        inputs={},
        input_digest="blake3:" + "00" * 32,
        params_hash="blake3:" + "00" * 32,
        proposed_by="agent",
    )
    bundle = OutputBundle(
        outputs={},
        prose=text,
        evidence_tables={"comp": CITED},
        observed={"missing": [], "numeral_sources": sources},
    )
    ctx = make_ctx(project, "01_filter", phase="post", action=action, output=bundle)
    design = Design(
        factors={"timepoint_h": Factor(column="timepoint_h", levels=["control", "6", "24", "48"])}
    )
    return replace(ctx, design=design)


# (class, must-pass text, must-fire text, sources)
EXEMPTIONS: list[tuple[str, str, str, dict[str, object]]] = [
    ("level", "At 24 hours it is 36.68.", "At 30 hours it is 36.68.", {}),
    ("key", "Cluster 9 is 36.68.", "Cluster 8 is 36.68.", {"key": ["9", "domain_2"]}),
    (
        "param",
        "At FDR 0.05 over clusters 0,1 and 11 it is 36.68.",
        "At FDR 0.01 it is 36.68.",
        {"param": ["0.05", "cluster in 0,1,9,11,14", "propeller,edger_ql"]},
    ),
    (
        "question",
        "At 72 hours in ROSC it is 36.68.",
        "At 96 hours in ROSC it is 36.68.",
        {"question": "what does 72 hours in ROSC show?"},
    ),
    ("year", "In the 2024 data it is 36.68.", "In the 2300 data it is 36.68.", {}),
    ("count", "Over 2 animals it is 36.68.", "Over 2 cells it is 36.68.", {}),
]


@pytest.mark.parametrize("cls,ok,bad,sources", EXEMPTIONS, ids=[e[0] for e in EXEMPTIONS])
def test_each_exemption_class_must_pass_and_must_fire(
    project: Project, cls: str, ok: str, bad: str, sources: dict[str, object]
) -> None:
    spec = registry.get("ans.numeral_unmatched")
    assert spec is not None and spec.version == 2
    assert spec.fn(_numeral_ctx(project, ok, **sources)).fired is False, ok
    v = spec.fn(_numeral_ctx(project, bad, **sources))
    assert v.fired is True, bad
    assert "36.68" not in (v.reason or "")  # the measurement matched its cell
    from stringency.predicates.engine.ans import EXEMPT_CLASSES

    want = {
        "year": "(nearest: a year (1900 to 2100))",
        "count": "cells is not a unit word of a count before a unit word (animals, punches, "
        "replicates)",
    }.get(cls, f"(nearest: {EXEMPT_CLASSES[cls]}")
    assert want in (v.reason or ""), v.reason


def test_the_reason_names_the_nearest_class_and_a_measurement_still_blocks(
    project: Project,
) -> None:
    spec = registry.get("ans.numeral_unmatched")
    assert spec is not None
    v = spec.fn(_numeral_ctx(project, "At 24 hours it is 36.7 against 52.040.", param=["0.05"]))
    assert v.fired is True
    assert v.reason == (
        "a numeral in the answer matches no cited cell: "
        "52.040 (nearest: a level of a design factor (48))"
    )
    assert v.evidence["not_checked"] == [{"numeral": "24", "class": "level"}]
    v = spec.fn(_numeral_ctx(project, "Over 3 cells it is 36.68."))
    assert "(nearest: a level of a design factor (6); cells is not a unit word" in (v.reason or "")
