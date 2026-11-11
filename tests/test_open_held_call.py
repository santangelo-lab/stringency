"""L114 (found 2026-10-26 in the Xenium method's open-tools check): in open mode a tool call
that holds could not finish. After the accept the on-demand step was `admissible`, `run` is
not a verb of an open project, a second `call` proposes a second step, and `propose <step>`
refused an admissible step, so the accepted step stayed admissible for good. `propose <step>`
with nothing else now carries out what was accepted."""

from __future__ import annotations

import json

import pytest

from stringency.project import Project
from stringency.review import queue, record_review
from tests.test_open_answers import questions  # noqa: F401
from tests.test_run import cli


def _run_step(q: Project, step: str) -> str:
    return str(
        q.store.scalar(
            "SELECT s.status FROM steps s JOIN runs r ON r.run_id = s.run_id "
            "WHERE r.kind = 'run' AND s.step_id = ? ORDER BY s.rowid DESC LIMIT 1",
            (step,),
        )
    )


def test_an_accepted_hold_on_a_tool_call_is_carried_out_by_propose(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = questions
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: q.config.roles.owner)
    asked = json.loads(cli(q, "ask", "Is group A above B?", "--json").output)
    r = cli(
        q,
        "call",
        "compare-groups",
        "--question",
        asked["question_id"],
        "--set",
        "correction=bonferroni",
        "--reason",
        "the stricter one",
        "--json",
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    holds = queue(q)
    assert [h["reason"].split(":")[0] for h in holds] == ["param.agent_proposed"]
    step = holds[0]["step_id"]
    record_review(q, holds[0]["hold_id"], "accept", reason="fine")
    assert _run_step(q, step) == "admissible"
    actions = q.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id = ?", (step,))
    # with a value it is a new proposal, which an admissible step does not take
    r = cli(q, "propose", step, "--set", "correction=none", "--reason", "x", "--json")
    assert r.exit_code == 16, r.output + str(r.stderr)
    # bare, it carries out the accepted Action: the same action, no new hold, the step done
    r = cli(q, "propose", step, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["status"] == "completed"
    assert _run_step(q, step) == "completed"
    assert q.store.scalar("SELECT COUNT(*) FROM actions WHERE step_id = ?", (step,)) == actions
    assert queue(q) == []
    row = q.store.one(
        "SELECT a.params_json FROM actions a JOIN runs r ON r.run_id = a.run_id "
        "WHERE r.kind = 'run' AND a.step_id = ?",
        (step,),
    )
    assert json.loads(row["params_json"])["correction"] == "bonferroni"
    # a completed step is not carried out twice
    r = cli(q, "propose", step, "--json")
    assert r.exit_code == 16, r.output + str(r.stderr)
