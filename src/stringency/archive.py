"""The archive marker (L132): `prov/archived.json`, written by `stringency archive --reason` or
by hand. A project carrying it is put away: `board` skips it and the console lists it under
"archived" instead of among the projects at work. The trace is not touched; removing the file
brings the project back as it was.

Reads: the marker; for the notes, `holds` and `runs` over a read-only connection. Writes: the
marker only.
"""

from __future__ import annotations

import getpass
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from stringency.clock import now_iso
from stringency.exit_codes import ConfigError, RefusedError

MARKER = Path("prov") / "archived.json"


def marker_path(root: Path) -> Path:
    return Path(root) / MARKER


def archived(root: Path) -> dict[str, Any] | None:
    """The marker's record, or None when the project is not archived. A marker that cannot be
    read still archives the project; its reason says so."""
    p = marker_path(root)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text() or "{}")
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {
        "reason": str(data.get("reason") or "no reason recorded in the marker"),
        "by": str(data.get("by") or ""),
        "ts": str(data.get("ts") or ""),
        "marker": str(p),
    }


def _open_holds(root: Path) -> int:
    db = Path(root) / "prov" / "run.db"
    if not db.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM holds WHERE resolved_by_review IS NULL "
                "AND resolved_via IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return 0
    return int(n or 0)


def archive_project(root: Path, reason: str) -> tuple[dict[str, Any], list[str]]:
    """Write the marker. Refuses an empty reason (15) and a project already archived (16, with
    the earlier reason). Returns the record and notes for the person (open holds stay open and
    leave the console's inbox). Writes: `prov/archived.json`."""
    words = reason.strip()
    if not words:
        raise ConfigError("archive needs --reason in words: why the project is put away")
    prior = archived(root)
    if prior is not None:
        raise RefusedError(
            f"{Path(root).name} is already archived ({prior['ts']}: {prior['reason']}); "
            f"remove {prior['marker']} to bring it back"
        )
    from stringency.operator_id import operator_env

    record = {
        "reason": words,
        "by": os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser(),
        "ts": now_iso(),
        "session_ref": operator_env().get("session_ref"),
    }
    p = marker_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(record, indent=2) + "\n")
    notes: list[str] = []
    n = _open_holds(root)
    if n:
        notes.append(f"{n} open hold(s) stay open in the trace; the console no longer lists them")
    return {**record, "marker": str(p)}, notes
