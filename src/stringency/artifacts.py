"""Artifacts and sidecars (design 9.6). Every file the engine writes under runs/ gets a
sidecar `<name>.stringency.json`; `deliver` refuses files without one."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from stringency import __version__, hashing
from stringency.db.store import Store

SIDECAR_SUFFIX = ".stringency.json"


def sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + SIDECAR_SUFFIX)


def write_sidecar(
    path: Path,
    *,
    run_id: str,
    step_id: str,
    action_id: str | None,
    digest: str,
    kind: str,
    name: str,
) -> Path:
    sc = sidecar_path(path)
    sc.write_text(
        json.dumps(
            {
                "stringency": 1,
                "run_id": run_id,
                "step_id": step_id,
                "action_id": action_id,
                "name": name,
                "kind": kind,
                "blake3": digest,
                "size": hashing.path_size(path),
                "engine_version": __version__,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return sc


def read_sidecar(path: Path) -> dict[str, Any] | None:
    sc = sidecar_path(path)
    if not sc.exists():
        return None
    data = json.loads(sc.read_text())
    return data if isinstance(data, dict) else None


def record_output(
    store: Store,
    *,
    run_id: str,
    step_id: str,
    action_id: str | None,
    name: str,
    path: Path,
    kind: str,
    is_final: bool = False,
) -> tuple[str, str]:
    """Hash `path` (a file, or a directory output as a tree hash), write its sidecar, and record
    it. Writes: artifacts, step_events. Returns (artifact_id, blake3 hex)."""
    digest = hashing.hash_path(path)
    sc = write_sidecar(
        path,
        run_id=run_id,
        step_id=step_id,
        action_id=action_id,
        digest=digest,
        kind=kind,
        name=name,
    )
    aid = store.add_artifact(
        {
            "run_id": run_id,
            "step_id": step_id,
            "action_id": action_id,
            "path": str(path),
            "hash": digest,
            "size": hashing.path_size(path),
            "kind": kind,
            "is_final": is_final,
            "provisional": False,
            "sidecar_path": str(sc),
            "name": name,
        }
    )
    return aid, digest


def place_output(src: Path, dest: Path) -> Path:
    """Copy an operator-produced output into the step directory (the durable record)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != dest.resolve():
        shutil.copyfile(src, dest)
    return dest


def step_outputs(store: Store, run_id: str, step_id: str) -> dict[str, Any]:
    """Reads: artifacts. Produced (not rejected) outputs of a step by name, latest first."""
    rows = store.all(
        "SELECT * FROM artifacts WHERE run_id = ? AND step_id = ? AND status = 'produced' "
        "ORDER BY rowid DESC",
        (run_id, step_id),
    )
    out: dict[str, Any] = {}
    for r in rows:
        if r["name"] not in out:
            out[r["name"]] = r
    return out
