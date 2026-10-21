"""Confirm once (`spec/plans/confirm-once.md`, backlog L67, L6, L5, L68, L69): what one person
already accepted in a sibling project speaks for the same thing here. A project opts into a
study by naming it in `stringency.yml` (`study:`); its siblings are the projects under the same
parent directory (to depth two, as the console discovers them) that name the same study. Every
inheritance is a recorded row: a hold created and resolved `inherited` by a `reviews` row that
names the sibling, its hold, its review and the person who accepted. Reads, read-only: each
sibling's `stringency.yml`, `design.yml`, the declaration files and `prov/run.db`; writes
nothing here (the callers write the rows)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.config import StringencyConfig, load_model
from stringency.db.store import Store

DECLARATIONS = ("design.yml", "objective.yml", "inputs.yml")


def major(tag: str) -> str | None:
    m = re.match(r"v?(\d+)\.", tag)
    return m.group(1) if m else None


def sibling_roots(root: Path, siblings_root: Path | None = None) -> list[Path]:
    """Project roots beside `root`: under `siblings_root` (default: the parent of `root`) to
    depth two, the directories the board skips left out, `root` itself left out."""
    from stringency.console import _candidates

    base = (siblings_root or root.parent).resolve()
    if not base.is_dir():
        return []
    found: list[Path] = []
    for child in _candidates(base):
        if (child / "stringency.yml").exists():
            found.append(child)
            continue
        for grand in _candidates(child):
            if (grand / "stringency.yml").exists():
                found.append(grand)
    me = root.resolve()
    return [f for f in found if f.resolve() != me]


def read_sibling(path: Path) -> dict[str, Any] | None:
    """A sibling's config and declaration hashes, or None when it cannot be read as a project
    (an unreadable neighbour is simply not a sibling)."""
    cfg_path, db_path = path / "stringency.yml", path / "prov" / "run.db"
    if not (cfg_path.exists() and db_path.exists()):
        return None
    try:
        cfg = load_model(StringencyConfig, cfg_path)
    except Exception:  # noqa: BLE001
        return None
    hashes = {d: hashing.hash_file(path / d) for d in DECLARATIONS if (path / d).exists()}
    return {"root": path, "config": cfg, "hashes": hashes, "db": db_path}


def accepted_confirm(db: Path) -> dict[str, Any] | None:
    """The sibling's latest confirm acceptance (hold, review, reviewer, ts), or None."""
    with Store.open(db, create=False) as up:
        row = up.one(
            "SELECT h.hold_id, r.review_id, r.reviewer, r.ts, r.verdict FROM holds h "
            "JOIN reviews r ON r.review_id = h.resolved_by_review "
            "WHERE h.kind = 'confirm' AND h.run_id IS NULL "
            "ORDER BY h.created DESC, h.rowid DESC LIMIT 1"
        )
        if row is None or row["verdict"] not in ("accept", "override"):
            return None
        return {
            "hold_id": row["hold_id"],
            "review_id": row["review_id"],
            "reviewer": row["reviewer"],
            "ts": row["ts"],
        }


def study_siblings(
    root: Path, study: str | None, siblings_root: Path | None = None
) -> list[dict[str, Any]]:
    """The readable siblings that name the same study (none when this project names none)."""
    if not study:
        return []
    out = []
    for p in sibling_roots(root, siblings_root):
        s = read_sibling(p)
        if s is not None and s["config"].study == study:
            out.append(s)
    return out


def flag_acceptance(
    siblings: list[dict[str, Any]],
    *,
    predicate: str,
    step_id: str,
    module_version: str,
    proposed: Any,
    reviewer: str,
) -> dict[str, Any] | None:
    """Accept-once (L6): a sibling's `accept` on a flag hold of the same predicate, step and
    module version whose `evidence.proposed` is identical, recorded by this project's reviewer.
    One module version only (the owner, 2026-10-21). Returns the sibling's project, hold,
    review and ts, or None."""
    want = json.dumps(proposed, sort_keys=True, default=str)
    for s in siblings:
        try:
            with Store.open(s["db"], create=False) as up:
                rows = up.all(
                    "SELECT h.hold_id, h.context_json, r.review_id, r.reviewer, r.ts FROM holds h "
                    "JOIN reviews r ON r.review_id = h.resolved_by_review "
                    "WHERE h.kind = 'flag' AND h.step_id = ? AND h.bound_module_version = ? "
                    "AND r.verdict = 'accept' AND r.reviewer = ? ORDER BY r.ts DESC, r.rowid DESC",
                    (step_id, module_version, reviewer),
                )
        except Exception:  # noqa: BLE001
            continue
        for row in rows:
            ctx = json.loads(row["context_json"] or "{}")
            if str(ctx.get("predicate", "")).split("@")[0] != predicate:
                continue
            ev = ctx.get("evidence") or {}
            if json.dumps(ev.get("proposed"), sort_keys=True, default=str) != want:
                continue
            return {
                "project": str(s["root"]),
                "hold_id": row["hold_id"],
                "review_id": row["review_id"],
                "reviewer": row["reviewer"],
                "ts": row["ts"],
            }
    return None
