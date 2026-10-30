"""`stringency board <root>`: a progress board over every project under one directory.

Read-only over the traces and independent of any plugin: it reads `stringency.yml` and the trace
database directly, never constructs a `Project`, and resolves nothing. Sentences a person reads:
ids appear only where a command needs them (hold ids), never hashes or paths except the deliver
directory. `--write` keeps `<root>/STATUS.md` current; the verbs that change a project's state call
`refresh_if_present`, so the board follows without the operator remembering (a failure there never
breaks the verb).

An open project's run never completes by itself (design 7.1), so with no step under way and no
hold open the board says it is open and idle since its last call or answer (L132); a project
archived with `stringency archive` (`prov/archived.json`) is skipped.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from stringency.archive import archived
from stringency.clock import now_iso
from stringency.config import StringencyConfig, load_model
from stringency.db.store import Store
from stringency.holds import open_holds
from stringency.pipelines import find_pipeline, load_pipeline
from stringency.runs import latest_run

SKIP_DIRS = {"superseded", "declarations"}
BOARD_FILE = "STATUS.md"


def scan_projects(root: Path) -> list[Path]:
    """Project directories one level under `root`: a `stringency.yml` and a `prov/run.db`, and
    not archived (L132)."""
    out = []
    for d in sorted(Path(root).iterdir()):
        if not d.is_dir() or d.name in SKIP_DIRS or d.name.startswith("."):
            continue
        has_trace = (d / "stringency.yml").exists() and (d / "prov" / "run.db").exists()
        if has_trace and archived(d) is None:
            out.append(d)
    return out


def _confirm(store: Store) -> tuple[str, str | None]:
    """(`accepted` | `rejected` | `pending`, hold id when pending). Reads: holds, reviews."""
    h = store.one(
        "SELECT hold_id, resolved_by_review FROM holds WHERE kind = 'confirm' "
        "ORDER BY created DESC, rowid DESC LIMIT 1"
    )
    if h is None:
        return "pending", None
    if h["resolved_by_review"] is None:
        return "pending", str(h["hold_id"])
    verdict = store.scalar(
        "SELECT verdict FROM reviews WHERE review_id = ?", (h["resolved_by_review"],)
    )
    return ("accepted" if verdict in ("accept", "override") else str(verdict or "pending")), None


def _who(cfg: StringencyConfig, role: str) -> str:
    return cfg.roles.reviewer if role == "reviewer" else cfg.roles.owner


def _titles(root: Path, cfg: StringencyConfig) -> tuple[dict[str, str], str | None]:
    """Step titles from the method's pipeline file, and the plugin the project needs (the
    pipeline's domain, or an open project's `domain`); empty and None when the file cannot be
    read."""
    if cfg.pipeline is None:
        return {}, cfg.domain  # an open project's steps are on demand; their titles are their ids
    try:
        pipeline = load_pipeline(find_pipeline(root / "method", cfg.pipeline))
        return {s: pipeline.title(s) for s in pipeline.order()}, pipeline.domain
    except Exception:  # noqa: BLE001
        return {}, None


# the step statuses of something under way; an open run with none of these and no open hold is
# idle (L132)
UNDER_WAY = (
    "pending",
    "proposed",
    "admissible",
    "running",
    "awaiting_execution",
    "dispatching",
    "produced",
    "held",
)


def _open_activity(store: Store, run_id: str) -> dict[str, Any]:
    """An open run's questions and answers and its last call or answer: the latest step event
    (a `rendered` mark is a reading, not a call), answer or question. Reads: steps, step_events,
    answers, questions."""
    last = store.scalar(
        "SELECT MAX(ts) FROM (SELECT ts FROM step_events WHERE run_id = ? AND event != 'rendered' "
        "UNION ALL SELECT ts FROM answers WHERE run_id = ? "
        "UNION ALL SELECT ts FROM questions WHERE run_id = ?)",
        (run_id, run_id, run_id),
    )
    return {
        "idle_since": str(last) if last else None,
        "questions": int(
            store.scalar("SELECT COUNT(*) FROM questions WHERE run_id = ?", (run_id,)) or 0
        ),
        "answers": int(
            store.scalar("SELECT COUNT(*) FROM answers WHERE run_id = ?", (run_id,)) or 0
        ),
    }


def when_text(ts: str | None) -> str:
    """`2026-10-22T14:03:09Z` as `2026-10-22 14:03 UTC`."""
    if not ts:
        return "an unknown time"
    return f"{ts[:10]} {ts[11:16]} UTC" if len(ts) >= 16 else ts


def project_entry(root: Path) -> dict[str, Any]:
    """One board row. Reads: stringency.yml, holds, reviews, runs, steps, deliveries, and
    deliver/<run>/index.json. Loads no plugin and writes nothing."""
    entry: dict[str, Any] = {"name": root.name, "path": str(root), "archived": archived(root)}
    try:
        cfg = load_model(StringencyConfig, root / "stringency.yml")
        store = Store.open(root / "prov" / "run.db", create=False)
    except Exception as e:  # noqa: BLE001 - a broken project is reported, not fatal
        entry["error"] = f"{type(e).__name__}: {e}"
        return entry
    try:
        entry.update(
            pipeline=cfg.pipeline or "open", method_tag=cfg.method.tag, profile=cfg.profile
        )
        status, hold_id = _confirm(store)
        entry["confirm"] = status
        holds: list[dict[str, Any]] = []
        if status == "pending":
            holds.append({"kind": "confirm", "waits_on": _who(cfg, "owner"), "hold_id": hold_id})
        for eh in store.all(
            "SELECT hold_id FROM holds WHERE kind = 'egress' AND run_id IS NULL "
            "AND resolved_by_review IS NULL ORDER BY created, rowid"
        ):
            holds.append(
                {"kind": "egress", "waits_on": _who(cfg, "owner"), "hold_id": eh["hold_id"]}
            )
        run = latest_run(store)
        entry["run"] = None
        entry["step"] = None
        titles, entry["domain"] = _titles(root, cfg)
        if run is not None:
            entry["run"] = {"run_id": run["run_id"], "status": run["status"]}
            steps = store.all(
                "SELECT step_id, status FROM steps WHERE run_id = ? ORDER BY rowid",
                (run["run_id"],),
            )
            # a skipped conditional step counts as done (L13); an open run's on-demand steps
            # are each their own, so only one under way is current there (L132)
            if cfg.pipeline is None:
                current = next((s for s in steps if s["status"] in UNDER_WAY), None)
            else:
                current = next(
                    (s for s in steps if s["status"] not in ("completed", "skipped")), None
                )
            entry["steps_done"] = sum(1 for s in steps if s["status"] in ("completed", "skipped"))
            entry["steps_total"] = len(steps)
            if current is not None:
                entry["step"] = {
                    "step_id": current["step_id"],
                    "title": titles.get(current["step_id"], current["step_id"]),
                    "status": current["status"],
                }
            run_holds = open_holds(store, run["run_id"])
            for h in run_holds:
                holds.append(
                    {
                        "kind": h["kind"],
                        "waits_on": _who(cfg, h["waits_on_role"]),
                        "hold_id": h["hold_id"],
                        "step_id": h["step_id"],
                    }
                )
            if cfg.pipeline is None and run["status"] not in ("completed", "abandoned"):
                entry["run"].update(_open_activity(store, run["run_id"]))
                if current is None and not run_holds:
                    entry["run"]["state"] = "open"
        entry["holds"] = holds
        entry["delivered"] = _latest_delivery(store)
    finally:
        store.close()
    return entry


def _latest_delivery(store: Store) -> dict[str, Any] | None:
    d = store.one("SELECT run_id, path, ts FROM deliveries ORDER BY ts DESC, rowid DESC LIMIT 1")
    if d is None:
        return None
    files: list[str] = []
    idx = Path(d["path"]) / "index.json"
    if idx.exists():
        try:
            data = json.loads(idx.read_text())
            files = [str(f["file"]) for f in data.get("files", [])]
        except (OSError, ValueError, KeyError, TypeError):
            files = []
    return {"run_id": d["run_id"], "path": d["path"], "when": d["ts"], "files": files}


def sentence(e: dict[str, Any]) -> str:
    """The one-line reading of a project."""
    if "error" in e:
        return f"{e['name']}: could not be read ({e['error']})."
    parts = [f"{e['name']} runs {e['pipeline']} from method {e['method_tag']}."]
    if e["confirm"] == "pending":
        parts.append(f"Its plan waits for {e['holds'][0]['waits_on']} to confirm it.")
    elif e["run"] is None:
        parts.append("The plan is confirmed and no run has started.")
    else:
        st = e["run"]["status"]
        step = e["step"]
        if st == "completed":
            parts.append("The latest run completed.")
        elif e["run"].get("state") == "open":
            parts.append(
                f"It is open, idle since {when_text(e['run'].get('idle_since'))}: "
                f"{e['run'].get('questions', 0)} question(s), {e['run'].get('answers', 0)} "
                "answer(s); `stringency abandon` closes it."
            )
        elif st == "abandoned":
            parts.append("The latest run was abandoned.")
        elif step is None:
            parts.append(f"The latest run is {st}.")
        elif step["status"] == "awaiting_execution":
            parts.append(f"An operator ticket is open for '{step['title']}'.")
        else:
            parts.append(f"Step '{step['title']}' is {step['status'].replace('_', ' ')}.")
        for h in e["holds"]:
            if h["kind"] != "confirm":
                parts.append(f"A {h['kind']} hold waits for {h['waits_on']} (hold {h['hold_id']}).")
    d = e.get("delivered")
    if d:
        parts.append(f"Delivered: {', '.join(d['files']) or 'no files'} in {d['path']}.")
    return " ".join(parts)


def _waiting(e: dict[str, Any]) -> str:
    if "error" in e:
        return "unreadable"
    if e["holds"]:
        h = e["holds"][0]
        return f"{h['kind']} hold, {h['waits_on']}"
    if e["run"] and e["run"]["status"] == "running" and e["step"]:
        return "the operator" if e["step"]["status"] == "awaiting_execution" else "the engine"
    return "nothing"


COLUMNS = (
    "project",
    "pipeline",
    "method",
    "plan",
    "latest run",
    "current step",
    "waiting on",
    "delivered",
)


def row(e: dict[str, Any]) -> dict[str, str]:
    """The board's table cells for one project, keyed by `COLUMNS`; the markdown board and the
    project page (Track 1h) both render these, so they cannot disagree."""
    if "error" in e:
        cells = [e["name"], "", "", "", "", "", "unreadable", ""]
        return dict(zip(COLUMNS, cells, strict=True))
    run = e["run"]["status"] if e["run"] else "none"
    if e["run"] and e["run"].get("state") == "open":
        run = f"open, idle since {when_text(e['run'].get('idle_since'))}"
    step = ""
    if e["step"]:
        step = f"{e['step']['title']} ({e['step']['status'].replace('_', ' ')})"
    elif e["run"] and e["run"]["status"] == "completed":
        step = "all steps completed"
    delivered = ", ".join(e["delivered"]["files"]) if e.get("delivered") else ""
    cells = [
        e["name"],
        e["pipeline"],
        e["method_tag"],
        e["confirm"],
        run,
        step,
        _waiting(e),
        delivered,
    ]
    return dict(zip(COLUMNS, cells, strict=True))


def render(entries: list[dict[str, Any]], root: Path, when: str | None = None) -> str:
    """Markdown: a heading with the time, one summary table, then one sentence per project."""
    when = when or now_iso()
    lines = [
        f"# Status of projects under {root}",
        "",
        f"Written {when} by `stringency board`. Re-read rather than trust: it is rewritten by "
        "every verb that changes a project.",
        "",
        "| project | pipeline | method | plan | latest run | current step | waiting on | delivered |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        lines.append("| " + " | ".join(row(e).values()) + " |")
    lines += ["", "## In words", ""]
    lines += [f"- {sentence(e)}" for e in entries]
    return "\n".join(lines) + "\n"


def board(root: Path) -> tuple[list[dict[str, Any]], str]:
    entries = [project_entry(p) for p in scan_projects(root)]
    return entries, render(entries, root)


def write_board(root: Path) -> Path:
    _, text = board(root)
    target = Path(root) / BOARD_FILE
    target.write_text(text)
    return target


def refresh_if_present(project_root: Path) -> None:
    """Rewrite the project's `README.md` (2026-10-19) and `<project>/../STATUS.md` when one
    exists. Never raises: both are conveniences and must not turn a successful verb into a
    failure."""
    from stringency.readme import write_readme

    with contextlib.suppress(Exception):
        write_readme(Path(project_root))
    try:
        parent = Path(project_root).resolve().parent
        if (parent / BOARD_FILE).exists():
            write_board(parent)
    except Exception:  # noqa: BLE001
        return
