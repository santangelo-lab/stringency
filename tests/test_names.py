"""Names (design 3.1, 2026-11-10; PLAN L163, L129): a `text:` parameter says how this dataset
labels its own contents. The benchmark's DE test replicate declared a factor column, a
reference level and a cell type for a pipeline that fixed all three; nothing could be told a
name. The owner's five decisions of 2026-11-10 are what these tests hold: a declared name is
admitted under every profile; an agent's proposal follows the profile (a hold where the agent
may choose, a block where parameters are locked); a column and a value of a column are
checked against the inputs' summaries; a required name is `unset` until given, and no step
runs on `unset`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from stringency import git
from stringency.exit_codes import ConfigError
from stringency.names import Resolution, resolve, resolve_step
from stringency.pipelines import UNSET, ParamDecl, Pipeline
from stringency.project import InitRequest, Project, check_declarations, init_project
from stringency.review import record_review
from stringency.state import ObjectState
from tests.conftest import MethodRepo, accept_hold, write_declarations
from tests.test_declared_params import OBJECTIVE
from tests.test_run import MOCK, cli

NAMES = {
    "min_value": {"default": 10, "range": [0, 40]},
    "keep_column": {"default": "", "text": "column"},
    "keep_value": {"default": "", "text": {"value_of": "keep_column"}},
    "tag_prefix": {"default": "r", "text": "prefix"},
}


def _method(method_repo: MethodRepo, params: dict[str, Any], tag: str = "v0.1.1") -> MethodRepo:
    """The toy method with name parameters on `01_filter` of `toy-engine`: the module's schema
    gains the text properties (its script reads `min_value` alone), the pipeline declares them."""
    schema = method_repo.path / "modules" / "filter-rows" / "params.schema.json"
    doc = json.loads(schema.read_text())
    for name in params:
        doc["properties"].setdefault(name, {"type": "string"})
    schema.write_text(json.dumps(doc, indent=2))
    pipe = method_repo.path / "pipelines" / "toy-engine.yml"
    p = yaml.safe_load(pipe.read_text())
    p["steps"][0]["params"] = params
    pipe.write_text(yaml.safe_dump(p, sort_keys=False))
    sha = method_repo.commit("names on 01_filter")
    git.tag(method_repo.path, tag)
    return MethodRepo(method_repo.path, tag, sha)


def _request(
    tmp_path: Path, toy_data: Path, repo: MethodRepo, name: str, params: dict[str, Any], **kw: Any
) -> InitRequest:
    decl = write_declarations(
        tmp_path / f"decl-{name}",
        toy_data,
        objective={**OBJECTIVE, **({"params": params} if params else {})},
    )
    req = InitRequest(
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
    for k, v in kw.items():
        setattr(req, k, v)
    return req


def _project(
    tmp_path: Path, toy_data: Path, repo: MethodRepo, name: str, params: dict[str, Any], **kw: Any
) -> Project:
    p = init_project(_request(tmp_path, toy_data, repo, name, params, **kw))
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    return p


def _frame(levels: bool = True) -> ObjectState:
    cols: dict[str, dict[str, Any]] = {
        "row_id": {"dtype": "string", "n_unique": 50},
        "group": {"dtype": "string", "n_unique": 3},
        "unit": {"dtype": "string", "n_unique": 9},
        "value": {"dtype": "number", "n_unique": 50},
    }
    if levels:
        cols["group"]["levels"] = ["A", "B", "C"]
    return ObjectState(type="frame", digest="b3:0", summary={"fields": {"columns": cols}})


@pytest.fixture(autouse=True)
def _reviewer_at_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


# -- the declaration ---------------------------------------------------------------------


def test_a_name_is_declared_with_text_and_is_not_fixed() -> None:
    column = ParamDecl(default="", text="column")
    assert column.is_name and not column.fixed and column.name_kind == "column"
    value = ParamDecl.model_validate({"default": "", "text": {"value_of": "keep_column"}})
    assert value.name_kind == "value" and value.value_of == "keep_column"
    required = ParamDecl.model_validate({"text": "column", "required": True})
    assert required.default == UNSET and required.required
    assert ParamDecl(default=5).fixed and not ParamDecl(default=5).is_name
    for bad, why in [
        ({"default": "", "text": "column", "options": ["a"]}, "no range and no options"),
        ({"default": "", "text": "column", "range": [0, 1]}, "no range and no options"),
        ({"default": "", "text": "label"}, "text is one of column, prefix"),
        ({"default": 3, "text": "column"}, "a name's default is text"),
        ({"default": "x", "required": True, "text": "column"}, "declares no default"),
        ({"default": 3, "required": False, "range": [0, 5], "text": None}, None),
    ]:
        if why is None:
            ParamDecl.model_validate(bad)
            continue
        with pytest.raises(ValidationError, match=why):
            ParamDecl.model_validate(bad)
    with pytest.raises(ValidationError, match="`required` is read only on a name"):
        ParamDecl.model_validate({"required": True})


def test_value_of_names_a_column_parameter_of_the_same_step() -> None:
    def pipeline(params: dict[str, Any]) -> Pipeline:
        return Pipeline.model_validate(
            {
                "pipeline": 1,
                "name": "p",
                "version": "0.1.0",
                "domain": "stringency-toy",
                "steps": [{"id": "01", "module": "m@0.1.0", "params": params}],
            }
        )

    ok = pipeline({"keep_column": {"default": "", "text": "column"}, "val": NAMES["keep_value"]})
    assert ok.step("01").params["val"].value_of == "keep_column"
    with pytest.raises(ValidationError, match="value_of names keep_column, which is not"):
        pipeline({"val": NAMES["keep_value"]})
    with pytest.raises(ValidationError, match="which is not a `text: column` parameter"):
        pipeline({"keep_column": {"default": "r", "text": "prefix"}, "val": NAMES["keep_value"]})
    # a required name written with no default is a declaration, not a fixed mapping
    req = pipeline({"col": {"text": "column", "required": True}})
    assert req.step("01").params["col"].default == UNSET


# -- resolution --------------------------------------------------------------------------


def test_a_column_and_a_value_resolve_against_the_summary() -> None:
    read = {"groups": _frame()}
    col = ParamDecl(default="", text="column")
    val = ParamDecl.model_validate(NAMES["keep_value"])
    r = resolve("keep_column", col, "group", {}, read)
    assert (r.status, r.where, r.detail["levels"]) == ("resolved", "groups", ["A", "B", "C"])
    assert r.says() == "keep_column = 'group', a column of groups (3 values: A, B, C)"
    r = resolve("keep_column", col, "Group", {}, read)
    assert r.status == "missing" and r.nearest[0] == "group"
    assert "that does not exist; nearest: group" in r.says()
    assert resolve("keep_column", col, "", {}, read).status == "empty"
    assert resolve("keep_column", col, UNSET, {}, read).status == "unset"
    # a value: one level, several separated by commas, one that is not there
    values = {"keep_column": "group"}
    assert resolve("keep_value", val, "B", values, read).status == "resolved"
    assert resolve("keep_value", val, "A, C", values, read).status == "resolved"
    r = resolve("keep_value", val, "A,D", values, read)
    assert r.status == "missing" and r.detail == {"missing": ["D"]} and r.column == "group"
    assert Resolution.from_json(r.to_json()) == r
    # not checked, and said so: no levels in the summary, no column named, no summary at all
    r = resolve("keep_value", val, "u1", {"keep_column": "unit"}, read)
    assert (r.status, r.why) == ("unchecked", "the summary does not list the column's values")
    assert resolve("keep_value", val, "B", {"keep_column": ""}, read).status == "unchecked"
    bare = {"groups": ObjectState(type="frame", digest="b3:0", summary={})}
    r = resolve("keep_column", col, "group", {}, bare)
    assert (r.status, r.why) == (
        "unchecked",
        "no object this step reads has its columns summarised",
    )
    prefix = ParamDecl(default="r", text="prefix")
    assert resolve("tag_prefix", prefix, "zz", {}, read).status == "unchecked"


def test_a_step_s_names_are_looked_for_in_the_inputs_it_descends_from() -> None:
    pipe = Pipeline.model_validate(
        {
            "pipeline": 1,
            "name": "p",
            "version": "0.1.0",
            "domain": "stringency-toy",
            "steps": [
                {"id": "01", "module": "m@0.1.0", "inputs": {"object": "$inputs.groups"}},
                {
                    "id": "02",
                    "module": "m@0.1.0",
                    "inputs": {"object": "$steps.01.object", "panel": "$inputs.panel"},
                    "params": {"by": {"default": "group", "text": "column"}},
                },
            ],
        }
    )
    panel = ObjectState(
        type="frame", digest="b3:1", summary={"fields": {"columns": {"gene": {}, "lineage": {}}}}
    )
    objects = {"groups": _frame(), "panel": panel}
    got = resolve_step(pipe, "02", {}, objects, ["groups", "panel"])
    assert [(r.parameter, r.status, r.where) for r in got] == [("by", "resolved", "groups")]
    got = resolve_step(pipe, "02", {"by": "lineage"}, objects, ["groups", "panel"])
    assert (got[0].status, got[0].where) == ("resolved", "panel")
    got = resolve_step(pipe, "02", {"by": "celltype"}, objects, ["groups", "panel"])
    assert got[0].status == "missing"


# -- declared ----------------------------------------------------------------------------


def test_a_declared_name_is_echoed_resolved_and_taken_as_given_under_every_profile(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    repo = _method(method_repo, NAMES)
    declared = {"01_filter": {"keep_column": "group", "keep_value": "A,B", "tag_prefix": "q"}}
    for profile in ("standard", "strict"):
        p = _project(tmp_path, toy_data, repo, f"declared-{profile}", declared, profile=profile)
        echo = " ".join(p.echo_path().read_text().split())
        assert "Names in step 01_filter: keep_column = 'group', a column of groups" in echo
        assert "keep_value = 'A,B', a value of group (declared)" in echo
        assert "tag_prefix = 'q', a naming convention, not checked" in echo
        r = cli(p, "run", "--json", env=MOCK)
        assert r.exit_code == 0, r.output
        run_id = json.loads(r.output)["run_id"]
        row = p.store.one("SELECT * FROM actions WHERE run_id=? AND step_id='01_filter'", (run_id,))
        assert json.loads(row["params_json"])["keep_column"] == "group"
        source = json.loads(row["param_source_json"])
        assert (source["keep_column"], source["keep_value"]) == ("declared", "declared")
        assert not p.store.all(
            "SELECT 1 FROM holds WHERE run_id=? AND step_id='01_filter'", (run_id,)
        )
        fired = p.store.all(
            "SELECT predicate_id FROM predicate_results WHERE run_id=? AND fired=1 "
            "AND predicate_id LIKE 'param.%'",
            (run_id,),
        )
        assert not fired


def test_a_declared_name_that_names_nothing_is_refused_at_init_and_by_declare_check(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    repo = _method(method_repo, NAMES)
    bad = {"01_filter": {"keep_column": "Group"}}
    with pytest.raises(ConfigError, match="init.name_unresolved") as e:
        init_project(_request(tmp_path, toy_data, repo, "bad-col", bad))
    said = str(e.value)
    assert "step 01_filter: keep_column = 'Group', a column that does not exist" in said
    assert "nearest: group" in said and not (tmp_path / "bad-col").exists()
    bad = {"01_filter": {"keep_column": "group", "keep_value": "A,Z"}}
    with pytest.raises(ConfigError, match="keep_value = 'A,Z', a value of group that does not"):
        check_declarations(_request(tmp_path, toy_data, repo, "bad-val", bad))
    # a value whose column lists no values is not checked, and the echo says so
    ok = {"01_filter": {"keep_column": "value", "keep_value": "83.4"}}
    out = check_declarations(_request(tmp_path, toy_data, repo, "unchecked", ok))
    assert "not checked (the summary does not list the column's values)" in " ".join(
        out.echo.split()
    )


# -- proposed ----------------------------------------------------------------------------


def test_an_agent_s_name_is_held_with_what_it_resolves_to(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    repo = _method(method_repo, NAMES)
    p = _project(tmp_path, toy_data, repo, "proposed", {})
    r = cli(
        p,
        "propose",
        "01_filter",
        "--set",
        "keep_column=group",
        "--set",
        "keep_value=B",
        "--reason",
        "the person asked for group B alone",
        "--json",
        env=MOCK,
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    hold = p.store.one("SELECT * FROM holds WHERE step_id='01_filter' AND resolved_via IS NULL")
    assert hold["reason"].startswith("param.agent_proposed")
    ev = json.loads(hold["context_json"])["evidence"]["proposed"]
    assert ev["keep_column"]["resolves"]["status"] == "resolved"
    assert ev["keep_column"]["resolves"]["detail"]["levels"] == ["A", "B", "C"]
    assert ev["keep_value"]["resolves"] == {
        "parameter": "keep_value",
        "kind": "value",
        "value": "B",
        "status": "resolved",
        "where": "groups",
        "column": "group",
    }
    shown = cli(p, "review", "--hold", hold["hold_id"]).output
    assert "In the data: keep_column = 'group', a column of groups (3 values: A, B, C)." in shown
    record_review(p, hold["hold_id"], "accept", reason="fine")
    assert cli(p, "run", "--json", env=MOCK).exit_code == 0


def test_an_agent_s_name_is_blocked_where_parameters_are_locked_or_it_names_nothing(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    repo = _method(method_repo, NAMES)
    strict = _project(tmp_path, toy_data, repo, "locked", {}, profile="strict")
    r = cli(strict, "propose", "01_filter", "--set", "keep_column=group", "--reason", "x", "--json")
    assert r.exit_code == 11, r.output + str(r.stderr)
    assert "param.locked_changed" in r.output + str(r.stderr)
    p = _project(tmp_path, toy_data, repo, "nothing", {})
    r = cli(p, "propose", "01_filter", "--set", "keep_column=celltype", "--reason", "x", "--json")
    assert r.exit_code == 11, r.output + str(r.stderr)
    row = p.store.one(
        "SELECT reason, evidence_json FROM predicate_results "
        "WHERE predicate_id='param.name_unresolved' AND fired=1"
    )
    assert row["reason"].startswith(
        "a name names nothing in the data the step reads: keep_column = 'celltype', a column "
        "that does not exist; nearest: "
    )
    # the step can be proposed again with a name that exists
    r = cli(p, "propose", "01_filter", "--set", "keep_column=unit", "--reason", "x", "--json")
    assert r.exit_code == 10, r.output + str(r.stderr)


def test_name_unresolved_must_fire_and_must_pass(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    """The predicate alone, on a context: fires on a column and on a value that name nothing;
    passes on names that exist, on an empty value, on a convention, and on a name it has no
    summary to check against (listed as not checked)."""
    from stringency.predicates.registry import registry
    from tests.helpers import make_ctx

    p = _project(tmp_path, toy_data, _method(method_repo, NAMES), "unit", {})
    spec = registry.get("param.name_unresolved")
    assert spec is not None and spec.version == 1 and spec.in_phase("pre")

    def verdict(proposed: dict[str, Any], objects: dict[str, ObjectState]):  # type: ignore[no-untyped-def]
        return spec.fn(make_ctx(p, "01_filter", proposed=proposed, objects=objects))

    seen = {"groups": _frame()}
    v = verdict({"keep_column": "celltype"}, seen)
    assert v.fired and v.evidence["unresolved"][0]["parameter"] == "keep_column"
    v = verdict({"keep_column": "group", "keep_value": "Z"}, seen)
    assert v.fired and "keep_value = 'Z', a value of group that does not exist" in (v.reason or "")
    assert not verdict({"keep_column": "group", "keep_value": "A,B"}, seen).fired
    assert not verdict({}, seen).fired  # empty names, and a convention
    assert not verdict({"tag_prefix": "zz"}, seen).fired
    v = verdict({"keep_column": "celltype"}, {})
    assert not v.fired


# -- unset -------------------------------------------------------------------------------


def test_a_required_name_stops_the_run_for_a_proposal_and_opens_no_hold(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    repo = _method(method_repo, {**NAMES, "unit_column": {"text": "column", "required": True}})
    p = _project(tmp_path, toy_data, repo, "required", {})
    echo = " ".join(p.echo_path().read_text().split())
    assert "unit_column is unset (the pipeline's default)" in echo
    assert "Unless declared here: unit_column is unset, so the run stops there" in echo
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 16, r.output
    out = json.loads(r.output)
    assert (out["kind"], out["step_id"]) == ("awaiting_proposal", "01_filter")
    assert out["unset"][0]["parameter"] == "unit_column" and out["unset"][0]["kind"] == "column"
    assert out["unset"][0]["candidates"] == {"groups": ["group", "row_id", "unit", "value"]}
    assert out["propose"].startswith("stringency propose 01_filter --set unit_column=<value>")
    assert "needs unit_column chosen before it can run" in out["plain"]
    assert not p.store.all("SELECT 1 FROM holds WHERE step_id='01_filter'")
    assert not p.store.all("SELECT 1 FROM actions WHERE step_id='01_filter'")
    assert json.loads(cli(p, "next", "--json").output)["kind"] == "awaiting_proposal"
    # a proposal that leaves it unset is refused before anything is written
    r = cli(p, "propose", "01_filter", "--set", "min_value=12", "--reason", "x", "--json")
    assert r.exit_code == 16 and "unit_column unset" in r.output + str(r.stderr)
    assert not p.store.all("SELECT 1 FROM actions WHERE step_id='01_filter'")
    # proposed, it is the agent's choice: held, accepted, run
    r = cli(p, "propose", "01_filter", "--set", "unit_column=unit", "--reason", "x", "--json")
    assert r.exit_code == 10, r.output + str(r.stderr)
    hold = p.store.one("SELECT hold_id FROM holds WHERE step_id='01_filter'")
    record_review(p, hold["hold_id"], "accept", reason="fine")
    assert cli(p, "run", "--json", env=MOCK).exit_code == 0
    # declared, the run never stops for it
    q = _project(tmp_path, toy_data, repo, "given", {"01_filter": {"unit_column": "unit"}})
    assert cli(q, "run", "--json", env=MOCK).exit_code == 0


def test_a_decision_point_the_method_leaves_unset_stops_the_run_for_a_proposal(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    """L129 (the Xenium method's rehearsal of 2026-10-27): a step reached with a decision at
    `unset` opened a sign-off on nothing, and an accept ran the step on `unset`. The owner,
    2026-11-10: the run stops for the proposal and no hold opens."""
    pipe = method_repo.path / "pipelines" / "toy-engine.yml"
    doc = yaml.safe_load(pipe.read_text())
    doc["steps"][3]["params"]["correction"] = {
        "default": "unset",
        "options": ["unset", "bh", "bonferroni", "none"],
    }
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    schema = method_repo.path / "modules" / "compare-groups" / "params.schema.json"
    sdoc = json.loads(schema.read_text())
    sdoc["properties"]["correction"]["enum"].append("unset")
    schema.write_text(json.dumps(sdoc, indent=2))
    sha = method_repo.commit("correction is unset until proposed")
    git.tag(method_repo.path, "v0.1.2")
    repo = MethodRepo(method_repo.path, "v0.1.2", sha)
    p = _project(tmp_path, toy_data, repo, "unset", {})
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 16, r.output
    out = json.loads(r.output)
    assert (out["kind"], out["step_id"]) == ("awaiting_proposal", "04_compare")
    assert out["unset"] == [
        {
            "parameter": "correction",
            "kind": "options",
            "options": ["unset", "bh", "bonferroni", "none"],
        }
    ]
    assert out["completed_steps"] == ["01_filter", "02_summarize", "03_label"]
    assert not p.store.all("SELECT 1 FROM holds WHERE step_id='04_compare'")
    r = cli(p, "propose", "04_compare", "--set", "correction=bonferroni", "--reason", "x", "--json")
    assert r.exit_code == 10, r.output + str(r.stderr)
    hold = p.store.one("SELECT hold_id FROM holds WHERE step_id='04_compare'")
    record_review(p, hold["hold_id"], "accept", reason="fine")
    assert cli(p, "run", "--json", env=MOCK).exit_code == 0


# -- lint --------------------------------------------------------------------------------


def test_lint_asks_no_decision_block_of_a_name_and_warns_on_a_decision_the_pipeline_fixes(
    method_repo: MethodRepo,
) -> None:
    from stringency.lint import lint_path

    _method(method_repo, NAMES)
    report = lint_path(method_repo.path)
    assert report.ok, report.render()
    assert not [w for w in report.warnings if "keep_column" in w or "tag_prefix" in w]
    skills = method_repo.path / "skills"
    skills.mkdir(exist_ok=True)
    (skills / "toy-engine.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "pipeline": "toy-engine",
                "decisions": [
                    {"step": "01_filter", "param": "keep_column", "how": "declared"},
                    {"step": "05_report", "param": "title", "how": "declared"},
                ],
            }
        )
    )
    pipe = method_repo.path / "pipelines" / "toy-engine.yml"
    doc = yaml.safe_load(pipe.read_text())
    doc["steps"][3]["params"]["correction"] = "bh"
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    (skills / "toy-engine.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "pipeline": "toy-engine",
                "decisions": [
                    {"step": "01_filter", "param": "keep_column", "how": "declared"},
                    {"step": "04_compare", "param": "correction", "how": "proposed"},
                ],
            }
        )
    )
    report = lint_path(method_repo.path)
    hits = [w for w in report.warnings if "decisions:" in w]
    assert len(hits) == 1 and "04_compare.correction is `how: proposed`" in hits[0]
    assert "the pipeline fixes it at 'bh'" in hits[0]
