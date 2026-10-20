"""`stringency audit` and `prov.trace_inconsistent` (trace-integrity-plan.md T2, backlog L51):
a mutable row changed by direct SQL disagrees with its events; the audit names it, run open and
deliver are blocked on it, and a healthy trace whose last event is not a status event is clean."""

from __future__ import annotations

import json
import sqlite3

import pytest

from stringency.audit import Finding, audit, expected_triggers
from stringency.db.store import Store
from stringency.predicates.context import Verdict
from stringency.predicates.engine.trace_ import trace_inconsistent
from tests.helpers import make_ctx
from tests.test_run import cli
from tests.test_store import _seed_project_and_run


@pytest.fixture
def store(tmp_path) -> Store:  # type: ignore[no-untyped-def]
    return Store.open(tmp_path / "run.db")


def _step(store: Store, run_id: str, step_id: str = "s1") -> None:
    store.create_step(
        {
            "run_id": run_id,
            "step_id": step_id,
            "module": "m",
            "module_version": "1",
            "operation": "op",
        }
    )


def test_healthy_trace_audits_clean_when_the_last_event_is_not_a_status(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    _step(store, run_id)
    store.set_step_status(run_id, "s1", "proposed", attempt=1)
    store.add_artifact(
        {
            "run_id": run_id,
            "step_id": "s1",
            "name": "x",
            "kind": "table",
            "path": "/x",
            "hash": "h",
            "size": 1,
        }
    )
    assert audit(store) == []


def test_a_status_changed_by_direct_sql_is_found(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    _step(store, run_id)
    store.set_step_status(run_id, "s1", "proposed", attempt=1)
    store._conn.execute("UPDATE steps SET status = 'completed' WHERE step_id = 's1'")
    found = audit(store)
    assert len(found) == 1 and found[0].table == "steps" and "completed" in found[0].current
    assert "proposed" in found[0].recorded and found[0].seq == 2
    store._conn.execute("UPDATE runs SET status = 'completed'")
    assert {f.table for f in audit(store)} == {"steps", "runs"}


def test_a_dropped_trigger_and_a_sequence_gap_are_found(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    _step(store, run_id)
    assert "ao_step_events_u" in expected_triggers()
    store._conn.execute("DROP TRIGGER ao_step_events_u")
    store._conn.execute(
        "INSERT INTO step_events(run_id, step_id, seq, event, payload_json, ts) VALUES (?, 's1', 9, 'note', '{}', 't')",
        (run_id,),
    )
    tables = {f.table: f for f in audit(store)}
    assert tables["sqlite_master"].key == "ao_step_events_u"
    assert "gap" in tables["step_events"].note


def test_a_hold_resolved_without_its_review_is_found(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    _step(store, run_id)
    hid = store.create_hold(
        {"run_id": run_id, "step_id": "s1", "kind": "flag", "reason": "r", "waits_on_role": "owner"}
    )
    store._conn.execute(
        "UPDATE holds SET resolved_by_review = 'nope', resolved_via = 'relayed' WHERE hold_id = ?",
        (hid,),
    )
    notes = [f.note for f in audit(store)]
    assert any("does not exist" in n for n in notes) and any("no event" in n for n in notes)


def test_predicate_fires_on_findings_and_passes_without(project) -> None:  # type: ignore[no-untyped-def]
    ctx = make_ctx(project, "01_filter")
    assert trace_inconsistent(ctx) == Verdict(False)
    pc = ctx.project.__class__(
        **{**ctx.project.__dict__, "trace_findings": ("steps r/s: now x, history says y; z",)}
    )
    v = trace_inconsistent(ctx.__class__(**{**ctx.__dict__, "project": pc}))
    assert v.fired and "stringency audit" in v.reason and v.evidence["findings"]


def test_deliver_and_run_open_are_blocked_on_a_tampered_trace(make_project) -> None:  # type: ignore[no-untyped-def]
    """A completed toy run: `deliver` writes the audit line into coverage.md; after a step's
    status is rewritten by hand, `deliver` is refused and a new run cannot open."""
    from tests.test_deliver import completed_project
    from tests.test_run import MOCK

    p, run_id = completed_project(make_project)
    r = cli(p, "deliver", "--json", env=MOCK)
    assert r.exit_code == 0, r.output + str(r.stderr)
    coverage = (p.root / "deliver" / run_id / "coverage.md").read_text()
    assert "trace audited: no disagreement" in coverage
    # the attempt rewritten by hand (a status rewrite would stop deliver before its gate)
    p.store._conn.execute("UPDATE steps SET attempt = attempt + 7 WHERE step_id = '01_filter'")
    r = cli(p, "audit")
    assert r.exit_code == 1 and "01_filter" in r.output and "attempt" in r.output
    r = cli(p, "deliver", "--json", env=MOCK)
    assert r.exit_code == 16, r.output + str(r.stderr)
    assert "prov.trace_inconsistent" in (r.output + str(r.stderr))
    r = cli(p, "run", "--new", "--json", env=MOCK)
    assert r.exit_code == 11, r.output + str(r.stderr)
    assert "prov.trace_inconsistent" in r.output


def test_finding_line_and_json() -> None:
    f = Finding("steps", "r/s", "status a", "status b", 3, "why")
    assert f.line() == "steps r/s: now status a, history says status b (event seq 3); why"
    assert f.to_json()["seq"] == 3


def test_audit_reads_only(store: Store) -> None:
    _seed_project_and_run(store)
    before = store._conn.execute("SELECT COUNT(*) FROM run_events").fetchone()[0]
    audit(store)
    assert store._conn.execute("SELECT COUNT(*) FROM run_events").fetchone()[0] == before
    with pytest.raises(sqlite3.OperationalError):
        store.reader().execute("INSERT INTO messages(hash, text) VALUES ('a', 'b')")
    assert json.loads(json.dumps([f.to_json() for f in audit(store)])) == []
