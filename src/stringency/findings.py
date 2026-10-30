"""Findings (open mode, the report; 2026-10-19): the answers a person marks as the ones the
report leads with. A mark is a row in the append-only `findings` table; the latest row per
answer is its state (`mark` or `unmark`). Marking can happen at any time, in any session, and
changes nothing about the answer, its label or its files; it changes which part of
`report.md` the answer appears in.

The person's arrangement of the report (L144) is recorded in `run_events`, so no trace table
changes shape: `finding_placed` sets a finding's place (`order`) and its heading in the
person's words (`heading`), the latest value of each field per answer standing; and
`story_recorded` holds the paragraph in the person's words that the report opens with, its
text in `messages`, refused when a numeral in it is no cell a finding cites and no numeral the
answers' check leaves aside. The engine never writes the story.

Reads: findings, answers, questions, messages, run_events. Writes: findings, messages,
run_events.
"""

from __future__ import annotations

import json
from typing import Any

from stringency import hashing
from stringency.answers import answer_row
from stringency.clock import now_iso
from stringency.db.store import Store
from stringency.exit_codes import ConfigError, RefusedError
from stringency.ids import new_id
from stringency.operator_id import operator_env
from stringency.predicates.engine.ans import classify_numerals, numeral_sources
from stringency.runs import RunContext
from stringency.tables import KEY_SEP


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
    no-op, reported with `changed: False` and no row. Each result names the figures attached
    to the answer (L143), which the report shows under it. The reason, when given, is the person's
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
            # the figures attached to the answer go with it (L143)
            "figures": [
                {"artifact_id": f["artifact_id"], "name": f["name"], "label": f["label"]}
                for f in (ans["provenance"].get("figures") or [])
            ],
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


# -- the person's arrangement of the report (L144) -------------------------------------------


def placements(store: Store, run_id: str) -> dict[str, dict[str, Any]]:
    """Answer id to its place in the report: `order` (an integer, or None when unset) and
    `heading` (the person's words, or None), each the latest value a `finding_placed` event
    gave it. Reads: run_events."""
    out: dict[str, dict[str, Any]] = {}
    for r in store.all(
        "SELECT payload_json FROM run_events WHERE run_id = ? AND event = 'finding_placed' "
        "ORDER BY seq",
        (run_id,),
    ):
        ev = json.loads(r["payload_json"] or "{}")
        cur = out.setdefault(str(ev.get("answer_id")), {"order": None, "heading": None})
        for k in ("order", "heading"):
            if k in ev:
                cur[k] = ev[k]
    return out


def place(
    rc: RunContext, answer_ids: list[str], *, order: int | None = None, heading: str | None = None
) -> list[dict[str, Any]]:
    """Set the place of findings in the report (L144): `order` n gives the first id place n,
    the next n+1, and so on (0 unsets it); `heading` puts each under that heading, in the
    person's words ("" removes it). Each id must be a finding of this run (exit 15). Writes:
    run_events (`finding_placed`, one per answer, carrying only the fields given)."""
    if order is None and heading is None:
        return []
    if order is not None and order < 0:
        raise ConfigError("--order takes a place from 1 (0 unsets it)")
    state = current(rc.store, rc.run_id)
    from stringency.review import current_user

    who = current_user()
    out: list[dict[str, Any]] = []
    for i, aid in enumerate(dict.fromkeys(answer_ids)):
        if aid not in state:
            raise ConfigError(f"answer {aid} is not a finding; mark it before placing it")
        payload: dict[str, Any] = {"answer_id": aid, "by": who}
        if order is not None:
            payload["order"] = order + i if order > 0 else None
        if heading is not None:
            payload["heading"] = heading.strip() or None
        rc.store.run_event(rc.run_id, "finding_placed", payload)
        out.append(payload)
    return out


def story(store: Store, run_id: str) -> dict[str, Any] | None:
    """The latest story of the run: its text, who recorded it, how and when. Reads:
    run_events, messages."""
    r = store.one(
        "SELECT payload_json, ts FROM run_events WHERE run_id = ? AND event = 'story_recorded' "
        "ORDER BY seq DESC LIMIT 1",
        (run_id,),
    )
    if r is None:
        return None
    ev = json.loads(r["payload_json"] or "{}")
    return {**ev, "text": store.message(str(ev.get("ref"))) or "", "ts": r["ts"]}


def story_numerals(
    rc: RunContext, text: str, finding_answers: list[dict[str, Any]]
) -> dict[str, list[dict[str, str]]]:
    """The story's numerals classified as an answer's are (`classify_numerals`): matched to a
    cell a finding cites, exempt (a design level, a cited row's key value, a parameter value a
    finding's path records, a numeral of a finding's question, a year, a count of animals,
    punches or replicates), or failed. Reads nothing; `finding_answers` are `answer_row`s."""
    cells: list[Any] = []
    src: dict[str, Any] = {"key": [], "param": [], "question": ""}
    for a in finding_answers:
        prov = a.get("provenance") or {}
        for rows in (prov.get("cells") or {}).values():
            for key, row in rows.items():
                src["key"] += str(key).split(KEY_SEP)
                cells += list(row.values())
        src["param"] += [str(d.get("value")) for d in prov.get("decisions") or []]
        src["question"] += " " + str(a.get("question") or "")
    return classify_numerals(
        text, cells, numeral_sources(rc.project.design, {"numeral_sources": src})
    )


def record_story(rc: RunContext, text: str) -> dict[str, Any]:
    """`deliver --story <file>` (L144): record the paragraph in the person's words that the
    report opens with. Refused (exit 16) when a numeral in it is not in a finding's cited cells
    and is not one the answers' check leaves aside; nothing is written then. Writes: messages,
    run_events (`story_recorded`: the text's hash, who, via, the session, the numerals)."""
    words = text.strip()
    if not words:
        raise ConfigError("a story needs text: a paragraph in the person's words")
    marks = current(rc.store, rc.run_id)
    found = [answer_row(rc, aid) for aid in marks]
    classes = story_numerals(rc, words, found)
    if classes["failed"]:
        raise RefusedError(
            "story refused: "
            + ", ".join(n["numeral"] for n in classes["failed"])
            + " is in no cell a finding cites"
            + ("" if found else " (no answer is marked as a finding yet)")
            + "; the story may use the findings' numbers only, or say it in words"
        )
    env = operator_env()
    from stringency.review import current_user

    ref = hashing.hash_text(words)
    rc.store.store_message(ref, words)
    payload = {
        "ref": ref,
        "by": current_user(),
        "via": "relayed" if env.get("session_ref") else "tty",
        "operator_session_ref": env.get("session_ref"),
        "findings": list(marks),
        "numerals": {"matched": len(classes["matched"]), "not_checked": classes["exempt"]},
    }
    rc.store.run_event(rc.run_id, "story_recorded", payload)
    return payload
