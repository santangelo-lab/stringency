"""Trace store: connection, WAL, migrations, and typed writers.

One database per project at `prov/run.db` (design 9.4). Every writer's docstring names the
table(s) it writes. Status mutations on the mutable tables (`runs`, `steps`, `holds`,
`consensus`, `artifacts`) go through methods that write the matching event row in the same
transaction (design 9.5); the raw connection is not exposed for writes.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from stringency.clock import now_iso
from stringency.exit_codes import ConfigError
from stringency.ids import new_id

SCHEMA_SQL = Path(__file__).with_name("schema.sql")
MIGRATIONS_DIR = Path(__file__).with_name("migrations")

APPEND_ONLY = frozenset(
    {
        "run_events",
        "step_events",
        "actions",
        "state_snapshots",
        "predicate_results",
        "executions",
        "reviews",
        "invocations",
        "messages",
        "judgments",
        "controls_runs",
        "deliveries",
        "policy_snapshots",
    }
)

MUTABLE = frozenset({"runs", "steps", "holds", "consensus", "artifacts", "projects"})

REFUSED_FSTYPES = frozenset({"cifs", "smb3", "smbfs"})


def filesystem_type(path: Path) -> str | None:
    """Filesystem type of the mount holding `path`, from /proc/mounts. None if unknown."""
    try:
        mounts = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        return None
    target = str(path.resolve())
    best: tuple[int, str] | None = None
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        mnt, fstype = parts[1], parts[2]
        mnt = mnt.replace("\\040", " ")
        covers = target == mnt or target.startswith(mnt.rstrip("/") + "/") or mnt == "/"
        if covers and (best is None or len(mnt) > best[0]):
            best = (len(mnt), fstype)
    return best[1] if best else None


def refuse_network_filesystem(path: Path) -> None:
    """Refuse a database on CIFS/SMB (design 9.4: never on CIFS)."""
    probe = path if path.exists() else path.parent
    fstype = filesystem_type(probe)
    if fstype in REFUSED_FSTYPES:
        raise ConfigError(f"refusing to open a trace database on {fstype}: {path}")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _encode(v: Any) -> Any:
    if isinstance(v, dict | list | tuple):
        return _json(v)
    if isinstance(v, bool):
        return int(v)
    return v


class Store:
    """A connection to one project's trace database."""

    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self.conn = conn
        self.path = path
        self._columns: dict[str, tuple[str, ...]] = {}

    # -- lifecycle -----------------------------------------------------------------

    @classmethod
    def open(cls, path: Path | str, *, create: bool = True) -> Store:
        p = Path(path)
        refuse_network_filesystem(p)
        if not p.exists() and not create:
            raise ConfigError(f"no trace database at {p}")
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        store = cls(conn, p)
        store.migrate()
        return store

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def migrate(self) -> None:
        """Apply schema.sql as version 1, then migrations/NNNN_*.sql in order. Forward-only.

        Writes: schema_migrations. `executescript` commits on its own, so the schema and
        each migration are applied as their own implicit transactions.
        """
        self.conn.executescript(SCHEMA_SQL.read_text())
        applied = {r[0] for r in self.conn.execute("SELECT version FROM schema_migrations")}
        if 1 not in applied:
            self.conn.execute(
                "INSERT INTO schema_migrations(version, applied) VALUES (1, ?)", (now_iso(),)
            )
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(sql_file.name.split("_", 1)[0])
            if version in applied:
                continue
            self.conn.executescript(sql_file.read_text())
            self.conn.execute(
                "INSERT INTO schema_migrations(version, applied) VALUES (?, ?)",
                (version, now_iso()),
            )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """One SQLite transaction. Nested calls join the outer transaction."""
        if self.conn.in_transaction:
            yield
            return
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    # -- generic --------------------------------------------------------------------

    def columns(self, table: str) -> tuple[str, ...]:
        if table not in self._columns:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                raise ValueError(f"unknown table {table}")
            self._columns[table] = tuple(r["name"] for r in rows)
        return self._columns[table]

    def insert(self, table: str, row: Mapping[str, Any], *, or_ignore: bool = False) -> None:
        """Insert one row. Dict and list values are stored as canonical JSON.

        Refuses to insert into `runs`, `steps`, `holds`, `consensus`, `artifacts`: those go
        through the typed writers so their event rows are written alongside.
        """
        if table in {"runs", "steps", "holds"}:
            raise ValueError(f"use the typed writer for {table}")
        cols = self.columns(table)
        unknown = set(row) - set(cols)
        if unknown:
            raise ValueError(f"unknown columns for {table}: {sorted(unknown)}")
        keys = list(row)
        values = [
            _json(v)
            if isinstance(v, dict | list | tuple)
            else (int(v) if isinstance(v, bool) else v)
            for v in (row[k] for k in keys)
        ]
        verb = "INSERT OR IGNORE" if or_ignore else "INSERT"
        sql = f"{verb} INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})"
        with self.transaction():
            self.conn.execute(sql, values)

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self.conn.execute(sql, params).fetchone()
        return row

    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = self.one(sql, params)
        return None if row is None else row[0]

    # -- messages ------------------------------------------------------------------

    def store_message(self, hash_: str, text: str) -> None:
        """Writes: messages (content-addressed; a repeat of the same hash is a no-op)."""
        self.insert("messages", {"hash": hash_, "text": text}, or_ignore=True)

    def message(self, hash_: str) -> str | None:
        text = self.scalar("SELECT text FROM messages WHERE hash = ?", (hash_,))
        return None if text is None else str(text)

    # -- runs -----------------------------------------------------------------------

    def open_run(self, row: Mapping[str, Any]) -> None:
        """Writes: runs (status from the row), run_events (`opened`)."""
        r = dict(row)
        r.setdefault("status", "running")
        r.setdefault("started", now_iso())
        with self.transaction():
            self._raw_insert("runs", r)
            self.run_event(r["run_id"], "opened", {"status": r["status"]})

    def run_event(self, run_id: str, event: str, payload: Mapping[str, Any] | None = None) -> int:
        """Writes: run_events with the next seq for the run. Returns the seq."""
        with self.transaction():
            seq = self.scalar(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM run_events WHERE run_id = ?", (run_id,)
            )
            self.conn.execute(
                "INSERT INTO run_events(run_id, seq, event, payload_json, ts) VALUES (?,?,?,?,?)",
                (run_id, seq, event, _json(payload or {}), now_iso()),
            )
            return int(seq)

    def set_run_status(
        self,
        run_id: str,
        status: str,
        payload: Mapping[str, Any] | None = None,
        *,
        ended: bool = False,
    ) -> None:
        """Writes: run_events (`status:<new>`) then runs.status (and runs.ended when closing)."""
        with self.transaction():
            self.run_event(run_id, f"status:{status}", dict(payload or {}))
            if ended:
                self.conn.execute(
                    "UPDATE runs SET status = ?, ended = ? WHERE run_id = ?",
                    (status, now_iso(), run_id),
                )
            else:
                self.conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))

    def set_run_field(self, run_id: str, field: str, value: Any) -> None:
        """Writes: run_events (`set:<field>`) then runs.<field>. For env_digest and delta."""
        if field not in self.columns("runs") or field in {"run_id", "status"}:
            raise ValueError(f"cannot set runs.{field}")
        with self.transaction():
            self.run_event(run_id, f"set:{field}", {field: value})
            self.conn.execute(f"UPDATE runs SET {field} = ? WHERE run_id = ?", (value, run_id))

    # -- steps ----------------------------------------------------------------------

    def create_step(self, row: Mapping[str, Any]) -> None:
        """Writes: steps (status `pending` unless given), step_events (`created`)."""
        r = dict(row)
        r.setdefault("status", "pending")
        r.setdefault("attempt", 0)
        with self.transaction():
            self._raw_insert("steps", r)
            self.step_event(r["run_id"], r["step_id"], "created", {"status": r["status"]})

    def step_event(
        self, run_id: str, step_id: str, event: str, payload: Mapping[str, Any] | None = None
    ) -> int:
        """Writes: step_events with the next seq for the step. Returns the seq."""
        with self.transaction():
            seq = self.scalar(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM step_events "
                "WHERE run_id = ? AND step_id = ?",
                (run_id, step_id),
            )
            self.conn.execute(
                "INSERT INTO step_events(run_id, step_id, seq, event, payload_json, ts) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, step_id, seq, event, _json(payload or {}), now_iso()),
            )
            return int(seq)

    def set_step_status(
        self,
        run_id: str,
        step_id: str,
        status: str,
        payload: Mapping[str, Any] | None = None,
        *,
        attempt: int | None = None,
        started: bool = False,
        ended: bool = False,
    ) -> None:
        """Writes: step_events (`status:<new>`, payload carries `from`), then steps.status.

        The only path that changes steps.status. Optionally bumps attempt and stamps
        started/ended.
        """
        with self.transaction():
            prev = self.scalar(
                "SELECT status FROM steps WHERE run_id = ? AND step_id = ?", (run_id, step_id)
            )
            if prev is None:
                raise ValueError(f"no step {step_id} in run {run_id}")
            body = {"from": prev, "to": status, **dict(payload or {})}
            if attempt is not None:
                body["attempt"] = attempt
            self.step_event(run_id, step_id, f"status:{status}", body)
            sets = ["status = ?"]
            vals: list[Any] = [status]
            if attempt is not None:
                sets.append("attempt = ?")
                vals.append(attempt)
            if started:
                sets.append("started = ?")
                vals.append(now_iso())
            if ended:
                sets.append("ended = ?")
                vals.append(now_iso())
            vals += [run_id, step_id]
            self.conn.execute(
                f"UPDATE steps SET {', '.join(sets)} WHERE run_id = ? AND step_id = ?", vals
            )

    # -- holds ----------------------------------------------------------------------

    def create_hold(self, row: Mapping[str, Any]) -> str:
        """Writes: holds; step_events (`hold:<kind>`) when the hold belongs to a step;
        run_events when it belongs to a run but no step. Returns hold_id."""
        r = dict(row)
        r.setdefault("hold_id", new_id())
        r.setdefault("created", now_iso())
        with self.transaction():
            self._raw_insert("holds", r)
            ev = {"hold_id": r["hold_id"], "kind": r["kind"], "item_id": r.get("item_id")}
            if r.get("run_id") and r.get("step_id"):
                self.step_event(r["run_id"], r["step_id"], f"hold:{r['kind']}", ev)
            elif r.get("run_id"):
                self.run_event(r["run_id"], f"hold:{r['kind']}", ev)
        return str(r["hold_id"])

    def resolve_hold(self, hold_id: str, review_id: str, via: str) -> None:
        """Writes: holds.resolved_by_review and resolved_via; step_events or run_events
        (`hold_resolved`). The review row must already exist."""
        with self.transaction():
            h = self.one("SELECT * FROM holds WHERE hold_id = ?", (hold_id,))
            if h is None:
                raise ValueError(f"no hold {hold_id}")
            if h["resolved_by_review"] is not None:
                raise ValueError(f"hold {hold_id} already resolved")
            ev = {"hold_id": hold_id, "review_id": review_id, "via": via}
            if h["run_id"] and h["step_id"]:
                self.step_event(h["run_id"], h["step_id"], "hold_resolved", ev)
            elif h["run_id"]:
                self.run_event(h["run_id"], "hold_resolved", ev)
            self.conn.execute(
                "UPDATE holds SET resolved_by_review = ?, resolved_via = ? WHERE hold_id = ?",
                (review_id, via, hold_id),
            )

    # -- consensus and artifacts ---------------------------------------------------

    def set_consensus(self, row: Mapping[str, Any]) -> None:
        """Writes: consensus (insert or replace for the item), step_events (`consensus`)."""
        r = dict(row)
        with self.transaction():
            self.step_event(
                r["run_id"],
                r["step_id"],
                "consensus",
                {"item_id": r["item_id"], "label": r.get("label"), "source": r["source"]},
            )
            self._raw_insert("consensus", r, replace=True)

    def add_artifact(self, row: Mapping[str, Any]) -> str:
        """Writes: artifacts; step_events (`artifact`). Returns artifact_id."""
        r = dict(row)
        r.setdefault("artifact_id", new_id())
        with self.transaction():
            self._raw_insert("artifacts", r)
            self.step_event(
                r["run_id"],
                r["step_id"],
                "artifact",
                {"artifact_id": r["artifact_id"], "path": r["path"], "hash": r["hash"]},
            )
        return str(r["artifact_id"])

    def set_artifact_flag(self, artifact_id: str, field: str, value: Any) -> None:
        """Writes: step_events (`artifact:<field>`) then artifacts.<field>.
        `field` is one of is_final, provisional, status, operator_session_ref,
        operator_artifact_ref."""
        if field not in {
            "is_final",
            "provisional",
            "status",
            "operator_session_ref",
            "operator_artifact_ref",
        }:
            raise ValueError(f"cannot set artifacts.{field}")
        with self.transaction():
            a = self.one(
                "SELECT run_id, step_id FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            )
            if a is None:
                raise ValueError(f"no artifact {artifact_id}")
            self.step_event(
                a["run_id"],
                a["step_id"],
                f"artifact:{field}",
                {"artifact_id": artifact_id, field: value},
            )
            v = int(value) if isinstance(value, bool) else value
            self.conn.execute(
                f"UPDATE artifacts SET {field} = ? WHERE artifact_id = ?", (v, artifact_id)
            )

    # -- policy snapshots -----------------------------------------------------------

    def record_policy_snapshot(
        self, digest: str, version: str, content: Any, predicate_set: list[str]
    ) -> None:
        """Writes: policy_snapshots (first sighting only)."""
        self.insert(
            "policy_snapshots",
            {
                "policy_digest": digest,
                "policy_version": version,
                "content_json": content,
                "predicate_set_json": predicate_set,
                "first_seen": now_iso(),
            },
            or_ignore=True,
        )

    # -- internals -----------------------------------------------------------------

    def _raw_insert(self, table: str, row: Mapping[str, Any], *, replace: bool = False) -> None:
        cols = self.columns(table)
        unknown = set(row) - set(cols)
        if unknown:
            raise ValueError(f"unknown columns for {table}: {sorted(unknown)}")
        keys = list(row)
        values = [
            _json(v)
            if isinstance(v, dict | list | tuple)
            else (int(v) if isinstance(v, bool) else v)
            for v in (row[k] for k in keys)
        ]
        verb = "INSERT OR REPLACE" if replace else "INSERT"
        self.conn.execute(
            f"{verb} INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})", values
        )
