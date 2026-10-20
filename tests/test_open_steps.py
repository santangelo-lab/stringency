"""Open mode S2, on-demand steps (spec/plans/open_mode_plan.md 2.2, 2.3, 2.8): `ask` files a
question; `call <tool>` adds a step to the open run and runs it through the ordinary gate;
the `person` parameter source; `topo.input_type_mismatch` and `param.schema_invalid` at the
pre-gate; `next` on an open run; the questions table is append-only."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import cli


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    """An open project on a `toy-process` delivery, its switch accepted."""
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    return q


def test_ask_then_call_completes_with_an_artifact(questions: Project) -> None:
    q = questions
    r = cli(q, "ask", "Which group is higher, A or B?", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    asked = json.loads(r.output)
    assert asked["origin"] == "person" and asked["seq"] == 1
    assert [t["name"] for t in asked["tools"]] == ["compare-groups", "plot-groups"]
    qid, run_id = asked["question_id"], asked["run_id"]
    row = q.store.one("SELECT * FROM questions WHERE question_id=?", (qid,))
    assert (
        row["run_id"] == run_id
        and q.store.message(row["text_ref"]) == "Which group is higher, A or B?"
    )
    # the run opened for the question carries no declared step and names the tools
    assert q.store.scalar("SELECT COUNT(*) FROM steps WHERE run_id=?", (run_id,)) == 0
    captures = json.loads(
        q.store.scalar(
            "SELECT payload_json FROM run_events WHERE run_id=? AND event='captures'", (run_id,)
        )
    )
    assert captures["tools"] == ["compare-groups@0.1.1", "plot-groups@0.1.0"]
    assert captures["script_blobs"].keys() == {"compare-groups@0.1.1", "plot-groups@0.1.0"}

    r = cli(q, "call", "compare-groups", "--question", qid, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["step_id"] == "01_compare-groups" and out["status"] == "completed"
    assert out["inputs"] == {"object": str(q.inputs.items[0].path)}  # the one frame input bound
    assert out["parameters"] == {"replicate_unit": "unit", "correction": "bh"}  # schema defaults
    assert out["param_source"] == {"replicate_unit": "default", "correction": "default"}
    assert [a["name"] for a in out["artifacts"]] == ["comparison_table"]
    assert out["next"]["kind"] == "open" and out["next"]["exit_code"] == 0
    # the step is in the run's topology, created on demand, and the run stays running
    rc = load_run(q, run_id)
    assert rc.order() == ["01_compare-groups"] and rc.status() == "running"
    assert rc.on_demand()[0]["kind"] == "tool" and rc.on_demand()[0]["question_id"] == qid
    created = q.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? AND event='created'",
        (run_id, "01_compare-groups"),
    )
    assert json.loads(created["payload_json"])["on_demand"]["decl"]["inputs"] == {
        "object": "$inputs.object"
    }
    # every ordinary predicate ran at the gate: the invariants, the params, the objective
    fired = {
        r["predicate_id"]: r["fired"]
        for r in q.store.all(
            "SELECT predicate_id, fired FROM predicate_results WHERE run_id=? AND action_id=?",
            (run_id, q.store.scalar("SELECT action_id FROM actions WHERE run_id=?", (run_id,))),
        )
    }
    assert {
        "topo.undeclared_step",
        "topo.input_type_mismatch",
        "param.schema_invalid",
        "param.agent_proposed",
    } <= set(fired)
    assert not fired["topo.undeclared_step"] and not fired["param.schema_invalid"]
    # the artifact carries a sidecar; the second call is a second step on the same inputs
    a = q.store.one("SELECT * FROM artifacts WHERE run_id=?", (run_id,))
    assert Path(a["path"]).exists() and Path(a["sidecar_path"]).exists()
    r = cli(q, "call", "compare-groups", "--json")
    assert r.exit_code == 0 and json.loads(r.output)["step_id"] == "02_compare-groups"
    assert (
        q.store.scalar(
            "SELECT COUNT(*) FROM actions WHERE run_id=? AND module='compare-groups@0.1.1'",
            (run_id,),
        )
        == 2
    )
    # next and status read the open run
    r = cli(q, "next", "--json")
    nx = json.loads(r.output)
    assert nx["kind"] == "open" and len(nx["questions"]) == 1 and len(nx["steps"]) == 2
    assert (
        len(nx["artifacts"]) == 2 and nx["questions"][0]["text"] == "Which group is higher, A or B?"
    )
    r = cli(q, "status", "--json")
    assert r.exit_code == 0 and "Open for questions: one asked" in json.loads(r.output)["plain"]


def test_schema_invalid_blocks_and_agent_choice_holds(questions: Project) -> None:
    q = questions
    cli(q, "ask", "compare with a stricter correction")
    r = cli(q, "call", "compare-groups", "--set", "correction=foo", "--json")
    assert r.exit_code == 11, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "blocked"
    preds = (
        {p["predicate_id"] for p in out["next"].get("predicates", [])}
        if out["next"]["kind"] == "blocked"
        else set()
    )
    blocked = {
        r_["predicate_id"]
        for r_ in q.store.all(
            "SELECT predicate_id FROM predicate_results WHERE fired=1 AND effective_disposition='block'"
        )
    }
    assert "param.schema_invalid" in blocked, (preds, blocked)
    # a blocked on-demand step is that step's state only: the run stays running, next is open
    rc = load_run(q, out["run_id"])
    assert rc.step_status()["01_compare-groups"] == "blocked" and rc.status() == "running"
    assert out["next"]["kind"] == "open"
    # the agent's own choice of a valid value opens a param.agent_proposed hold under standard
    r = cli(
        q,
        "call",
        "compare-groups",
        "--set",
        "correction=bonferroni",
        "--reason",
        "fewer false positives",
        "--json",
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "held" and out["step_id"] == "02_compare-groups"
    assert out["param_source"]["correction"] == "agent"
    hold = q.store.one(
        "SELECT * FROM holds WHERE run_id=? AND step_id=?", (out["run_id"], "02_compare-groups")
    )
    assert hold["kind"] == "flag" and "param.agent_proposed" in hold["reason"]
    assert rc.status() == "held"
    # accepted, the step completes through propose (the retry path of a held tool step)
    accept_hold(q.store, hold["hold_id"], reason="the person agreed to bonferroni")
    from stringency.machine import StepStatus, transition
    from stringency.steps import execute_engine, resume_after_hold

    transition(q.store, out["run_id"], "02_compare-groups", StepStatus.ADMISSIBLE)
    done = execute_engine(rc, resume_after_hold(rc, "02_compare-groups"))
    assert done.status == StepStatus.COMPLETED
    action = q.store.one(
        "SELECT * FROM actions WHERE run_id=? AND step_id=?", (out["run_id"], "02_compare-groups")
    )
    assert json.loads(action["params_json"])["correction"] == "bonferroni"


def test_person_set_values_open_no_hold(questions: Project) -> None:
    q = questions
    cli(q, "ask", "use bonferroni, please")
    r = cli(
        q,
        "call",
        "compare-groups",
        "--set",
        "correction=bonferroni",
        "--asked-by",
        "person",
        "--json",
    )
    assert r.exit_code == 15  # a person's value needs their words as the reason
    r = cli(
        q,
        "call",
        "compare-groups",
        "--set",
        "correction=bonferroni",
        "--asked-by",
        "person",
        "--reason",
        "the person said: use bonferroni, please",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "completed" and out["param_source"]["correction"] == "person"
    assert q.store.scalar("SELECT COUNT(*) FROM holds WHERE run_id=?", (out["run_id"],)) == 0
    action = q.store.one("SELECT * FROM actions WHERE run_id=?", (out["run_id"],))
    assert action["proposed_by"] == "person"
    assert q.store.message(action["rationale_ref"]) == "the person said: use bonferroni, please"
    fired = q.store.scalar(
        "SELECT fired FROM predicate_results WHERE action_id=? AND predicate_id='param.agent_proposed'",
        (action["action_id"],),
    )
    assert fired == 0


def test_wrong_input_kind_blocks_and_unbound_input_is_named(questions: Project) -> None:
    q = questions
    cli(q, "ask", "compare the comparison")
    r = cli(q, "call", "compare-groups", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    # bind the tool's frame input to the table it just produced: blocked at the pre-gate
    r = cli(
        q,
        "call",
        "compare-groups",
        "--in",
        "object=$steps.01_compare-groups.comparison_table",
        "--json",
    )
    assert r.exit_code == 11, r.output + str(r.stderr)
    out = json.loads(r.output)
    blocked = {
        r_["predicate_id"]
        for r_ in q.store.all(
            "SELECT predicate_id FROM predicate_results WHERE fired=1 AND effective_disposition='block'"
        )
    }
    assert "topo.input_type_mismatch" in blocked
    # an artifact id binds the same way
    aid = q.store.scalar(
        "SELECT artifact_id FROM artifacts WHERE run_id=? AND step_id='01_compare-groups'",
        (out["run_id"],),
    )
    r = cli(q, "call", "compare-groups", "--in", f"object={aid}", "--json")
    assert r.exit_code == 11
    # an unknown input name, a bad reference and an unknown tool are configuration errors
    r = cli(q, "call", "compare-groups", "--in", "frame=$inputs.object")
    assert r.exit_code == 15 and "has no input frame" in str(r.stderr)
    r = cli(q, "call", "compare-groups", "--in", "object=nonsense")
    assert r.exit_code == 15
    r = cli(q, "call", "draw-things")
    assert r.exit_code == 15 and "no tool named draw-things" in str(r.stderr)
    r = cli(q, "call", "compare-groups", "--question", "01NOTAQUESTION000000000000")
    assert r.exit_code == 15


def test_ask_refused_before_the_switch_and_on_a_pipeline_project(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    r = cli(up, "ask", "anything")
    assert r.exit_code == 16 and "open project" in str(r.stderr)
    q = open_project(tmp_path, method_repo, delivery)
    r = cli(q, "ask", "anything")
    assert r.exit_code == 10 and "confirm" in str(r.stderr)  # the switch is not accepted
    assert q.store.scalar("SELECT COUNT(*) FROM questions") == 0
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    r = cli(q, "ask", "a path I proposed", "--suggested", "--json")
    assert r.exit_code == 0 and json.loads(r.output)["origin"] == "suggested"
    r = cli(q, "ask", "   ")
    assert r.exit_code == 15
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        q.store._conn.execute("DELETE FROM questions")
    # abandon closes the open run; the next ask opens another
    run_id = json.loads(cli(q, "next", "--json").output)["run_id"]
    r = cli(q, "abandon", "--run", run_id, "--reason", "done for today")
    assert r.exit_code == 0, r.output + str(r.stderr)
    r = cli(q, "ask", "a new day", "--json")
    assert r.exit_code == 0 and json.loads(r.output)["run_id"] != run_id
