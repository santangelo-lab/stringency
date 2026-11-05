"""Flags (the beta-tester package, 2026-11-03): a person says, after delivery, that a result is
wrong. A flag is a review that happens after delivery with no hold to resolve: it records who
said so, when, through what (`tty`, `relayed`, `web`), the delivered file that was on screen by
name and blake3, the step it came from when the delivery index names one, and the person's
words. It changes nothing about the run; it is the record the eval store reads for the
failures a person caught after delivery (plan section 7, catch point 3).

Reads: runs, deliveries, messages, flags. Writes: flags, messages, run_events.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.clock import now_iso
from stringency.db.store import Store
from stringency.exit_codes import ConfigError
from stringency.ids import new_id
from stringency.operator_id import operator_env
from stringency.project import Project
from stringency.review import current_user

REPORT_KEYS = ("coverage", "methods", "summary", "report")


def delivered_files(store: Store, run_id: str) -> dict[str, dict[str, Any]]:
    """The run's latest delivery as `index.json` lists it: file name to its kind, step and path.
    Empty when the run has no delivery. Reads: deliveries."""
    d = store.one(
        "SELECT path FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC LIMIT 1",
        (run_id,),
    )
    if d is None or not (Path(d["path"]) / "index.json").exists():
        return {}
    ddir = Path(d["path"])
    idx = json.loads((ddir / "index.json").read_text())
    out: dict[str, dict[str, Any]] = {}
    for f in idx.get("files", []):
        name = str(f["file"])
        out[name] = {
            "kind": str(f.get("kind") or ""),
            "step_id": str(f.get("step_id") or "") or None,
            "path": ddir / name,
        }
    for key in REPORT_KEYS:
        entry = idx.get(key)
        if isinstance(entry, dict) and entry.get("file"):
            out[str(entry["file"])] = {"kind": key, "step_id": None, "path": ddir / entry["file"]}
    for a in idx.get("answers") or []:
        if a.get("file"):
            out[str(a["file"])] = {"kind": "answer", "step_id": None, "path": ddir / a["file"]}
    return out


def _resolve_run(store: Store, run_id: str | None) -> str:
    if run_id is None:
        row = store.one("SELECT run_id FROM deliveries ORDER BY ts DESC, rowid DESC LIMIT 1")
        if row is None:
            raise ConfigError("no delivered run to flag; name one with --run")
        return str(row["run_id"])
    if store.one("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)) is None:
        raise ConfigError(f"no run {run_id}")
    return run_id


VIA_GIVEN = frozenset({"app"})  # the values a caller may give; web, relayed and tty are detected


def record_flag(
    project: Project,
    run_id: str | None,
    *,
    reason: str,
    step_id: str | None = None,
    object_name: str | None = None,
    via: str | None = None,
) -> dict[str, Any]:
    """Record a flag on `run_id` (the latest delivered run when None). `object_name` must be a
    file the run's delivery index lists; its hash is taken now, so a later delivery cannot
    change what was flagged. `step_id` must be a pipeline step; when the object names one and
    `step_id` is not given, the object's step is recorded. `via` is `web` from the console,
    `app` from the desktop app (given), else `relayed` under a harness session and `tty`
    otherwise, as reviews are. Writes:
    messages, flags, run_events (`flagged`)."""
    words = (reason or "").strip()
    if not words:
        raise ConfigError("a flag needs the person's words: --reason")
    store = project.store
    rid = _resolve_run(store, run_id)
    files = delivered_files(store, rid)
    obj: dict[str, Any] | None = None
    if object_name is not None:
        obj = files.get(object_name)
        if obj is None:
            listed = ", ".join(sorted(files)) or "nothing delivered"
            raise ConfigError(
                f"{object_name} is not a delivered file of run {rid} (delivered: {listed})"
            )
    if step_id is not None and not project.pipeline.has_step(step_id):
        raise ConfigError(f"no step {step_id} in the pipeline")
    if step_id is None and obj is not None:
        step_id = obj.get("step_id")
    env = operator_env()
    who = current_user()
    reason_ref = hashing.hash_text(words)
    row = {
        "flag_id": new_id(),
        "run_id": rid,
        "step_id": step_id,
        "object_name": object_name,
        "object_hash": hashing.hash_file(obj["path"]) if obj and obj["path"].exists() else None,
        "object_kind": obj["kind"] if obj else None,
        "flagged_by": who,
        "host": socket.gethostname(),
        "via": via or ("relayed" if env.get("session_ref") else "tty"),
        "operator_harness": env.get("harness"),
        "operator_session_ref": env.get("session_ref"),
        "reason_ref": reason_ref,
        "ts": now_iso(),
    }
    with store.transaction():
        store.store_message(reason_ref, words)
        store.insert("flags", row)
        store.run_event(
            rid,
            "flagged",
            {
                "flag_id": row["flag_id"],
                "step_id": step_id,
                "object": object_name,
                "by": who,
                "via": row["via"],
            },
        )
    out = dict(row)
    out["reason"] = words
    return out


def flags_for(store: Store, run_id: str) -> list[dict[str, Any]]:
    """The run's flags, oldest first, each with the person's words under `reason`.
    Reads: flags, messages."""
    out: list[dict[str, Any]] = []
    for r in store.all("SELECT * FROM flags WHERE run_id = ? ORDER BY rowid", (run_id,)):
        row = dict(r)
        row["reason"] = store.message(r["reason_ref"]) if r["reason_ref"] else None
        out.append(row)
    return out
