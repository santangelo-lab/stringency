"""`<project>/README.md`: a guide to a project directory for anyone who opens it later, a person
or an AI, without knowing the engine (2026-10-19, the owner's open-mode test drive).

It says what the project is, what it was asked and what it delivered, and what every file and
directory holds. The engine writes it at `init` and rewrites it after every verb that changes the
trace (beside `STATUS.md`, through `board.refresh_if_present`); it is rendered from the trace and
the project's files, never edited by hand.

Reads: stringency.yml, inputs.yml, the module index, runs, steps, step_events, questions,
answers, messages, deliveries. Writes: `<project>/README.md` only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stringency.config import InputsManifest, load_model
from stringency.present import Site

README_FILE = "README.md"
# the first line of an engine-written README: one without it was written by someone else and is
# never overwritten
MARKER = "<!-- written by stringency; rewritten after every command -->"

HEAD_NOTE = (
    "The engine writes this file and rewrites it after every command, so edits to it are lost. "
    "The record itself is `prov/run.db`; everything here is read from it."
)

OPEN_LAYOUT = [
    ("`README.md`", "this guide"),
    ("`echo.md`", "what the project is bound to, accepted once before the first question"),
    (
        "`inputs.yml`",
        "the files it reads: the delivered files, and the upstream pipeline's own inputs "
        "(`upstream_*`), all read-only and pinned by hash",
    ),
    ("`design.yml`, `objective.yml`", "copied from the upstream project"),
    ("`stringency.yml`", "the method and its tag, the executor, the owner and reviewer"),
    ("`method/`", "the method repository checked out at its tag: the tools' code and controls"),
    (
        "`runs/<run>/<NN>_<tool or exec>/`",
        "one directory per tool run or script, numbered in the order they ran: `job.json` (what "
        "it was given), its outputs, its logs, and for code written in the session `script.*`",
    ),
    (
        "`controls/<tool>/<control>/`",
        "each tool's control runs on known data; a passing one is what lets the tool's answers be "
        "labelled trusted",
    ),
    (
        "`deliver/answers-<NN>/`",
        "each delivery of the answers the person chose: one `q<NN>-*.md` per answer, the files it "
        "cites, `answers-summary.md` (start here), `answers-coverage.md`, `answers-methods.md`, "
        "and `index.json` (every file with its hash and provenance)",
    ),
    (
        "`prov/run.db`",
        "the trace (SQLite): every question, step, check, hold and answer",
    ),
    ("`prov/justifications/`", "the written reasons recorded with reviews"),
    ("`.stringency/`", "engine scratch; safe to ignore"),
]

PIPELINE_LAYOUT = [
    ("`README.md`", "this guide"),
    ("`brief.md`", "the description of the experiment the declarations were drafted from"),
    ("`echo.md`", "the engine's reading of the declarations, accepted before the first run"),
    ("`inputs.yml`", "the input files, each pinned by hash"),
    ("`design.yml`", "the samples, units, factors and replicate"),
    ("`objective.yml`", "the question, the contrasts, the deliverables, declared parameters"),
    ("`stringency.yml`", "the method and its tag, the pipeline, the executor, the owner"),
    ("`method/`", "the method repository checked out at its tag: modules, pipeline, policy"),
    (
        "`runs/<run>/<step>/`",
        "one directory per step of a run: `job.json` (what it was given), its outputs and logs",
    ),
    ("`controls/<module>/<control>/`", "control runs of the method's modules on known data"),
    (
        "`deliver/<run>/`",
        "a run's delivery: the final files, `summary.md` (start here), `coverage.md`, "
        "`methods.md`, and `index.json` (every file with its hash and provenance)",
    ),
    ("`prov/run.db`", "the trace (SQLite): every step, check, hold, review and delivery"),
    ("`prov/justifications/`", "the written reasons recorded with reviews"),
    ("`.stringency/`", "engine scratch; safe to ignore"),
]


def _cell(text: Any) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _rel(root: Path, path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(root))
    except ValueError:
        return str(p)


def _layout(root: Path, rows: list[tuple[str, str]]) -> list[str]:
    """The table of what is where, leaving out a named file the project does not have."""
    out = ["| path | what it holds |", "|---|---|"]
    for p, w in rows:
        first = p.split(",")[0].strip("` ").split("<")[0]
        if "<" in p or first == README_FILE or (root / first).exists():
            out.append(f"| {p} | {w} |")
    return out


def _deliveries(site: Site) -> list[Any]:
    return list(site.store.all("SELECT * FROM deliveries ORDER BY ts, rowid"))


def _upstream(site: Site) -> tuple[str | None, str | None]:
    """(upstream project, run) of an open project's delivered inputs."""
    inputs = load_model(InputsManifest, site.root / "inputs.yml")
    for i in inputs.items:
        if i.derived_from is not None:
            return i.derived_from.project, i.derived_from.run_id
    return None, None


def _question_rows(site: Site) -> list[dict[str, Any]]:
    """Per question, in the order asked: its words, origin, the steps run for it, the latest
    admissible answer's label, and the delivery file holding that answer, if any."""
    store, root = site.store, site.root
    steps_for: dict[str, list[dict[str, Any]]] = {}
    for e in store.all(
        "SELECT e.run_id, e.step_id, e.payload_json, s.module FROM step_events e "
        "LEFT JOIN steps s ON s.run_id=e.run_id AND s.step_id=e.step_id "
        "WHERE e.event='created' ORDER BY e.rowid"
    ):
        od = (json.loads(e["payload_json"] or "{}") or {}).get("on_demand") or {}
        qid = od.get("question_id")
        if not qid:
            continue
        steps_for.setdefault(str(qid), []).append(
            {
                "kind": od.get("kind"),
                "module": e["module"],
                "dir": f"runs/{e['run_id']}/{e['step_id']}/",
            }
        )
    delivered: dict[str, str] = {}
    for d in _deliveries(site):
        idx = Path(d["path"]) / "index.json"
        if not idx.exists():
            continue
        try:
            for a in json.loads(idx.read_text()).get("answers") or []:
                delivered[str(a.get("question_id"))] = _rel(root, Path(d["path"]) / a["file"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    rows: list[dict[str, Any]] = []
    for q in store.all("SELECT * FROM questions ORDER BY ts, seq"):
        qid = str(q["question_id"])
        ans = store.one(
            "SELECT label FROM answers WHERE question_id=? AND status='admissible' "
            "ORDER BY rowid DESC LIMIT 1",
            (qid,),
        )
        steps = steps_for.get(qid, [])
        routes = [
            f"tool {s['module']}" if s["kind"] == "tool" else "code written in the session"
            for s in steps
        ]
        rows.append(
            {
                "seq": q["seq"],
                "text": store.message(q["text_ref"]) or "",
                "origin": "a suggested path" if q["origin"] == "suggested" else "the person",
                "route": ", ".join(dict.fromkeys(routes)) or "no step",
                "label": ans["label"] if ans is not None else "not answered",
                "dirs": ", ".join(f"`{s['dir']}`" for s in steps) or "none",
                "delivered": f"`{delivered[qid]}`" if qid in delivered else "not delivered",
            }
        )
    return rows


def render_open(site: Site) -> str:
    cfg, root = site.config, site.root
    up_project, up_run = _upstream(site)
    lines = [
        MARKER,
        f"# {root.name}",
        "",
        "A stringency open-mode project: questions asked of the results that "
        + (f"`{up_project}` delivered (run {up_run})" if up_project else "a delivery holds")
        + ". Each answer was produced by a tool the method ships or by code written in the "
        "session, run and recorded by the engine, and labelled trusted or untested from what "
        "ran. Nothing asked here changes the delivered results.",
        "",
        f"Method `{cfg.method.repo}` at `{cfg.method.tag}`; engine {cfg.stringency_version}; "
        f"owner {cfg.roles.owner}.",
        "",
        HEAD_NOTE,
        "",
        "## Questions",
        "",
    ]
    rows = _question_rows(site)
    if rows:
        lines += [
            "| # | question | asked by | answered by | label | steps | delivered as |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {r['seq']} | {_cell(r['text'])} | {r['origin']} | {r['route']} | "
                f"{r['label']} | {r['dirs']} | {r['delivered']} |"
            )
    else:
        lines.append("No question has been asked yet.")
    lines += ["", "## Deliveries", ""]
    ds = _deliveries(site)
    if not ds:
        lines.append("No answer has been delivered yet.")
    for d in ds:
        idx = Path(d["path"]) / "index.json"
        seqs: list[str] = []
        start = "answers-summary.md"
        if idx.exists():
            try:
                index = json.loads(idx.read_text())
                seqs = [str(a["seq"]) for a in index.get("answers") or [] if a.get("seq")]
                start = str((index.get("summary") or {}).get("file") or start)
            except (json.JSONDecodeError, AttributeError):
                seqs = []
        which = f"questions {', '.join(seqs)}" if seqs else "answers"
        lines.append(
            f"- `{_rel(root, d['path'])}/` ({str(d['ts'])[:10]}): {which}. Start with `{start}`."
        )
    lines += ["", "## What is where", "", *_layout(root, OPEN_LAYOUT), ""]
    return "\n".join(lines)


def render_pipeline(site: Site) -> str:
    cfg, root, store = site.config, site.root, site.store
    p = site.pipeline
    lines = [
        MARKER,
        f"# {root.name}",
        "",
        f"A stringency pipeline project: pipeline `{p.name}` {p.version} of method "
        f"`{cfg.method.repo}` at `{cfg.method.tag}`, run step by step by the engine, every step "
        "checked before and after it ran and recorded.",
        "",
        f"Engine {cfg.stringency_version}; profile {cfg.profile}; owner {cfg.roles.owner}.",
        "",
        HEAD_NOTE,
        "",
        "## Steps of the pipeline",
        "",
        "| step | module | what it does |",
        "|---|---|---|",
    ]
    for s in p.steps:
        lines.append(f"| `{s.id}` | {s.module} | {_cell(s.title or '')} |")
    lines += ["", "## Runs", ""]
    runs = list(
        store.all("SELECT run_id, status, started FROM runs WHERE kind='run' ORDER BY started")
    )
    if not runs:
        lines.append("No run has started yet.")
    else:
        delivered = {str(d["run_id"]): d for d in _deliveries(site)}
        lines += ["| run | started | status | delivered to |", "|---|---|---|---|"]
        for r in runs:
            d = delivered.get(str(r["run_id"]))
            where = f"`{_rel(root, d['path'])}/`" if d is not None else "not delivered"
            lines.append(
                f"| `{r['run_id']}` | {str(r['started'])[:16]} | {r['status']} | {where} |"
            )
    lines += ["", "## What is where", "", *_layout(root, PIPELINE_LAYOUT), ""]
    return "\n".join(lines)


def write_readme(project_root: Path) -> Path | None:
    """Render and write `<project>/README.md`, unless a README the engine did not write is
    there (returns None then). Reads the trace through `Site`."""
    out = Path(project_root).resolve() / README_FILE
    if out.exists() and not out.read_text().startswith(MARKER):
        return None
    site = Site.load(Path(project_root))
    try:
        text = render_open(site) if site.open_ended else render_pipeline(site)
    finally:
        site.store.close()
    out.write_text(text)
    return out
