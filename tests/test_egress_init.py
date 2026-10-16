"""The egress report and hold at init and run open (backlog L1): init opens the hold beside the
confirm hold and saves the report; run waits on the acknowledgement; a changed profile asks
again; a setup over the ceiling is refused at init and blocked at run open."""

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
from stringency.ids import new_id
from stringency.project import Project
from stringency.review import queue, record_review
from stringency.review_render import render
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations
from tests.test_declare import PROCESS_OBJECTIVE, _declare_args
from tests.test_run import MOCK, cli

pytestmark = pytest.mark.egress
runner = CliRunner()

# toy-engine under the engine with the mock harness and no hosted operator: class 0
QUIET: dict[str, object] = {
    "pipeline": "toy-engine",
    "execution": "engine",
    "operator_model": "none",
}


def _holds(p: Project, kind: str) -> list[dict]:
    return [
        dict(h)
        for h in p.store.all(
            "SELECT * FROM holds WHERE kind = ? AND run_id IS NULL ORDER BY created, rowid", (kind,)
        )
    ]


def _edit_config(p: Project, **changes: object) -> Project:
    path = p.root / "stringency.yml"
    cfg = yaml.safe_load(path.read_text())
    for key, value in changes.items():
        if key == "max_class":
            cfg.setdefault("egress", {})["max_class"] = value
        else:
            cfg[key] = value
    path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return Project.load(p.root)


def _reject(p: Project, hold_id: str) -> None:
    rid = new_id()
    p.store.insert(
        "reviews",
        {
            "review_id": rid,
            "hold_id": hold_id,
            "reviewer": "tester",
            "host": "test",
            "via": "tty",
            "ts": "2026-01-01T00:00:00Z",
            "verdict": "reject",
            "reason": "not acceptable",
        },
    )
    p.store.resolve_hold(hold_id, rid, "tty")


def test_init_opens_confirm_then_egress_and_saves_the_report(make_project: InitFn) -> None:
    p = make_project(egress_max=4)
    (eh,) = _holds(p, "egress")
    assert eh["waits_on_role"] == "owner" and eh["resolved_by_review"] is None
    a = p.egress_assessment()
    assert eh["bound_input_digest"] == hashing.prefixed(a.fingerprint)
    ctx = json.loads(eh["context_json"])
    assert ctx["assessed_class"] == 4 and ctx["max_class"] == 4 and ctx["within"] is True
    assert Path(ctx["report_path"]).exists() and (p.root / "prov" / "egress.md").exists()
    saved = json.loads((p.root / "prov" / "egress.json").read_text())
    assert saved["fingerprint"] == eh["bound_input_digest"]
    # the project-level holds come first, confirm before egress
    assert [h["kind"] for h in queue(p)] == ["confirm", "egress"]
    assert p.config.egress.max_class == 4 and p.config.egress.operator == "hosted"


def test_init_cli_prints_both_holds_and_exits_10(
    tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    decl = declarations
    args = [
        "init",
        str(tmp_path / "p"),
        "--method",
        method_repo.spec,
        "--pipeline",
        "toy-engine",
        "--objective",
        str(decl["objective.yml"]),
        "--design",
        str(decl["design.yml"]),
        "--inputs",
        str(decl["inputs.yml"]),
        "--judgment-harness",
        "mock",
        "--execution",
        "engine",
        "--executor",
        "local",
        "--egress-max",
        "0",
        "--operator-model",
        "none",
    ]
    r = runner.invoke(app, args)
    assert r.exit_code == 10, r.output
    assert "(confirm)" in r.output and "(egress)" in r.output
    assert "data egress: class 0 none, within the ceiling class 0 none" in r.output
    r = runner.invoke(app, ["init", str(tmp_path / "q"), *args[2:], "--json"])
    out = json.loads(r.output)
    assert out["egress_hold"] and out["egress"] == {
        "max_class": 0,
        "assessed_class": 0,
        "within": True,
        "report": out["egress"]["report"],
    }


def test_run_waits_on_the_acknowledgement(make_project: InitFn) -> None:
    p = make_project(**QUIET)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 10, r.output
    (eh,) = _holds(p, "egress")
    assert f"hold {eh['hold_id']} (egress)" in r.output and "report " in r.output
    st = json.loads(cli(p, "status", "--json").output)
    assert st["egress"] == "pending" and eh["hold_id"] in {h["hold_id"] for h in st["holds"]}
    accept_hold(p.store, eh["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    captures = json.loads(
        p.store.scalar(
            "SELECT payload_json FROM run_events WHERE run_id=? AND event='captures'", (run_id,)
        )
    )
    assert captures["egress"]["fingerprint"] == eh["bound_input_digest"]
    assert captures["egress"]["assessed_class"] == 0


def test_reject_keeps_the_run_held(make_project: InitFn) -> None:
    p = make_project(**QUIET)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    (eh,) = _holds(p, "egress")
    _reject(p, eh["hold_id"])
    assert p.egress_status() == "rejected"
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 10 and "(egress)" in r.output


def test_a_changed_profile_asks_again_with_a_new_report(make_project: InitFn) -> None:
    p = make_project(egress_max=3, **QUIET)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    (first,) = _holds(p, "egress")
    accept_hold(p.store, first["hold_id"])
    assert p.egress_status() == "accepted"
    # the harness changes: a judgment prompt now goes to a hosted model
    p = _edit_config(p, judgment_harness="api")
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 10, r.output
    holds = _holds(p, "egress")
    assert len(holds) == 2 and holds[1]["hold_id"] != first["hold_id"]
    report = Path(json.loads(holds[1]["context_json"])["report_path"])
    assert report.exists() and report != Path(json.loads(first["context_json"])["report_path"])
    assert "judgment harness api: class 3 derived" in report.read_text()
    accept_hold(p.store, holds[1]["hold_id"])
    # the ceiling is raised after init: the report names the acknowledged one
    p = _edit_config(p, max_class=4)
    assert cli(p, "run", env=MOCK).exit_code == 10
    latest = _holds(p, "egress")[-1]
    text = Path(json.loads(latest["context_json"])["report_path"]).read_text()
    assert "ceiling: class 4 data" in text and "last acknowledged report had class 3" in text


def test_over_the_ceiling_init_is_refused(make_project: InitFn, tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as e:
        make_project(egress_max=0)  # toy: 01_filter is operator-run under a hosted operator
    msg = str(e.value)
    assert "init.egress_exceeds_ceiling" in msg and "operator-run steps class 4" in msg
    assert "operator session (hosted) class 3" in msg


def test_over_the_ceiling_run_open_is_blocked(make_project: InitFn) -> None:
    p = make_project(egress_max=4, **QUIET)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    accept_hold(p.store, _holds(p, "egress")[0]["hold_id"])
    p = _edit_config(p, max_class=0, judgment_harness="api")
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 11, r.output
    assert "prov.egress_exceeds_ceiling" in r.output and "report " in r.output
    assert len(_holds(p, "egress")) == 1  # a block opens no question


def test_declare_check_shows_the_assessment(
    method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    decl_dir = declarations["design.yml"].parent
    r = runner.invoke(app, [*_declare_args(decl_dir, method_repo), "--egress-max", "4"])
    assert r.exit_code == 0, r.output
    assert "# Data egress" in r.output and "ceiling: class 4 data" in r.output
    out = json.loads(
        runner.invoke(
            app, [*_declare_args(decl_dir, method_repo), "--egress-max", "4", "--json"]
        ).output
    )
    assert out["egress"]["assessed_class"] == 4 and out["egress"]["within"] is True
    r = runner.invoke(app, [*_declare_args(decl_dir, method_repo), "--egress-max", "0"])
    assert r.exit_code == 15
    assert "init.egress_exceeds_ceiling" in (r.output + str(r.stderr))


def test_review_renders_and_settles_the_egress_hold(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = make_project(**QUIET)
    (eh,) = _holds(p, "egress")
    view = render(p, p.store.one("SELECT * FROM holds WHERE hold_id = ?", (eh["hold_id"],)))
    assert "question: is it acceptable that this leaves the machine" in view.text
    assert "# Data egress" in view.text
    assert [v["verdict"] for v in view.verdicts] == ["accept", "reject"]
    monkeypatch.setenv("USER", "tester")
    res = record_review(p, eh["hold_id"], "accept", reason="read it", via_override="tty")
    assert res.verdict == "accept" and res.step_status is None
    assert p.egress_status() == "accepted"


def test_a_chained_project_does_not_inherit_the_acknowledgement(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    up_files = write_declarations(tmp_path / "up", toy_data, objective=PROCESS_OBJECTIVE)
    up = make_project(
        pipeline="toy-process",
        execution="engine",
        operator_model="none",
        objective=up_files["objective.yml"],
        design=up_files["design.yml"],
        inputs=up_files["inputs.yml"],
    )
    accept_hold(up.store, up.confirm_hold()["hold_id"])
    accept_hold(up.store, _holds(up, "egress")[0]["hold_id"])
    r = cli(up, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    d = deliver(load_run(up, run_id))
    delivered = d.path / "01_filter.object.csv"
    down_inputs = {
        "inputs": 1,
        "items": [
            {
                "name": "groups",
                "path": str(delivered),
                "type": "frame",
                "blake3": hashing.hash_file(delivered),
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
        objective=down_files["objective.yml"],
        design=down_files["design.yml"],
        inputs=down_files["inputs.yml"],
        **QUIET,
    )
    assert down.confirm_status() == "accepted"  # inherited
    assert down.egress_status() == "pending"  # never inherited
    r = cli(down, "run", env=MOCK)
    assert r.exit_code == 10 and "(egress)" in r.output
