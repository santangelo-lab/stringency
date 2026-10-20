"""Findings (open mode, the report; 2026-10-19): the answers a person marks as the ones the
report leads with. A mark is a row in the append-only `findings` table; the latest row per
answer is its state (`mark` or `unmark`). Marking can happen at any time, in any session, and
changes nothing about the answer, its label or its files; it changes which part of
`report.md` the answer appears in.

Reads: findings, answers, questions, messages. Writes: findings, messages, run_events.
"""

from __future__ import annotations

from typing import Any

from stringency import hashing
from stringency.answers import answer_row
from stringency.clock import now_iso
from stringency.db.store import Store
from stringency.exit_codes import ConfigError
from stringency.ids import new_id
from stringency.operator_id import operator_env
from stringency.runs import RunContext


def current(store: Store, run_id: str) -> dict[str, dict[str, Any]]:
    """The answers of the run that are findings now: answer id to the `mark` row that made it
    one, with the reason's words under `reason`. An answer whose latest row is `unmark`, or
    which has no row, is absent. Reads: findings, messages."""
    out: dict[str, dict[str, Any]] = {}
    for r in store.all(
        "SELECT f.* FROM findings f WHERE f.run_id = ? AND f.rowid = "
        "(SELECT MAX(g.rowid) FROM findings g WHERE g.answer_id = f.answer_id) "
        "ORDER BY f.rowid",
        (run_id,),
    ):
        if r["action"] != "mark":
            continue
        row = dict(r)
        row["reason"] = store.message(r["reason_ref"]) if r["reason_ref"] else None
        out[str(r["answer_id"])] = row
    return out


def mark(
    rc: RunContext, answer_ids: list[str], *, reason: str | None = None, remove: bool = False
) -> list[dict[str, Any]]:
    """Mark (or with `remove`, unmark) answers as findings. Each id must be an admissible
    answer of this run (exit 15 otherwise). An answer already in the asked-for state is a
    no-op, reported with `changed: False` and no row. The reason, when given, is the person's
    words, stored content-addressed. Writes: messages, findings, run_events."""
    store = rc.store
    env = operator_env()
    state = current(store, rc.run_id)
    reason_ref = None
    if reason and reason.strip():
        reason_ref = hashing.hash_text(reason.strip())
        store.store_message(reason_ref, reason.strip())
    from stringency.review import current_user

    who = current_user()
    out: list[dict[str, Any]] = []
    for aid in dict.fromkeys(answer_ids):
        ans = answer_row(rc, aid)
        if ans["status"] != "admissible":
            raise ConfigError(
                f"answer {aid} is {ans['status']}; only an admissible answer can be a finding"
            )
        is_finding = aid in state
        action = "unmark" if remove else "mark"
        result = {
            "answer_id": aid,
            "question_id": ans["question_id"],
            "question_seq": ans.get("seq"),
            "question": ans["question"],
            "action": action,
            "changed": is_finding == remove,
        }
        if result["changed"]:
            row = {
                "finding_id": new_id(),
                "run_id": rc.run_id,
                "question_id": ans["question_id"],
                "answer_id": aid,
                "action": action,
                "marked_by": who,
                "via": "relayed" if env.get("session_ref") else "tty",
                "operator_session_ref": env.get("session_ref"),
                "reason_ref": reason_ref,
                "ts": now_iso(),
            }
            store.insert("findings", row)
            store.run_event(
                rc.run_id,
                "finding_marked" if action == "mark" else "finding_unmarked",
                {"answer_id": aid, "question_id": ans["question_id"], "by": who},
            )
        out.append(result)
    return out
