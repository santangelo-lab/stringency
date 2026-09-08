import json
import sqlite3
from pathlib import Path

import pytest

from stringency import hashing
from stringency.db.store import APPEND_ONLY, Store, filesystem_type
from stringency.exit_codes import ConfigError
from stringency.ids import new_id


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store.open(tmp_path / "prov" / "run.db")
    yield s
    s.close()


def _seed_project_and_run(store: Store) -> str:
    store.insert(
        "projects",
        {
            "project_id": "P1",
            "path": "/x",
            "pipeline_name": "toy",
            "pipeline_version": "0.1.0",
            "pipeline_digest": "d",
            "method_repo": "r",
            "method_tag": "v0",
            "mode": "pipeline",
            "profile": "standard",
            "owner": "o",
            "reviewer": "o",
            "judgment_harness": "mock",
            "executor": "local",
            "objective_json": {},
            "design_json": {},
            "created": "t",
            "stringency_version": "0",
        },
    )
    run_id = new_id()
    store.open_run(
        {
            "run_id": run_id,
            "project_id": "P1",
            "git_sha": "abc",
            "git_dirty": False,
            "host": "h",
            "user": "u",
            "policy_version": "0.1.0",
            "policy_digest": "pd",
            "stringency_version": "0",
        }
    )
    return run_id


def test_schema_creates_from_empty(store: Store) -> None:
    tables = {r[0] for r in store.all("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in APPEND_ONLY | {
        "projects",
        "runs",
        "steps",
        "holds",
        "consensus",
        "artifacts",
        "schema_migrations",
    }:
        assert t in tables, t
    assert store.scalar("PRAGMA journal_mode") == "wal"
    assert store.scalar("SELECT version FROM schema_migrations") == 1


def test_reopen_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "run.db"
    Store.open(p).close()
    s = Store.open(p)
    # schema.sql is version 1; every file under db/migrations/ adds one
    from stringency.db.store import MIGRATIONS_DIR

    n_migrations = 1 + len(list(MIGRATIONS_DIR.glob("*.sql")))
    assert s.scalar("SELECT COUNT(*) FROM schema_migrations") == n_migrations
    assert "expected_env_digest" in s.columns("executions")
    s.close()


@pytest.mark.parametrize("table", sorted(APPEND_ONLY))
def test_append_only_tables_raise_on_update_and_delete(store: Store, table: str) -> None:
    run_id = _seed_project_and_run(store)
    # a row exists in run_events after open_run; for other tables insert a minimal row
    if table == "run_events":
        pass
    elif table == "step_events":
        store.create_step(
            {
                "run_id": run_id,
                "step_id": "s1",
                "module": "m",
                "module_version": "1",
                "operation": "op",
            }
        )
    elif table == "messages":
        store.store_message("h", "text")
    elif table == "policy_snapshots":
        store.record_policy_snapshot("pd", "0.1.0", {}, [])
    else:
        cols = store.columns(table)
        row = {}
        info = store.all(f"PRAGMA table_info({table})")
        for c in info:
            if c["notnull"] and c["dflt_value"] is None:
                name = c["name"]
                if name in ("run_id",):
                    row[name] = run_id
                elif name == "hold_id":
                    hid = store.create_hold(
                        {"run_id": run_id, "kind": "flag", "reason": "r", "waits_on_role": "owner"}
                    )
                    row[name] = hid
                elif c["type"] == "INTEGER":
                    row[name] = 1
                else:
                    row[name] = "x"
        assert set(row) <= set(cols)
        store.insert(table, row)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute(f"UPDATE {table} SET {store.columns(table)[-1]} = NULL")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute(f"DELETE FROM {table}")


def test_step_status_mutation_writes_event_in_same_transaction(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    store.create_step(
        {"run_id": run_id, "step_id": "s1", "module": "m", "module_version": "1", "operation": "op"}
    )
    store.set_step_status(run_id, "s1", "proposed", attempt=1)
    events = store.all(
        "SELECT event, payload_json FROM step_events WHERE step_id='s1' ORDER BY seq"
    )
    assert [e["event"] for e in events] == ["created", "status:proposed"]
    assert json.loads(events[1]["payload_json"])["from"] == "pending"
    assert store.scalar("SELECT status FROM steps WHERE step_id='s1'") == "proposed"


def test_store_api_refuses_raw_insert_into_mutable_status_tables(store: Store) -> None:
    with pytest.raises(ValueError, match="typed writer"):
        store.insert("steps", {"run_id": "r", "step_id": "s"})


def test_set_step_status_is_atomic_with_event(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _seed_project_and_run(store)
    store.create_step(
        {"run_id": run_id, "step_id": "s1", "module": "m", "module_version": "1", "operation": "op"}
    )
    # force the event write to fail: the status must not change either
    orig = store.step_event

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("event write failed")

    monkeypatch.setattr(store, "step_event", boom)
    with pytest.raises(RuntimeError):
        store.set_step_status(run_id, "s1", "proposed")
    monkeypatch.setattr(store, "step_event", orig)
    assert store.scalar("SELECT status FROM steps WHERE step_id='s1'") == "pending"
    assert store.scalar("SELECT COUNT(*) FROM step_events WHERE step_id='s1'") == 1


def test_hold_create_and_resolve(store: Store) -> None:
    run_id = _seed_project_and_run(store)
    store.create_step(
        {"run_id": run_id, "step_id": "s1", "module": "m", "module_version": "1", "operation": "op"}
    )
    hid = store.create_hold(
        {
            "run_id": run_id,
            "step_id": "s1",
            "kind": "flag",
            "reason": "r",
            "waits_on_role": "reviewer",
        }
    )
    store.insert(
        "reviews",
        {
            "review_id": "R1",
            "hold_id": hid,
            "reviewer": "u",
            "host": "h",
            "via": "tty",
            "ts": "t",
            "verdict": "accept",
            "reason": "ok",
        },
    )
    store.resolve_hold(hid, "R1", "tty")
    h = store.one("SELECT * FROM holds WHERE hold_id=?", (hid,))
    assert h["resolved_by_review"] == "R1"
    with pytest.raises(ValueError, match="already resolved"):
        store.resolve_hold(hid, "R1", "tty")
    events = [e["event"] for e in store.all("SELECT event FROM step_events WHERE step_id='s1'")]
    assert "hold:flag" in events and "hold_resolved" in events


def test_refuses_cifs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.db.store.filesystem_type", lambda p: "cifs")
    with pytest.raises(ConfigError, match="cifs"):
        Store.open(tmp_path / "run.db")


def test_filesystem_type_returns_something_for_tmp(tmp_path: Path) -> None:
    assert filesystem_type(tmp_path) is not None


# -- hashing -----------------------------------------------------------------------


def test_canonical_json_hash_stable_under_key_order() -> None:
    a = {"b": 1, "a": {"y": [1, 2], "x": None}}
    b = {"a": {"x": None, "y": [1, 2]}, "b": 1}
    assert hashing.hash_json(a) == hashing.hash_json(b)
    assert hashing.hash_json(a) != hashing.hash_json({"b": 2, "a": {"y": [1, 2], "x": None}})


def test_dir_hash_changes_on_one_byte(tmp_path: Path) -> None:
    d = tmp_path / "d"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_bytes(b"hello")
    (d / "sub" / "b.txt").write_bytes(b"world")
    h1 = hashing.hash_dir(d)
    (d / "sub" / "b.txt").write_bytes(b"worle")
    assert hashing.hash_dir(d) != h1
    (d / "sub" / "b.txt").write_bytes(b"world")
    assert hashing.hash_dir(d) == h1
    (d / "sub" / "b.txt").rename(d / "sub" / "c.txt")
    assert hashing.hash_dir(d) != h1


def test_file_hash_matches_bytes(tmp_path: Path) -> None:
    f = tmp_path / "f"
    f.write_bytes(b"abc" * 100000)
    assert hashing.hash_file(f) == hashing.hash_bytes(b"abc" * 100000)
    assert hashing.prefixed("ab") == "blake3:ab"
    assert hashing.strip_prefix("blake3:ab") == "ab"
