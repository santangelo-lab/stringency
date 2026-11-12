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


def _held_call(q: Project, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    """A tool call held on its proposed value: (step id, hold id)."""
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
    payload = json.loads(r.output)
    # the held report names the one command that carries the step out once accepted
    mine = [h for h in payload["next"]["holds"] if h["step_id"] == payload["step_id"]]
    assert [h["after_accept"] for h in mine] == [f"stringency propose {payload['step_id']}"]
    hold = next(h for h in queue(q) if h["step_id"] == payload["step_id"])
    return str(hold["step_id"]), str(hold["hold_id"])


def test_call_names_the_step_it_held_and_next_says_the_one_command(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rest of L114: `call --step` carries out the call that was accepted, the hold view
    and `next` say the one command, and nothing makes a second step."""
    q = questions
    step, hold = _held_call(q, monkeypatch)
    shown = json.loads(cli(q, "present", "--hold", hold, "--json").output)
    assert shown["after_accept"]["command"] == f"stringency propose {step}"
    assert f"abandon --step {step}" in shown["after_accept"]["close"]
    assert f"stringency propose {step}" in cli(q, "present", "--hold", hold).output
    # still held: --step does not run it, and says who it waits for
    r = cli(q, "call", "--step", step, "--json")
    assert r.exit_code == 16 and "still held" in (r.output + str(r.stderr))
    record_review(q, hold, "accept", reason="fine")
    nx = json.loads(cli(q, "next", "--json").output)
    waiting = nx["to_carry_out"]
    assert [w["step_id"] for w in waiting] == [step]
    assert waiting[0]["command"] == f"stringency propose {step}"
    assert step in nx["message"] and "accepted and not yet run" in nx["message"]
    # --step takes nothing else, and a tool named beside it must be the step's
    r = cli(q, "call", "--step", step, "--set", "correction=none", "--json")
    assert r.exit_code == 15, r.output + str(r.stderr)
    r = cli(q, "call", "some-other-tool", "--step", step, "--json")
    assert r.exit_code == 15, r.output + str(r.stderr)
    n_steps = len(nx["steps"])
    r = cli(q, "call", "--step", step, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    done = json.loads(r.output)
    assert done["step_id"] == step and done["status"] == "completed"
    assert done["parameters"]["correction"] == "bonferroni"
    after = json.loads(cli(q, "next", "--json").output)
    assert after["to_carry_out"] == [] and len(after["steps"]) == n_steps
    # done once
    assert cli(q, "call", "--step", step, "--json").exit_code == 16


def test_a_call_nobody_wants_is_closed(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = questions
    # a held call is closed: its hold is withdrawn, no verdict recorded, the run stays open
    step, hold = _held_call(q, monkeypatch)
    reviews = q.store.scalar("SELECT COUNT(*) FROM reviews")
    r = cli(q, "abandon", "--step", step, "--reason", "not wanted", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["holds"] == [hold] and json.loads(r.output)["was"] == "held"
    assert queue(q) == [] and _run_step(q, step) == "abandoned"
    row = q.store.one("SELECT resolved_via FROM holds WHERE hold_id = ?", (hold,))
    assert row["resolved_via"] == "withdrawn"
    assert q.store.scalar("SELECT COUNT(*) FROM reviews") == reviews
    # an accepted call that will not be carried out is closed the same way
    step2, hold2 = _held_call(q, monkeypatch)
    record_review(q, hold2, "accept", reason="fine")
    r = cli(q, "abandon", "--step", step2, "--reason", "the person asked another way", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["was"] == "admissible"
    assert _run_step(q, step2) == "abandoned"
    nx = json.loads(cli(q, "next", "--json").output)
    assert nx["kind"] == "open" and nx["to_carry_out"] == []
    # closed: neither carried out nor closed twice, and the run is still open
    assert cli(q, "propose", step2, "--json").exit_code == 16
    assert cli(q, "abandon", "--step", step2, "--reason", "again", "--json").exit_code == 16
    assert q.store.scalar("SELECT status FROM runs WHERE kind = 'run'") != "abandoned"
    # a step that is not an on-demand step of this run is refused
    assert cli(q, "abandon", "--step", "no_such_step", "--reason", "x", "--json").exit_code == 16


def test_abandon_step_closes_only_its_own_call_and_never_one_that_ran(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The review of #33: closing one held call leaves another call's hold open; a completed
    call, and a call held on what it produced, are refused (their artifacts exist and the
    post-run hold is a person's)."""
    q = questions
    step_a, hold_a = _held_call(q, monkeypatch)
    step_b, hold_b = _held_call(q, monkeypatch)
    assert step_a != step_b
    r = cli(q, "abandon", "--step", step_a, "--reason", "not wanted", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["holds"] == [hold_a]
    assert [h["hold_id"] for h in queue(q)] == [hold_b] and _run_step(q, step_b) == "held"
    # completed: refused
    record_review(q, hold_b, "accept", reason="fine")
    assert cli(q, "propose", step_b, "--json").exit_code == 0
    assert _run_step(q, step_b) == "completed"
    r = cli(q, "abandon", "--step", step_b, "--reason", "x", "--json")
    assert r.exit_code == 16, r.output + str(r.stderr)
    assert _run_step(q, step_b) == "completed"
    # held after it ran (as a post-phase or item hold leaves it): refused, nothing changes
    run_id = str(q.store.scalar("SELECT run_id FROM runs WHERE kind = 'run'"))
    q.store.set_step_status(run_id, step_b, "held", {"from": "produced"})
    r = cli(q, "abandon", "--step", step_b, "--reason", "x", "--json")
    assert r.exit_code == 16, r.output + str(r.stderr)
    assert "has run" in str(r.stderr) + r.output and _run_step(q, step_b) == "held"


def test_the_console_shows_the_one_command_for_a_held_call(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The console's hold page and its JSON route carry the same after-accept commands as
    `present --hold` (L114)."""
    import html
    import threading

    from stringency.review_serve import make_server
    from tests.test_review_serve import TOKEN, get

    q = questions
    step, hold = _held_call(q, monkeypatch)
    srv = make_server([q.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        status, body = get(f"{base}/hold/{hold}?t={TOKEN}")
        assert status == 200
        text = html.unescape(body)
        assert "After an accept" in text and f"stringency propose {step}" in text
        assert f"stringency abandon --step {step}" in text
        status, body = get(f"{base}/api/hold/{hold}?t={TOKEN}")
        assert status == 200, body
        assert json.loads(body)["after_accept"]["command"] == f"stringency propose {step}"
    finally:
        srv.shutdown()
        srv.server_close()
