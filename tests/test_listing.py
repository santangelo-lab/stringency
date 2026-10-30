"""Opening an older delivery for questions (rows L135 and L136, 2026-10-29): `tools list
--method` on a pipeline project, the project's own inputs as candidates that bind by name, a
deliverable named `<step>.<output>`, the latest-step binding of one output delivered twice and
its record in the `created` event, the `--in` forms in the refusal, `open: {words_of:}` in the
listing and the renderer, and the lint on two `open.intro` blocks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from stringency import git, hashing
from stringency.deliver import deliver
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations
from tests.test_declare import PROCESS_OBJECTIVE
from tests.test_open_init import delivered_process, open_project
from tests.test_render_skill import _toy_analyze, _toy_repo, _toy_tools, rs
from tests.test_run import MOCK, cli

# a pipeline whose two steps produce the same output name, as the Xenium layers pipeline writes
# its domain tables from two steps
TWICE = {
    "pipeline": 1,
    "name": "toy-twice",
    "version": "0.1.0",
    "domain": "stringency-toy",
    "answers": ["process_rows"],
    "steps": [
        {
            "id": "01_filter",
            "title": "Filter low-value rows",
            "module": "filter-rows@0.1.1",
            "inputs": {"object": "$inputs.groups"},
            "params": {"min_value": {"default": 5, "range": [0, 40]}},
        },
        {
            "id": "02_refilter",
            "title": "Filter again, harder",
            "module": "filter-rows@0.1.1",
            "inputs": {"object": "$steps.01_filter.object"},
            "params": {"min_value": {"default": 10, "range": [0, 40]}},
        },
    ],
}

TOOL_WORDS = {
    "pipeline": "toy-engine",
    "tools": [
        {
            "module": "compare-groups",
            "title": "Compare the groups",
            "use_when": "the person asks which group is higher",
        }
    ],
    "open": {
        "intro": "The engine pipeline's words.",
        "paths": [{"answers": "which group is higher", "tool": "compare-groups"}],
    },
}


def _retag(repo: MethodRepo, tag: str, message: str) -> MethodRepo:
    sha = repo.commit(message)
    git.tag(repo.path, tag)
    return MethodRepo(repo.path, tag, sha)


def _twice_method(repo: MethodRepo) -> MethodRepo:
    pfile = repo.path / "pipelines" / "toy-twice.yml"
    if pfile.exists():
        return MethodRepo(repo.path, "v0.1.1", git.tag_sha(repo.path, "v0.1.1"))
    pfile.write_text(yaml.safe_dump(TWICE, sort_keys=False))
    return _retag(repo, "v0.1.1", "toy-twice")


def _delivered_twice(
    tmp_path: Path,
    toy_data: Path,
    make_project: InitFn,
    method_repo: MethodRepo,
    deliverables: list[str],
) -> tuple[Project, Path]:
    m = _twice_method(method_repo)
    files = write_declarations(
        tmp_path / f"up-{len(deliverables)}-{deliverables[0].replace('.', '-')}",
        toy_data,
        objective={**PROCESS_OBJECTIVE, "deliverables": deliverables},
    )
    up = make_project(
        method=m.spec,
        pipeline="toy-twice",
        execution="engine",
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    accept_hold(up.store, up.confirm_hold()["hold_id"])
    r = cli(up, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    return up, deliver(load_run(up, json.loads(r.output)["run_id"])).path


def _delivered_files(delivery: Path) -> list[tuple[str, str]]:
    index = json.loads((delivery / "index.json").read_text())
    return sorted((f["step_id"], f["output"]) for f in index["files"])


# -- deliverables by step ---------------------------------------------------------------------


def test_a_bare_deliverable_ships_from_every_step_a_qualified_one_from_its_step(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, bare = _delivered_twice(tmp_path, toy_data, make_project, method_repo, ["object"])
    assert _delivered_files(bare) == [("01_filter", "object"), ("02_refilter", "object")]
    _, one = _delivered_twice(tmp_path, toy_data, make_project, method_repo, ["02_refilter.object"])
    assert _delivered_files(one) == [("02_refilter", "object")]


def test_init_accepts_a_qualified_deliverable_and_refuses_a_step_without_it(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    m = _twice_method(method_repo)
    for bad in ("03_missing.object", "01_filter.figure"):
        files = write_declarations(
            tmp_path / f"bad-{bad}",
            toy_data,
            objective={**PROCESS_OBJECTIVE, "deliverables": [bad]},
        )
        with pytest.raises(ConfigError, match="init.deliverable_unproduced"):
            make_project(
                method=m.spec,
                pipeline="toy-twice",
                execution="engine",
                objective=files["objective.yml"],
                design=files["design.yml"],
                inputs=files["inputs.yml"],
            )


# -- binding one output delivered twice ------------------------------------------------------


def test_the_latest_steps_delivery_binds_and_the_created_event_says_so(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = _delivered_twice(tmp_path, toy_data, make_project, method_repo, ["object"])
    q = open_project(tmp_path, MethodRepo(method_repo.path, "v0.1.1", ""), delivery)
    assert sorted(i.name for i in q.inputs.items if i.derived_from) == [
        "01_filter_object",
        "02_refilter_object",
    ]
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    cli(q, "ask", "Which group is higher?")
    r = cli(q, "call", "compare-groups", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["inputs"] == {"object": str(q.inputs.by_name()["02_refilter_object"].path)}
    created = json.loads(
        q.store.scalar(
            "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? AND event='created'",
            (out["run_id"], out["step_id"]),
        )
    )
    assert created["on_demand"]["binding"] == {
        "object": {
            "bound_by": "latest_step",
            "ref": "$inputs.02_refilter_object",
            "alternatives": ["$inputs.01_filter_object"],
        }
    }
    # named with --in, the earlier step's binds and nothing is recorded as a rule's
    r = cli(q, "call", "compare-groups", "--in", "object=$inputs.01_filter_object", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    created = json.loads(
        q.store.scalar(
            "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? AND event='created'",
            (out["run_id"], out["step_id"]),
        )
    )
    assert "binding" not in created["on_demand"]


def test_inputs_of_different_outputs_are_refused_with_the_in_forms(
    tmp_path: Path, toy_data: Path, method_repo: MethodRepo
) -> None:
    other = toy_data.parent / "groups-b.csv"
    other.write_bytes(toy_data.read_bytes() + b"")
    item: dict[str, Any] = {"type": "frame", "source": "toy fixture"}
    files = write_declarations(
        tmp_path / "two",
        toy_data,
        objective={**PROCESS_OBJECTIVE, "id": "two-open", "deliverables": []},
        inputs={
            "inputs": 1,
            "items": [
                {**item, "name": "a", "path": str(toy_data), "blake3": hashing.hash_file(toy_data)},
                {**item, "name": "b", "path": str(other), "blake3": hashing.hash_file(other)},
            ],
        },
    )
    q = open_project(
        tmp_path,
        method_repo,
        None,
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    cli(q, "ask", "Which group is higher?")
    r = cli(q, "call", "compare-groups", "--json")
    assert r.exit_code == 15
    assert "name one with --in object=$inputs.a or --in object=$inputs.b" in str(r.stderr)


# -- the listing on a pipeline project -------------------------------------------------------


def test_tools_list_with_another_method_on_a_pipeline_project(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    # a later tag of the method ships one more tool and the words the open project will read
    mod = method_repo.path / "modules" / "summarize-groups" / "module.yml"
    mod.write_text(mod.read_text().replace("modes: [pipeline]", "modes: [pipeline, open]"))
    (method_repo.path / "skills").mkdir()
    (method_repo.path / "skills" / "toy-process.analyze.yml").write_text(
        yaml.safe_dump({"pipeline": "toy-process", "open": {"words_of": "toy-engine"}})
    )
    (method_repo.path / "skills" / "toy-engine.analyze.yml").write_text(yaml.safe_dump(TOOL_WORDS))
    later = _retag(method_repo, "v0.2.0", "summarize-groups lists open; skill words")

    own = json.loads(cli(up, "tools", "list", "--json").output)
    assert [t["name"] for t in own["tools"]] == ["compare-groups", "plot-groups"]
    assert own["tools"][0]["words"] is None and own["words_of"] is None

    r = cli(up, "tools", "list", "--method", later.spec, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    payload = json.loads(r.output)
    assert [t["name"] for t in payload["tools"]] == [
        "compare-groups",
        "plot-groups",
        "summarize-groups",
    ]
    assert payload["method"]["tag"] == "v0.2.0" and payload["method"]["sha"] == later.sha
    assert payload["method"]["project_pins"]["tag"] == "v0.1.0"
    # the words come from the file words_of names, read once
    assert payload["words_of"] == "toy-engine"
    assert payload["tools"][0]["words"]["title"] == "Compare the groups"
    assert payload["open"]["intro"] == "The engine pipeline's words."
    # the project's own input is a candidate the open project holds as upstream_groups
    cands = payload["tools"][0]["inputs"]["object"]["candidates"]
    assert cands[-1]["ref"] == "$inputs.upstream_groups" and cands[-1]["binds_by_name"]
    human = cli(up, "tools", "list", "--method", later.spec).output
    assert "tools of method" in human and "the project pins" in human
    assert "$inputs.upstream_groups binds by name (--in)" in human
    assert "words: the toy-engine analyze file's (open.words_of)" in human
    # the project's own method checkout is untouched
    assert git.head_sha(up.method_root) == method_repo.sha


def test_a_tool_whose_only_candidate_binds_by_name_is_offerable_with_in(
    make_project: InitFn, tmp_path: Path, toy_data: Path
) -> None:
    """Before delivery the project's own input is the only frame: compare-groups is offerable
    with `--in`, plot-groups (a table input) is not offered."""
    files = write_declarations(tmp_path / "up", toy_data, objective=PROCESS_OBJECTIVE)
    up = make_project(
        pipeline="toy-process",
        execution="engine",
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    payload = json.loads(cli(up, "tools", "list", "--json").output)
    compare, plot = payload["tools"]
    assert compare["offerable"] and compare["offer"] == (
        "offerable; bind with --in object=$inputs.upstream_groups"
    )
    assert not plot["offerable"] and plot["offer"] == "not offered: no candidate for comparison"
    human = cli(up, "tools", "list").output
    assert "  offerable; bind with --in object=$inputs.upstream_groups" in human


def test_an_optional_input_says_bind_with_in(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    mod = method_repo.path / "modules" / "compare-groups" / "module.yml"
    mod.write_text(
        mod.read_text().replace(
            "  object: {type: frame, format: csv, hash: true}\n",
            "  object: {type: frame, format: csv, hash: true}\n"
            "  extra: {type: frame, format: csv, hash: true, optional: true}\n",
        )
    )
    later = _retag(method_repo, "v0.2.0", "an optional input")
    payload = json.loads(cli(up, "tools", "list", "--method", later.spec, "--json").output)
    extra = payload["tools"][0]["inputs"]["extra"]
    assert extra["optional"] and extra["note"] == "bind with --in to use"
    assert payload["tools"][0]["offer"] == "offerable"
    human = cli(up, "tools", "list", "--method", later.spec).output
    assert "input extra (frame, optional): " in human and "; bind with --in to use" in human


def test_on_an_open_project_a_words_of_file_contributes_nothing(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    (method_repo.path / "skills").mkdir()
    (method_repo.path / "skills" / "toy-engine.analyze.yml").write_text(yaml.safe_dump(TOOL_WORDS))
    # a stray block beside the pointer is ignored: the file takes the other's words
    (method_repo.path / "skills" / "toy-process.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "pipeline": "toy-process",
                "tools": [{"module": "plot-groups", "title": "own words", "use_when": "never"}],
                "open": {"words_of": "toy-engine", "intro": "would win the merge"},
            }
        )
    )
    later = _retag(method_repo, "v0.2.0", "words")
    q = open_project(tmp_path, later, delivery)
    payload = json.loads(cli(q, "tools", "list", "--json").output)
    assert payload["open"]["intro"] == "The engine pipeline's words."
    assert payload["tools"][1]["words"] is None  # plot-groups: the pointer file's words unread
    # the open project's upstream input binds by name too
    up_cand = [c for c in payload["candidates"] if c.get("upstream_input")]
    assert up_cand and all(c["binds_by_name"] for c in up_cand)


# -- lint and the renderer -------------------------------------------------------------------


def test_lint_warns_on_two_open_intros_and_not_with_words_of(tmp_path: Path) -> None:
    repo = _toy_repo(tmp_path)
    skills = repo / "skills"
    (skills / "toy-engine.analyze.yml").write_text(yaml.safe_dump(TOOL_WORDS))
    (skills / "toy-process.analyze.yml").write_text(
        yaml.safe_dump({"pipeline": "toy-process", "open": {"intro": "a second intro"}})
    )
    report = lint_path(repo)
    assert any("open.intro in 2 analyze files" in w for w in report.warnings), report.warnings
    (skills / "toy-process.analyze.yml").write_text(
        yaml.safe_dump({"pipeline": "toy-process", "open": {"words_of": "toy-engine"}})
    )
    report = lint_path(repo)
    assert not any("open.intro" in w or "words_of" in w for w in report.warnings)
    (skills / "toy-process.analyze.yml").write_text(
        yaml.safe_dump({"pipeline": "toy-process", "open": {"words_of": "toy-nothing"}})
    )
    report = lint_path(repo)
    assert any("open.words_of names toy-nothing" in w for w in report.warnings)


def _process_analyze() -> dict[str, Any]:
    data = _toy_analyze()
    data.update(
        pipeline="toy-process",
        name="toy-process",
        question="process_rows",
        steps={"01_filter": "Filter low-value rows"},
        deliverables={"01_filter.object": "the filtered rows"},
        open={"words_of": "toy-engine"},
    )
    return data


def test_the_renderer_says_whose_words_open_the_delivery(tmp_path: Path) -> None:
    repo = _toy_repo(tmp_path)
    (repo / "skills" / "toy-engine.analyze.yml").write_text(
        yaml.safe_dump({**_toy_analyze(), **_toy_tools()})
    )
    src = repo / "skills" / "toy-process.analyze.yml"
    src.write_text(yaml.safe_dump(_process_analyze()))
    ctx, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert not problems, problems  # the qualified deliverable is accepted too
    out = " ".join(rs.render(ctx).split())
    assert (
        "This pipeline's delivery is opened for questions with the `stringency-analyze-toy-compare` "
        "skill's words; load that skill after delivery." in out
    )
    assert "ships no tools for questions" not in out
    # a pointer carries nothing of its own, and points at a file with tools
    bad = {**_process_analyze(), "open": {"words_of": "toy-engine", "intro": "mine"}}
    _, problems = rs.validate(bad, src, repo)
    assert any("carries no `intro` or `paths`" in p for p in problems), problems
    bad = {**_process_analyze(), "open": {"words_of": "toy-missing"}}
    _, problems = rs.validate(bad, src, repo)
    assert any("no analyze file toy-missing.analyze.yml" in p for p in problems), problems
    bad = {**_process_analyze(), "deliverables": {"02_nope.object": "x"}}
    _, problems = rs.validate(bad, src, repo)
    assert any("deliverables.02_nope.object" in p for p in problems), problems
