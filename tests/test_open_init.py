"""Open mode S1, binding (spec/archive/open_mode_plan.md 2.1, 2.3): `mode: open` in the config,
`init --mode open --from-delivery` deriving the declarations from a delivery, the confirm hold
whose echo is the switch paragraph, `tools list --context` on a delivered pipeline project and
on an open project, and the verbs open mode refuses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from stringency.config import StringencyConfig
from stringency.deliver import deliver
from stringency.echo import OPEN_SWITCH
from stringency.exit_codes import ConfigError
from stringency.pipelines import open_pipeline
from stringency.project import InitRequest, Project, init_project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations
from tests.test_declare import PROCESS_OBJECTIVE
from tests.test_run import MOCK, cli


def delivered_process(tmp_path: Path, toy_data: Path, make_project: InitFn) -> tuple[Project, Path]:
    """A `toy-process` project run to delivery: the upstream of every open project here."""
    files = write_declarations(tmp_path / "up", toy_data, objective=PROCESS_OBJECTIVE)
    up = make_project(
        pipeline="toy-process",
        execution="engine",
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    accept_hold(up.store, up.confirm_hold()["hold_id"])
    r = cli(up, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    d = deliver(load_run(up, json.loads(r.output)["run_id"]))
    return up, d.path


def open_project(
    tmp_path: Path, method_repo: MethodRepo, delivery: Path, **overrides: object
) -> Project:
    req = InitRequest(
        path=tmp_path / "questions",
        method=method_repo.spec,
        pipeline=None,
        objective=None,
        design=None,
        inputs=None,
        mode="open",
        owner="tester",
        reviewer="tester",
        judgment_harness="mock",
        execution="engine",
        executor="local",
        from_delivery=delivery,
    )
    for k, v in overrides.items():
        setattr(req, k, v)
    return init_project(req)


# -- config -------------------------------------------------------------------------------


def _cfg(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "project_id": "01TEST",
        "created": "2026-10-16T00:00:00Z",
        "stringency_version": "0.2.21",
        "method": {"repo": "x", "tag": "v0.1.0", "sha": "0" * 40},
        "pipeline": None,
        "mode": "open",
        "domain": "stringency-toy",
        "roles": {"owner": "a", "reviewer": "a"},
    }
    base.update(over)
    return base


def test_config_open_mode_shape() -> None:
    cfg = StringencyConfig.model_validate(_cfg())
    assert cfg.pipeline is None and cfg.domain == "stringency-toy"
    with pytest.raises(ValueError, match="strict"):
        StringencyConfig.model_validate(_cfg(profile="strict"))
    with pytest.raises(ValueError, match="binds no pipeline"):
        StringencyConfig.model_validate(_cfg(pipeline="toy"))
    with pytest.raises(ValueError, match="needs domain"):
        StringencyConfig.model_validate(_cfg(domain=None))
    with pytest.raises(ValueError, match="reserved"):
        StringencyConfig.model_validate(_cfg(mode="staged", pipeline="toy", domain=None))
    with pytest.raises(ValueError, match="needs a pipeline"):
        StringencyConfig.model_validate(_cfg(mode="pipeline", domain=None))


def test_open_pipeline_is_empty_and_valid() -> None:
    p = open_pipeline("stringency-toy", "v0.1.0", ["compare_groups"])
    assert (
        p.name == "open" and p.steps == [] and p.order() == [] and p.answers == ["compare_groups"]
    )


# -- tools list on a delivered pipeline project -----------------------------------------


def test_tools_list_on_a_delivered_pipeline_project(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    r = cli(up, "tools", "list", "--context", "--json")
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert payload["schema"] == "stringency.tools/1" and payload["mode"] == "pipeline"
    names = [t["name"] for t in payload["tools"]]
    assert names == ["compare-groups", "plot-groups"]  # the toy modules that list open
    tool = payload["tools"][0]
    assert tool["ref"] == "compare-groups@0.1.1" and tool["kind"] == "deterministic"
    assert tool["env_status"] == "verified"  # the local executor digests the lock file
    # the delivered frame is what the tool's input could bind; the project's own input is a
    # candidate the open project holds as upstream_groups, bound only by name (L135)
    cands = tool["inputs"]["object"]["candidates"]
    assert [c.get("delivered") or c["ref"] for c in cands] == [
        "01_filter.object.csv",
        "$inputs.upstream_groups",
    ]
    assert cands[0]["type"] == "frame" and cands[1]["binds_by_name"] is True
    assert "binds_by_name" not in cands[0] and tool["offer"] == "offerable"
    assert set(tool["params"]) == {"replicate_unit", "correction"}
    assert tool["params"]["correction"]["decision_point"] is True
    assert tool["controls"]["last_passing"] is None
    # a deterministic tool with declared controls: they run before its first use
    assert "before the tool's first use" in tool["controls"]["note"]
    plot = payload["tools"][1]
    assert plot["controls"]["declared"] == ["positive-draws"]
    assert tool["words"] is None  # the toy method ships no analyze skill file here
    ctx = payload["context"]
    assert ctx["objective"]["question"] == "process_rows"
    assert ctx["objective"]["deliverables"] == ["object"]
    assert ctx["design"]["factors"]["group"]["levels"] == ["A", "B", "C"]
    human = cli(up, "tools", "list", "--context").output
    assert "compare-groups@0.1.1" in human and "factor group" in human and "process_rows" in human


def test_tools_list_reads_the_analyze_skill_words(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    skills = up.method_root / "skills"
    skills.mkdir()
    (skills / "toy-process.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "pipeline": "toy-process",
                "tools": [
                    {
                        "module": "compare-groups",
                        "title": "Compare the groups",
                        "use_when": "the person asks which group is higher",
                        "asks": {"correction": "Which correction do you want?"},
                    }
                ],
                "open": {
                    "paths": [
                        {"answers": "which group is higher", "tool": "compare-groups"},
                        {"answers": "a plot of the groups", "code": True},
                    ]
                },
            }
        )
    )
    payload = json.loads(cli(up, "tools", "list", "--json").output)
    assert payload["tools"][0]["words"]["title"] == "Compare the groups"
    assert payload["open"]["paths"][1]["answers"] == "a plot of the groups"
    human = cli(up, "tools", "list").output
    assert "use when: the person asks which group is higher" in human
    assert "ask: Which correction do you want?" in human
    assert "a plot of the groups: code" in human


# -- init --mode open --from-delivery -----------------------------------------------------


def test_init_from_delivery_binds_an_open_project_with_the_switch_paragraph(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    assert q.open_ended and q.config.mode == "open" and q.config.pipeline is None
    assert q.config.domain == "stringency-toy" and q.pipeline.steps == []
    assert [m.manifest.name for m in q.tools()] == ["compare-groups", "plot-groups"]
    assert q.env_names() == ["toy-py"] and q.env_for_input("object") == "toy-py"
    # the declarations derived from the delivery
    item = q.inputs.items[0]
    assert item.name == "object" and item.type == "frame"
    assert item.derived_from is not None and item.derived_from.project == str(up.root)
    assert item.derived_from.step_id == "01_filter" and item.derived_from.output == "object"
    assert (q.root / "design.yml").read_bytes() == (up.root / "design.yml").read_bytes()
    assert q.objective.id == "toy_process-open" and q.objective.deliverables == []
    assert q.objective.params == {} and q.objective.question == "process_rows"
    row = q.store.one("SELECT * FROM projects")
    assert row["pipeline_name"] == "open" and row["pipeline_version"] == "v0.1.0"
    assert row["mode"] == "open"
    # no inherited confirmation (decision 4): one confirm hold, open, whose echo is the switch
    hold = q.confirm_hold()
    assert hold is not None and hold["resolved_by_review"] is None
    assert q.inherited_confirmation() is None and q.confirm_status() == "pending"
    echo = q.echo_path().read_text()
    assert " ".join(OPEN_SWITCH.split()) in " ".join(echo.split())
    assert f"run {item.derived_from.run_id} of {up.root}" in " ".join(echo.split())
    assert "compare-groups (compare_groups), plot-groups (plot_groups)" in echo
    # the init predicates all passed against the empty topology
    rows = q.store.all("SELECT predicate_id, fired FROM predicate_results WHERE run_id='init'")
    assert {r["predicate_id"] for r in rows} >= {
        "init.question_unsupported",
        "init.deliverable_unproduced",
        "init.column_missing",
    }
    assert not any(r["fired"] for r in rows)


def test_open_project_accepts_the_switch_relayed_with_attest(
    tmp_path: Path,
    toy_data: Path,
    make_project: InitFn,
    method_repo: MethodRepo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    hold = q.confirm_hold()
    monkeypatch.setattr("stringency.review.detect_via", lambda: None)
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    monkeypatch.setenv("STRINGENCY_SESSION_REF", "claude-code:open-test")
    r = cli(
        q,
        "review",
        "--hold",
        hold["hold_id"],
        "--verdict",
        "accept",
        "--reason",
        "the person said yes to the switch paragraph",
        "--attest",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert q.confirm_status() == "accepted"
    rev = q.store.one("SELECT * FROM reviews WHERE hold_id=?", (hold["hold_id"],))
    assert rev["via"] == "relayed" and rev["operator_session_ref"] == "claude-code:open-test"


def test_open_project_tools_list_names_the_inputs(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    payload = json.loads(cli(q, "tools", "list", "--context", "--json").output)
    assert payload["mode"] == "open" and payload["pipeline"] is None
    cands = payload["tools"][0]["inputs"]["object"]["candidates"]
    # the upstream pipeline's own input is listed, marked, and binds only when named
    assert [c["ref"] for c in cands] == ["$inputs.object", "$inputs.upstream_groups"]
    assert "upstream_input" not in cands[0] and cands[1]["upstream_input"] == "groups"
    assert payload["context"]["objective"]["deliverables"] == []


def test_open_mode_refusals(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    with pytest.raises(ConfigError, match="binds no pipeline"):
        open_project(tmp_path, method_repo, delivery, pipeline="toy")
    with pytest.raises(ConfigError, match="strict"):
        open_project(tmp_path, method_repo, delivery, profile="strict")
    with pytest.raises(ConfigError, match="needs --mode open"):
        open_project(tmp_path, method_repo, delivery, mode="pipeline", pipeline="toy")
    with pytest.raises(ConfigError, match="not a delivery directory"):
        open_project(tmp_path, method_repo, tmp_path)
    with pytest.raises(ConfigError, match="--pipeline is required"):
        make_project(pipeline=None)
    # an open objective declares no params and no deliverables
    decl = write_declarations(
        tmp_path / "bad",
        toy_data,
        objective={**PROCESS_OBJECTIVE, "params": {"x": {"y": 1}}},
    )
    with pytest.raises(ConfigError, match="no params"):
        open_project(tmp_path, method_repo, delivery, objective=decl["objective.yml"])
    # the CLI: --pipeline with --mode open is exit 15; run and fork on an open project exit 16
    q = open_project(tmp_path, method_repo, delivery)
    r = cli(
        q,
        "init",
        str(tmp_path / "x"),
        "--method",
        method_repo.spec,
        "--mode",
        "open",
        "--pipeline",
        "toy",
        "--from-delivery",
        str(delivery),
    )
    assert r.exit_code == 15, r.output + str(r.stderr)
    accept_hold(q.store, q.confirm_hold()["hold_id"])
    r = cli(q, "run")
    assert r.exit_code == 16 and "run is not a verb of an open project" in str(r.stderr)
    r = cli(q, "fork", "--from", "x", "--at", "y", "--reason", "z")
    assert r.exit_code == 16 and "fork is not a verb" in str(r.stderr)
    # a method that ships no tool cannot open
    for pf in (method_repo.path / "modules" / "compare-groups" / "module.yml",):
        pf.write_text(pf.read_text().replace("modes: [pipeline, open]", "modes: [pipeline]"))
    import shutil

    shutil.rmtree(method_repo.path / "modules" / "plot-groups")
    method_repo.commit("no open tools")
    from stringency import git

    git.tag(method_repo.path, "v0.1.1")
    with pytest.raises(ConfigError, match="ships no module that lists open"):
        open_project(
            tmp_path,
            method_repo,
            delivery,
            method=f"{method_repo.path}@v0.1.1",
            path=tmp_path / "q2",
        )


def test_init_cli_from_delivery_and_declare_check(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    common = [
        "--method",
        method_repo.spec,
        "--mode",
        "open",
        "--from-delivery",
        str(delivery),
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--execution",
        "engine",
    ]
    r = cli(up, "declare", str(tmp_path / "nothing"), "--check", *common, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    check = json.loads(r.output)
    assert "Shall I open it for questions?" in check["echo"] and "object" in check["inputs"]
    assert not (tmp_path / "nothing").exists()
    r = cli(
        up,
        "init",
        str(tmp_path / "q"),
        *common,
        "--owner",
        "tester",
        "--reviewer",
        "tester",
        "--json",
    )
    assert r.exit_code == 10, r.output + str(r.stderr)  # held on the confirm
    out = json.loads(r.output)
    assert out["confirm_hold"] and (tmp_path / "q" / "stringency.yml").exists()
    cfg = yaml.safe_load((tmp_path / "q" / "stringency.yml").read_text())
    assert cfg["mode"] == "open" and cfg["pipeline"] is None and cfg["domain"] == "stringency-toy"
    # reading verbs work on the open project without its plugin's pipeline
    from stringency.present import Site

    site = Site.load(tmp_path / "q")
    assert site.open_ended and site.pipeline.steps == [] and site.skill_name == "open"
    from stringency.board import project_entry

    e = project_entry(tmp_path / "q")
    assert e["pipeline"] == "open" and e["confirm"] == "pending"


def test_init_from_delivery_takes_each_files_producing_run_from_its_sidecar(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    """A resumed or forked run delivers steps an earlier run completed; the file's sidecar names
    that run, and `derived_from.run_id` must agree with it or `init` refuses the input (seen on
    the Lyons liver delivery, 2026-10-20)."""
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    index = json.loads((delivery / "index.json").read_text())
    first = index["files"][0]
    sidecar = delivery / first["sidecar"]
    meta = json.loads(sidecar.read_text())
    meta["run_id"] = "01AAAAAAAAAAAAAAAAAAAAAAAA"
    sidecar.write_text(json.dumps(meta))
    r = cli(
        up,
        "init",
        str(tmp_path / "q"),
        "--method",
        method_repo.spec,
        "--mode",
        "open",
        "--from-delivery",
        str(delivery),
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--execution",
        "engine",
        "--owner",
        "tester",
        "--reviewer",
        "tester",
        "--json",
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    inputs = yaml.safe_load(
        (tmp_path / "q" / ".stringency" / "from-delivery" / "inputs.yml").read_text()
    )
    by_name = {i["name"]: i for i in inputs["items"]}
    assert by_name[first["output"]]["derived_from"]["run_id"] == "01AAAAAAAAAAAAAAAAAAAAAAAA"
    others = [i for i in inputs["items"] if "derived_from" in i and i["name"] != first["output"]]
    assert all(i["derived_from"]["run_id"] == index["run_id"] for i in others)
