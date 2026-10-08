"""The console's readers (`spec/plans/console-and-fleet-plan.md` sections 3.5 to 3.9): project
discovery and the registry that keys projects by their trace id; the lookups that find which
project owns a hold or a run; the inbox grouping (which question a hold asks); the driver block
(who operates a run, its last engine call, the current step against the same step elsewhere, the
stale mark); the per-project timeline. Everything here reads; nothing writes, and nothing here
chooses, ranks or recommends.

Reads: `stringency.yml`, `holds`, `reviews`, `runs`, `run_events`, `step_events`, `steps` over
read-only connections. Writes nothing.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from stringency.board import SKIP_DIRS
from stringency.exit_codes import ConfigError

RESCAN_SECONDS = 30.0


def _candidates(d: Path) -> list[Path]:
    """Subdirectories the board would scan: not `superseded/`, `declarations/` or dot-dirs."""
    return sorted(
        c
        for c in d.iterdir()
        if c.is_dir() and c.name not in SKIP_DIRS and not c.name.startswith(".")
    )


def discover(projects: list[Path], projects_dirs: list[Path] | Path | None) -> list[Path]:
    """Project roots: the ones named, plus every child of each directory to depth two that holds
    a `stringency.yml`, skipping the directories the board skips (`superseded/`, `declarations/`,
    dot-dirs) at both levels. Ordered as given, then by path. A named root that is not a project
    is an error; a directory that does not exist contributes nothing."""
    roots: list[Path] = [p.resolve() for p in projects]
    dirs = [projects_dirs] if isinstance(projects_dirs, Path) else list(projects_dirs or [])
    for projects_dir in dirs:
        base = projects_dir.resolve()
        found: list[Path] = []
        for child in _candidates(base) if base.is_dir() else []:
            if (child / "stringency.yml").exists():
                found.append(child)
                continue
            for grand in _candidates(child):
                if (grand / "stringency.yml").exists():
                    found.append(grand)
        roots += [f for f in found if f not in roots]
    for r in roots:
        if not (r / "stringency.yml").exists():
            raise ConfigError(f"{r} is not a stringency project (no stringency.yml)")
    if not roots:
        raise ConfigError("review --serve needs --project <path> or --projects <dir>")
    return roots


def project_id_of(root: Path) -> str | None:
    """The `project_id` in `stringency.yml`, read leniently; None when the file is unreadable."""
    try:
        data = yaml.safe_load((root / "stringency.yml").read_text())
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(data, dict) and isinstance(data.get("project_id"), str):
        return str(data["project_id"])
    return None


def _ro(root: Path) -> sqlite3.Connection | None:
    path = root / "prov" / "run.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=2000")
    return conn


@dataclass
class Registry:
    """The projects a console serves, rescanned every `rescan_seconds` on demand so a project
    initialised during the day appears without a restart. Keyed by `project_id`; the positional
    index survives for the `/p/<i>/...` routes of engine 0.2.6, which redirect."""

    explicit: list[Path]
    dirs: list[Path]
    rescan_seconds: float = RESCAN_SECONDS
    roots: list[Path] = field(default_factory=list)
    by_id: dict[str, Path] = field(default_factory=dict)
    ids: dict[Path, str] = field(default_factory=dict)
    scanned_at: float = 0.0
    _owner: dict[tuple[str, str], str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def refresh(self, *, force: bool = False) -> None:
        with self._lock:
            if (
                not force
                and self.roots
                and time.monotonic() - self.scanned_at < self.rescan_seconds
            ):
                return
            roots = discover(self.explicit, self.dirs)
            by_id: dict[str, Path] = {}
            ids: dict[Path, str] = {}
            for r in roots:
                pid = project_id_of(r)
                if pid is not None and pid not in by_id:
                    by_id[pid] = r
                    ids[r] = pid
            self.roots, self.by_id, self.ids = roots, by_id, ids
            self.scanned_at = time.monotonic()

    def root_of(self, project_id: str) -> Path:
        self.refresh()
        root = self.by_id.get(project_id)
        if root is None:
            self.refresh(force=True)
            root = self.by_id.get(project_id)
        if root is None:
            raise ConfigError(f"no project {project_id}")
        return root

    def id_of(self, root: Path) -> str | None:
        self.refresh()
        return self.ids.get(root)

    def root_at(self, index: int) -> Path:
        """The 0.2.6 positional route."""
        self.refresh()
        if index < 0 or index >= len(self.roots):
            raise ConfigError(f"no project {index}")
        return self.roots[index]

    def owner_of(self, what: str, ident: str) -> tuple[str, Path]:
        """The project that holds hold or run `ident`: (`project_id`, root). Reads `holds` or
        `runs` of each project over a read-only connection; a hit is remembered, since ids never
        move between projects."""
        if what not in ("hold", "run"):
            raise ConfigError(f"no {what} route")
        table, column = ("holds", "hold_id") if what == "hold" else ("runs", "run_id")
        self.refresh()
        pid = self._owner.get((what, ident))
        if pid is not None and pid in self.by_id:
            return pid, self.by_id[pid]
        for root in self.roots:
            conn = _ro(root)
            if conn is None:
                continue
            try:
                found = conn.execute(
                    f"SELECT 1 FROM {table} WHERE {column} = ?",
                    (ident,),  # noqa: S608 - fixed names
                ).fetchone()
            except sqlite3.DatabaseError:
                continue
            finally:
                conn.close()
            if found is not None:
                owner = self.ids.get(root)
                if owner is None:
                    raise ConfigError(f"{root} has no project_id in stringency.yml")
                self._owner[(what, ident)] = owner
                return owner, root
        raise ConfigError(f"no {what} {ident} in {len(self.roots)} project(s)")


# -- the inbox (plan 3.7) ------------------------------------------------------------------------

ASK_GROUPS: tuple[tuple[str, str], ...] = (
    ("confirm", "Confirm the plan"),
    ("parameters", "Approve the operator's parameters"),
    ("consensus", "Decide on the reviewers' consensus"),
    ("disagreement", "Settle a disagreement"),
    ("uncertain", "Decide an uncertain item"),
    ("invalid", "Accept or reject a dispatch with invalid replicates"),
    ("flag", "Accept a flagged condition"),
)
ASK_HEADINGS = dict(ASK_GROUPS)


def hold_context(h: Any) -> dict[str, Any]:
    try:
        ctx = json.loads(h["context_json"] or "{}")
    except (ValueError, TypeError):
        return {}
    return ctx if isinstance(ctx, dict) else {}


def ask_of(h: Any, ctx: dict[str, Any]) -> str:
    """Which question a hold asks, from its kind and the shape of its evidence; no biology and
    no predicate names beyond the engine's own. The method may word the card (`card_title`), the
    group is the engine's."""
    kind = str(h["kind"])
    if kind == "confirm":
        return "confirm"
    if h["item_id"] is not None:
        return "uncertain" if kind == "self_uncertain" else "disagreement"
    if kind == "run_disagreement":
        return "invalid"
    evidence = ctx.get("evidence")
    ev = evidence if isinstance(evidence, dict) else {}
    if "proposed" in ev or "decision_points" in ev:
        return "parameters"
    if "consensus_label" in ev or "items" in ev:
        return "consensus"
    return "flag"


def method_ask(skill: dict[str, Any] | None, predicate: str, step_id: str | None) -> str | None:
    """The `ask` phrase of the delivery skill's `hold_view` entry for this predicate (and step,
    when the entry names one); None when the method says nothing."""
    if not skill:
        return None
    views = skill.get("hold_view")
    if not isinstance(views, list):
        return None
    pred_id = predicate.split("@")[0]
    for v in views:
        if not isinstance(v, dict) or not v.get("ask"):
            continue
        if str(v.get("predicate", "")).split("@")[0] != pred_id:
            continue
        if v.get("step") not in (None, step_id):
            continue
        return str(v["ask"])
    return None


def _param_names(ev: dict[str, Any]) -> list[str]:
    for key in ("decision_points", "proposed"):
        d = ev.get(key)
        if isinstance(d, dict):
            return [str(k) for k in d]
    return []


def card_title(h: Any, ctx: dict[str, Any], group: str, step_title: str, skill: Any) -> str:
    """The card's title: the method's `ask` phrase when it gives one, else the engine's words
    built from the step title and the hold's evidence."""
    predicate = str(ctx.get("predicate") or "")
    phrase = method_ask(skill, predicate, h["step_id"]) if predicate else None
    if phrase:
        return phrase
    evidence = ctx.get("evidence")
    ev = evidence if isinstance(evidence, dict) else {}
    if group == "confirm":
        return "the plan"
    if group == "parameters":
        names = _param_names(ev)
        return f"{step_title}: {', '.join(names)}" if names else step_title
    if group == "consensus":
        label = ev.get("consensus_label")
        return f"{step_title}: the reviewers agreed on {label}" if label else step_title
    if group in ("disagreement", "uncertain"):
        return f"{step_title}, item {h['item_id']}"
    if group == "invalid":
        return f"{step_title}: a replicate was invalid"
    return f"{step_title}: {predicate.split('@')[0] or h['reason']}"


def group_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cards in the inbox's order: group by ask in `ASK_GROUPS` order, oldest first within."""
    out: list[dict[str, Any]] = []
    for key, heading in ASK_GROUPS:
        members = sorted(
            (c for c in cards if c["group"] == key), key=lambda c: (c["created"], c["hold_id"])
        )
        out.append({"key": key, "heading": heading, "cards": members})
    return out


# -- who is driving (plan 3.9) -------------------------------------------------------------------

STALE_FLOOR_SECONDS = 15 * 60
WAITING_STATUSES = ("running", "dispatching", "awaiting_execution", "proposed", "admissible")


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_between(a: str | None, b: str | None) -> float | None:
    ta, tb = _ts(a), _ts(b)
    if ta is None or tb is None:
        return None
    return (tb - ta).total_seconds()


def duration_text(seconds: float | None) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min" + (f" {s % 60} s" if s % 60 and s < 600 else "")
    if s < 48 * 3600:
        return f"{s // 3600} h {(s % 3600) // 60} min"
    return f"{s // 86400} d"


def references(roots: list[Path]) -> dict[tuple[str, str], float]:
    """Median duration in seconds of each completed step, keyed by (pipeline, step id), over
    every project given, so a running step can be shown against the same step elsewhere.
    Reads `stringency.yml` and `steps` read-only."""
    samples: dict[tuple[str, str], list[float]] = {}
    for root in roots:
        try:
            cfg = yaml.safe_load((root / "stringency.yml").read_text())
        except (OSError, yaml.YAMLError):
            continue
        pipeline = cfg.get("pipeline") if isinstance(cfg, dict) else None
        if not isinstance(pipeline, str):
            continue
        conn = _ro(root)
        if conn is None:
            continue
        try:
            rows = conn.execute(
                "SELECT step_id, started, ended FROM steps WHERE status = 'completed' "
                "AND started IS NOT NULL AND ended IS NOT NULL"
            ).fetchall()
        except sqlite3.DatabaseError:
            continue
        finally:
            conn.close()
        for r in rows:
            d = seconds_between(r["started"], r["ended"])
            if d is not None and d >= 0:
                samples.setdefault((pipeline, str(r["step_id"])), []).append(d)
    return {k: statistics.median(v) for k, v in samples.items()}


def driver(
    conn: sqlite3.Connection,
    run: Any,
    current: dict[str, Any] | None,
    pipeline: str,
    refs: dict[tuple[str, str], float],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The driver block of one project's latest run: who operates it, when the engine was last
    called, how long the current step has been going against the same step elsewhere, and
    whether it looks stale. `current` is the board's current-step entry (`step_id`, `title`,
    `status`) or None. Reads: step_events, run_events, reviews, steps, holds."""
    now = now or datetime.now(UTC)
    run_id = run["run_id"]
    last = conn.execute(
        "SELECT MAX(ts) AS ts FROM (SELECT ts FROM step_events WHERE run_id = ? "
        "UNION ALL SELECT ts FROM run_events WHERE run_id = ? "
        "UNION ALL SELECT ts FROM reviews WHERE run_id = ?)",
        (run_id, run_id, run_id),
    ).fetchone()
    last_call = str(last["ts"]) if last and last["ts"] else None
    since_call = seconds_between(last_call, now.isoformat()) if last_call else None
    out: dict[str, Any] = {
        "harness": run["operator_harness"] or "",
        "session": run["operator_session_ref"] or "",
        "host": run["host"],
        "user": run["user"],
        "last_call": last_call,
        "last_call_age": duration_text(since_call),
        "step": None,
        "status": None,
        "elapsed": "",
        "elsewhere": "",
        "stale": False,
    }
    if current is None:
        return out
    out["step"], out["status"] = current["title"], str(current["status"])
    started = conn.execute(
        "SELECT started FROM steps WHERE run_id = ? AND step_id = ?",
        (run_id, current["step_id"]),
    ).fetchone()
    since: str | None = str(started["started"]) if started and started["started"] else None
    if current["status"] == "held":
        h = conn.execute(
            "SELECT MIN(created) AS c FROM holds WHERE run_id = ? AND step_id = ? "
            "AND resolved_by_review IS NULL AND resolved_via IS NULL",
            (run_id, current["step_id"]),
        ).fetchone()
        since = str(h["c"]) if h and h["c"] else since
    elapsed = seconds_between(since, now.isoformat()) if since else None
    out["elapsed"] = duration_text(elapsed)
    ref = refs.get((pipeline, str(current["step_id"])))
    out["elsewhere"] = duration_text(ref)
    if current["status"] in WAITING_STATUSES and since_call is not None:
        limit = max(STALE_FLOOR_SECONDS, 2 * ref if ref else 0)
        out["stale"] = since_call > limit
    return out


# -- the timeline (plan 3.9) ---------------------------------------------------------------------


def _clock(ts: str) -> str:
    t = _ts(ts)
    return t.strftime("%Y-%m-%d %H:%M") if t else ts


def timeline(conn: sqlite3.Connection, titles: dict[str, str]) -> list[dict[str, Any]]:
    """Every run of the project in order of start, each with its events in words: opened by
    whom, forked from what at which step, held where and how it was answered, blocked, failed,
    abandoned with the reason, completed, delivered. Reads: runs, run_events, holds, reviews."""
    runs = conn.execute("SELECT * FROM runs ORDER BY started, rowid").fetchall()
    out: list[dict[str, Any]] = []
    for run in runs:
        rid = run["run_id"]
        entries: list[tuple[str, str]] = []
        for e in conn.execute(
            "SELECT event, payload_json, ts FROM run_events WHERE run_id = ? ORDER BY seq", (rid,)
        ):
            try:
                payload = json.loads(e["payload_json"] or "{}")
            except ValueError:
                payload = {}
            ev = str(e["event"])
            if ev == "opened":
                who = run["operator_harness"] or "a terminal"
                ref = f" ({run['operator_session_ref']})" if run["operator_session_ref"] else ""
                entries.append((e["ts"], f"opened by {who}{ref} as {run['user']} on {run['host']}"))
            elif ev == "fork":
                at = titles.get(str(payload.get("at")), str(payload.get("at")))
                delta = payload.get("delta") or {}
                words = ", ".join(f"{k}={v}" for k, v in delta.items()) if delta else "no change"
                why = f': "{payload["reason"]}"' if payload.get("reason") else ""
                entries.append((e["ts"], f"forked at '{at}' with {words}{why}"))
            elif ev.startswith("status:"):
                status = ev.split(":", 1)[1]
                if status in ("held", "running"):
                    continue  # the hold lines below say where and how it was answered
                reason = payload.get("reason")
                entries.append((e["ts"], status + (f": {reason}" if reason else "")))
            elif ev == "delivered":
                n = payload.get("files")
                entries.append((e["ts"], f"delivered, {n} files" if n else "delivered"))
        for h in conn.execute(
            "SELECT * FROM holds WHERE run_id = ? ORDER BY created, rowid", (rid,)
        ):
            where = titles.get(str(h["step_id"]), str(h["step_id"]))
            item = f", item {h['item_id']}" if h["item_id"] else ""
            entries.append((h["created"], f"held at '{where}'{item} ({h['kind']})"))
            r = (
                conn.execute(
                    "SELECT * FROM reviews WHERE review_id = ?", (h["resolved_by_review"],)
                ).fetchone()
                if h["resolved_by_review"]
                else None
            )
            if r is not None:
                said = f' "{r["reason"]}"' if r["reason"] else ""
                rep = f" replicate {r['chosen_replicate']}" if r["chosen_replicate"] else ""
                entries.append(
                    (r["ts"], f"{r['verdict']}{rep}{said} by {r['reviewer']} via {r['via']}")
                )
            elif h["resolved_via"]:
                entries.append((h["created"], f"hold {h['resolved_via']}"))
        entries.sort(key=lambda e: e[0])  # stable: same-second events keep their order
        out.append(
            {
                "run_id": rid,
                "label": f"run of {_clock(run['started'])}",
                "status": run["status"],
                "fork": bool(run["parent_run_id"]),
                "events": [{"when": _clock(ts), "text": text} for ts, text in entries],
            }
        )
    return out
