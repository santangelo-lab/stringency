"""Questions of an open run (open_mode_plan.md 1 and 2.3, 2026-10-16).

A question is the person's words verbatim, filed before anything runs for it. `origin` tells
the two populations apart: `person` (their own words) and `suggested` (a path the operator
proposed before the switch and the person picked). The reply is an `answers` row (S5).

Reads: runs, questions. Writes: questions, messages.
"""

from __future__ import annotations

from typing import Any

from stringency import hashing
from stringency.clock import now_iso
from stringency.exit_codes import ConfigError, RefusedError
from stringency.ids import new_id
from stringency.operator_id import operator_env
from stringency.project import Project
from stringency.runs import CLOSED_STATUSES, RunContext, latest_run, open_or_resume

ORIGINS = ("person", "suggested")


def open_for_questions(project: Project) -> RunContext:
    """The open run questions are filed on: the latest open run, or a new one when none is
    open (the confirm hold is enforced by `open_or_resume`). Refused on a pipeline project."""
    if not project.open_ended:
        raise RefusedError(
            "ask files a question in an open project; this project runs a declared pipeline"
        )
    last = latest_run(project.store)
    new = last is not None and last["status"] in CLOSED_STATUSES
    return open_or_resume(project, new=new)


def file_question(
    rc: RunContext, text: str, *, origin: str = "person", via: str | None = None
) -> dict[str, Any]:
    """Writes: messages (the words, content-addressed), questions. Returns the row."""
    if origin not in ORIGINS:
        raise ConfigError(f"origin must be one of {', '.join(ORIGINS)}")
    words = text.strip()
    if not words:
        raise ConfigError("a question needs words")
    store = rc.store
    ref = hashing.hash_text(words)
    store.store_message(ref, words)
    env = operator_env()
    seq = int(
        store.scalar(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM questions WHERE run_id = ?", (rc.run_id,)
        )
    )
    row = {
        "question_id": new_id(),
        "run_id": rc.run_id,
        "seq": seq,
        "text_ref": ref,
        "origin": origin,
        "asked_via": via or ("relayed" if env.get("session_ref") else "tty"),
        "operator_session_ref": env.get("session_ref"),
        "ts": now_iso(),
    }
    store.insert("questions", row)
    return {**row, "text": words}


def question(rc: RunContext, question_id: str) -> dict[str, Any]:
    """Reads: questions, messages. ConfigError when the id is not a question of this run."""
    row = rc.store.one(
        "SELECT * FROM questions WHERE run_id = ? AND question_id = ?", (rc.run_id, question_id)
    )
    if row is None:
        raise ConfigError(f"no question {question_id} in run {rc.run_id}")
    return {**dict(row), "text": rc.store.message(row["text_ref"]) or ""}
