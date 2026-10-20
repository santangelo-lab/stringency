"""Read the trace back against its own history (trace-integrity-plan.md T2, backlog L51).

The Store's typed writers write an event for every change to a mutable row, but the schema does
not require it: a direct `UPDATE` on `steps`, `runs`, `holds`, `consensus` or `artifacts`
changes the row and leaves the history as it was. `audit` reads the current rows and the event
tables in one read transaction on a read-only connection and reports every disagreement. It
names; it never repairs. `stringency audit` prints the findings; `prov.trace_inconsistent`
blocks run open and deliver on them; `coverage.md` states the result.

What it cannot see: a change made together with a forged event (the event tables accept
inserts), which is T3 of the plan; and a database replaced whole, which is T4.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from stringency.db.store import MIGRATIONS_DIR, SCHEMA_SQL, Store


@dataclass(frozen=True)
class Finding:
    table: str
    key: str
    current: str
    recorded: str
    seq: int | None
    note: str

    def line(self) -> str:
        at = f" (event seq {self.seq})" if self.seq is not None else ""
        return f"{self.table} {self.key}: now {self.current}, history says {self.recorded}{at}; {self.note}"

    def to_json(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "key": self.key,
            "current": self.current,
            "recorded": self.recorded,
            "seq": self.seq,
            "note": self.note,
        }


def expected_triggers() -> set[str]:
    """The trigger names `schema.sql` and the migrations install."""
    names: set[str] = set()
    for text in [SCHEMA_SQL.read_text()] + [
        p.read_text() for p in sorted(MIGRATIONS_DIR.glob("*.sql"))
    ]:
        names.update(re.findall(r"CREATE TRIGGER IF NOT EXISTS (\w+)", text))
    return names


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        v = json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return v if isinstance(v, dict) else {}


def _steps(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for s in conn.execute("SELECT run_id, step_id, status, attempt FROM steps"):
        ev = conn.execute(
            "SELECT event, payload_json, seq FROM step_events WHERE run_id = ? AND step_id = ? "
            "AND (event LIKE 'status:%' OR event = 'created') ORDER BY seq DESC LIMIT 1",
            (s["run_id"], s["step_id"]),
        ).fetchone()
        key = f"{s['run_id']}/{s['step_id']}"
        if ev is None:
            out.append(
                Finding(
                    "steps", key, str(s["status"]), "no event", None, "a step with no created event"
                )
            )
            continue
        p = _payload(ev)
        recorded = (
            ev["event"][len("status:") :]
            if ev["event"].startswith("status:")
            else str(p.get("status", "pending"))
        )
        if recorded != s["status"]:
            out.append(
                Finding(
                    "steps",
                    key,
                    f"status {s['status']}",
                    f"status {recorded}",
                    ev["seq"],
                    "the status changed without a status event",
                )
            )
        with_attempt = conn.execute(
            "SELECT payload_json, seq FROM step_events WHERE run_id = ? AND step_id = ? "
            "AND event LIKE 'status:%' AND payload_json LIKE '%\"attempt\"%' ORDER BY seq DESC LIMIT 1",
            (s["run_id"], s["step_id"]),
        ).fetchone()
        if with_attempt is not None:
            pa = _payload(with_attempt)
            if "attempt" in pa and pa["attempt"] != s["attempt"]:
                out.append(
                    Finding(
                        "steps",
                        key,
                        f"attempt {s['attempt']}",
                        f"attempt {pa['attempt']}",
                        with_attempt["seq"],
                        "the attempt changed without a status event",
                    )
                )


def _runs(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for r in conn.execute("SELECT run_id, status FROM runs"):
        ev = conn.execute(
            "SELECT event, payload_json, seq FROM run_events WHERE run_id = ? "
            "AND (event LIKE 'status:%' OR event = 'opened') ORDER BY seq DESC LIMIT 1",
            (r["run_id"],),
        ).fetchone()
        if ev is None:
            out.append(
                Finding(
                    "runs",
                    r["run_id"],
                    str(r["status"]),
                    "no event",
                    None,
                    "a run with no opened event",
                )
            )
            continue
        recorded = (
            ev["event"][len("status:") :]
            if ev["event"].startswith("status:")
            else str(_payload(ev).get("status", "running"))
        )
        if recorded != r["status"]:
            out.append(
                Finding(
                    "runs",
                    r["run_id"],
                    f"status {r['status']}",
                    f"status {recorded}",
                    ev["seq"],
                    "the status changed without a status event",
                )
            )


def _holds(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for h in conn.execute(
        "SELECT hold_id, run_id, step_id, resolved_by_review, resolved_via FROM holds"
    ):
        rid, via = h["resolved_by_review"], h["resolved_via"]
        if rid is None and via is None:
            continue
        if rid is not None:
            if conn.execute("SELECT 1 FROM reviews WHERE review_id = ?", (rid,)).fetchone() is None:
                out.append(
                    Finding(
                        "holds",
                        h["hold_id"],
                        f"resolved by {rid}",
                        "no such review",
                        None,
                        "resolved_by_review names a review that does not exist",
                    )
                )
            if not h["run_id"]:
                continue  # a project-level hold (confirm, egress) is recorded by its review alone
            ev = _hold_event(conn, h, "hold_resolved")
            if ev is None or _payload(ev).get("review_id") != rid:
                out.append(
                    Finding(
                        "holds",
                        h["hold_id"],
                        f"resolved by {rid}",
                        "no hold_resolved event for it",
                        None,
                        "the resolution has no event",
                    )
                )
            elif _payload(ev).get("via") != via:
                out.append(
                    Finding(
                        "holds",
                        h["hold_id"],
                        f"via {via}",
                        f"via {_payload(ev).get('via')}",
                        ev["seq"],
                        "the route of the resolution changed without an event",
                    )
                )
        elif via == "withdrawn" and _hold_event(conn, h, "hold_withdrawn") is None:
            out.append(
                Finding(
                    "holds",
                    h["hold_id"],
                    "withdrawn",
                    "no hold_withdrawn event",
                    None,
                    "the withdrawal has no event",
                )
            )


def _hold_event(conn: sqlite3.Connection, h: sqlite3.Row, event: str) -> sqlite3.Row | None:
    rows: list[sqlite3.Row]
    if h["run_id"] and h["step_id"]:
        rows = conn.execute(
            "SELECT payload_json, seq FROM step_events WHERE run_id = ? AND step_id = ? AND event = ? ORDER BY seq DESC",
            (h["run_id"], h["step_id"], event),
        ).fetchall()
    elif h["run_id"]:
        rows = conn.execute(
            "SELECT payload_json, seq FROM run_events WHERE run_id = ? AND event = ? ORDER BY seq DESC",
            (h["run_id"], event),
        ).fetchall()
    else:
        return None  # a project-level hold (confirm, egress) is resolved through reviews alone
    for r in rows:
        if _payload(r).get("hold_id") == h["hold_id"]:
            return r
    return None


def _consensus(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for c in conn.execute("SELECT run_id, step_id, item_id, label FROM consensus"):
        rows = conn.execute(
            "SELECT payload_json, seq FROM step_events WHERE run_id = ? AND step_id = ? AND event = 'consensus' ORDER BY seq DESC",
            (c["run_id"], c["step_id"]),
        ).fetchall()
        ev = next((r for r in rows if _payload(r).get("item_id") == c["item_id"]), None)
        key = f"{c['run_id']}/{c['step_id']}/{c['item_id']}"
        if ev is None:
            out.append(
                Finding(
                    "consensus",
                    key,
                    f"label {c['label']}",
                    "no consensus event",
                    None,
                    "a consensus row with no event",
                )
            )
        elif _payload(ev).get("label") != c["label"]:
            out.append(
                Finding(
                    "consensus",
                    key,
                    f"label {c['label']}",
                    f"label {_payload(ev).get('label')}",
                    ev["seq"],
                    "the label changed without a consensus event",
                )
            )


def _artifacts(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for a in conn.execute(
        "SELECT artifact_id, run_id, step_id, is_final FROM artifacts WHERE is_final = 1"
    ):
        rows = conn.execute(
            "SELECT payload_json, seq FROM step_events WHERE run_id = ? AND step_id = ? AND event = 'artifact:is_final' ORDER BY seq DESC",
            (a["run_id"], a["step_id"]),
        ).fetchall()
        ev = next((r for r in rows if _payload(r).get("artifact_id") == a["artifact_id"]), None)
        if ev is None or not _payload(ev).get("is_final"):
            out.append(
                Finding(
                    "artifacts",
                    a["artifact_id"],
                    "final",
                    "no artifact:is_final event",
                    None,
                    "marked final without the event",
                )
            )


def _sequences(conn: sqlite3.Connection, out: list[Finding]) -> None:
    for r in conn.execute(
        "SELECT run_id, COUNT(*) AS n, MIN(seq) AS lo, MAX(seq) AS hi FROM run_events GROUP BY run_id"
    ):
        if r["lo"] != 1 or r["hi"] != r["n"]:
            out.append(
                Finding(
                    "run_events",
                    r["run_id"],
                    f"{r['n']} events, seq {r['lo']} to {r['hi']}",
                    "1 to n",
                    None,
                    "a gap in the sequence",
                )
            )
    for r in conn.execute(
        "SELECT run_id, step_id, COUNT(*) AS n, MIN(seq) AS lo, MAX(seq) AS hi FROM step_events GROUP BY run_id, step_id"
    ):
        if r["lo"] != 1 or r["hi"] != r["n"]:
            out.append(
                Finding(
                    "step_events",
                    f"{r['run_id']}/{r['step_id']}",
                    f"{r['n']} events, seq {r['lo']} to {r['hi']}",
                    "1 to n",
                    None,
                    "a gap in the sequence",
                )
            )


def _triggers(conn: sqlite3.Connection, out: list[Finding]) -> None:
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
    for name in sorted(expected_triggers() - present):
        out.append(
            Finding(
                "sqlite_master",
                name,
                "absent",
                "installed by the schema",
                None,
                "an append-only trigger is missing",
            )
        )


def audit(store: Store) -> list[Finding]:
    """Reads, read-only, in one transaction: steps, runs, holds, reviews, consensus, artifacts,
    run_events, step_events, sqlite_master. Writes nothing."""
    conn = store.reader()
    out: list[Finding] = []
    conn.execute("BEGIN")
    try:
        for check in (_steps, _runs, _holds, _consensus, _artifacts, _sequences, _triggers):
            check(conn, out)
    finally:
        conn.execute("ROLLBACK")
    return out


def audit_lines(store: Store) -> tuple[str, ...]:
    return tuple(f.line() for f in audit(store))
