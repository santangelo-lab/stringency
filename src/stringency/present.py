"""`stringency present`: what a person should see after a delivery or at a hold.

Driven by the METHOD's delivery skill file `method/skills/<pipeline>.yml` (design 14.3): the
method states which delivered tables to show, in what columns and formats, which file to send,
and what to render when a flag hold opens. The engine adds nothing of its own except the default
when no skill file exists: the run's progress sentence and the list of deliverables. The reader
is defensive: a missing or malformed skill degrades to the default and says so.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

from stringency.config import StringencyConfig, load_model
from stringency.db.store import Store
from stringency.exit_codes import ConfigError
from stringency.pipelines import Pipeline, find_pipeline, load_pipeline
from stringency.plain import progress_sentence

KINDS = ("table", "json_table", "jsonl", "text", "file")


@dataclass
class Site:
    """What `present` needs of a project: its config, trace and pipeline. Loads no plugin, so it
    works from any engine install (the project's plugin need not be installed to read results)."""

    root: Path
    config: StringencyConfig
    store: Store
    pipeline: Pipeline

    @property
    def method_root(self) -> Path:
        return self.root / "method"

    @classmethod
    def load(cls, root: Path) -> Site:
        root = Path(root).resolve()
        if not (root / "stringency.yml").exists():
            raise ConfigError(f"{root} is not a stringency project (no stringency.yml)")
        cfg = load_model(StringencyConfig, root / "stringency.yml")
        store = Store.open(root / "prov" / "run.db", create=False)
        pipeline = load_pipeline(find_pipeline(root / "method", cfg.pipeline))
        return cls(root, cfg, store, pipeline)

    @classmethod
    def find(cls, start: Path | None = None) -> Site:
        cur = (start or Path.cwd()).resolve()
        for cand in (cur, *cur.parents):
            if (cand / "stringency.yml").exists():
                return cls.load(cand)
        raise ConfigError("no stringency project found here or in a parent directory")

    def step_statuses(self, run_id: str) -> dict[str, str]:
        rows = self.store.all("SELECT step_id, status FROM steps WHERE run_id = ?", (run_id,))
        return {r["step_id"]: r["status"] for r in rows}


def load_skill(project: Site, skills_dir: Path | None = None) -> tuple[dict[str, Any] | None, str]:
    """(skill dict, note). None with a note when the file is absent or malformed."""
    d = Path(skills_dir) if skills_dir else project.method_root / "skills"
    f = d / f"{project.config.pipeline}.yml"
    if not f.exists():
        return None, f"no delivery skill at {f}; showing the engine default"
    try:
        data = yaml.safe_load(f.read_text())
    except yaml.YAMLError as e:
        return None, f"delivery skill {f} is not valid YAML ({e}); showing the engine default"
    if not isinstance(data, dict) or data.get("skill") != 1:
        return None, f"delivery skill {f} is not a `skill: 1` document; showing the engine default"
    if data.get("pipeline") not in (None, project.config.pipeline):
        return None, (
            f"delivery skill {f} is for pipeline {data.get('pipeline')}, not "
            f"{project.config.pipeline}; showing the engine default"
        )
    return data, f"delivery skill {f}"


# -- rendering ----------------------------------------------------------------------------------


def _fmt(value: Any, spec: str | None) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{k}={_fmt(v, None)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(_fmt(v, None) for v in value)
    if value is None or value == "":
        return ""
    if spec is None:
        return str(value)
    try:
        if spec == "percent":
            return f"{float(value) * 100:.1f}%"
        if spec == "int":
            return f"{int(round(float(value))):,}"
        if spec.endswith("f") and spec[:-1].isdigit():
            return f"{float(value):.{int(spec[:-1])}f}"
    except (TypeError, ValueError):
        return str(value)
    return str(value)


def _rows_from_table(path: Path) -> list[dict[str, Any]]:
    text = path.read_text()
    delim = (
        "\t"
        if path.suffix.lower() in (".tsv", ".tab")
        or ("\t" in text.splitlines()[0] if text else False)
        else ","
    )
    return [dict(r) for r in csv.DictReader(text.splitlines(), delimiter=delim)]


def _rows_from_json(path: Path, key: str | None) -> list[dict[str, Any]]:
    node: Any = json.loads(path.read_text())
    for part in (key or "").split("."):
        if part:
            node = node.get(part) if isinstance(node, dict) else None
    if isinstance(node, dict):
        return [node]
    if isinstance(node, list):
        return [r for r in node if isinstance(r, dict)]
    raise ConfigError(f"{path}: `{key}` is not a list of rows")


def _rows_from_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _table(
    rows: list[dict[str, Any]], columns: list[str] | None, formats: dict[str, str]
) -> dict[str, Any]:
    cols = list(columns) if columns else (list(rows[0].keys()) if rows else [])
    cells = [[_fmt(r.get(c), formats.get(c)) for c in cols] for r in rows]
    return {"columns": cols, "rows": cells}


def _esc(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def markdown_table(columns: list[str], rows: list[list[str]]) -> str:
    if not columns:
        return "(empty table)"
    lines = ["| " + " | ".join(_esc(c) for c in columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_esc(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _resolve(project: Site, run_id: str, source: str, deliver_dir: Path | None) -> Path | None:
    """A skill source is relative to deliver/<run>/ (preferred) or runs/<run>/ (fallback)."""
    for base in (deliver_dir, project.root / "runs" / run_id):
        if base is not None and (base / source).exists():
            return base / source
    return None


def render_items(
    project: Site, run_id: str, items: list[dict[str, Any]], deliver_dir: Path | None
) -> tuple[list[dict[str, Any]], list[str]]:
    sections: list[dict[str, Any]] = []
    files: list[str] = []
    for item in items:
        title = str(item.get("title") or item.get("source") or "")
        kind = str(item.get("kind") or "table")
        src = str(item.get("source") or "")
        path = _resolve(project, run_id, src, deliver_dir)
        if kind not in KINDS:
            sections.append({"title": title, "kind": kind, "error": f"unknown kind `{kind}`"})
            continue
        if path is None:
            sections.append(
                {"title": title, "kind": kind, "error": f"{src} not found for this run"}
            )
            continue
        if kind == "file":
            files.append(str(path))
            sections.append({"title": title, "kind": "file", "path": str(path)})
            continue
        if kind == "text":
            sections.append({"title": title, "kind": "text", "text": path.read_text()})
            continue
        try:
            if kind == "table":
                rows = _rows_from_table(path)
            elif kind == "jsonl":
                rows = _rows_from_jsonl(path)
            else:
                rows = _rows_from_json(path, item.get("path"))
        except (OSError, ValueError, ConfigError) as e:
            sections.append({"title": title, "kind": kind, "error": f"{src}: {e}"})
            continue
        raw_cols = item.get("columns")
        cols: list[str] | None = [str(c) for c in raw_cols] if isinstance(raw_cols, list) else None
        raw_fmt = item.get("format")
        fmts: dict[str, str] = (
            {str(k): str(v) for k, v in raw_fmt.items()} if isinstance(raw_fmt, dict) else {}
        )
        sections.append({"title": title, "kind": kind, **_table(rows, cols, fmts)})
    return sections, files


def _deliver_dir(project: Site, run_id: str) -> Path | None:
    d = project.store.one(
        "SELECT path FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC LIMIT 1",
        (run_id,),
    )
    return Path(d["path"]) if d is not None else None


def present_run(
    project: Site, run_id: str | None, skills_dir: Path | None = None
) -> dict[str, Any]:
    """The after-delivery view of a run (the latest completed run by default)."""
    if run_id is None:
        row = project.store.one(
            "SELECT run_id FROM runs WHERE status = 'completed' ORDER BY ended DESC, rowid DESC LIMIT 1"
        )
        if row is None:
            raise ConfigError("no completed run to present")
        run_id = row["run_id"]
    if project.store.one("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)) is None:
        raise ConfigError(f"no run {run_id}")
    deliver_dir = _deliver_dir(project, run_id)
    skill, note = load_skill(project, skills_dir)
    payload: dict[str, Any] = {
        "schema": "stringency.present/1",
        "kind": "run",
        "run_id": run_id,
        "pipeline": project.config.pipeline,
        "progress": progress_sentence(project.pipeline, project.step_statuses(run_id)),
        "skill": note,
        "sections": [],
        "files": [],
        "never_show": [],
        "deliverables": [],
    }
    if deliver_dir is not None and (deliver_dir / "index.json").exists():
        idx = json.loads((deliver_dir / "index.json").read_text())
        payload["deliverables"] = [str(deliver_dir / f["file"]) for f in idx.get("files", [])]
    if skill is not None:
        raw_items = skill.get("after_delivery")
        items: list[dict[str, Any]] = list(raw_items) if isinstance(raw_items, list) else []
        payload["sections"], payload["files"] = render_items(project, run_id, items, deliver_dir)
        ns = skill.get("never_show")
        payload["never_show"] = [str(x) for x in ns] if isinstance(ns, list) else []
    return payload


def present_hold(
    project: Site, hold_id: str | None, skills_dir: Path | None = None
) -> dict[str, Any]:
    """The hold view: kind, reason, the review commands, and the skill's tables for the predicate
    that opened it."""
    if hold_id is None:
        h = project.store.one(
            "SELECT * FROM holds WHERE resolved_by_review IS NULL AND resolved_via IS NULL ORDER BY created DESC, rowid DESC LIMIT 1"
        )
        if h is None:
            raise ConfigError("no open hold to present")
    else:
        h = project.store.one("SELECT * FROM holds WHERE hold_id = ?", (hold_id,))
        if h is None:
            raise ConfigError(f"no hold {hold_id}")
    ctx = json.loads(h["context_json"]) if h["context_json"] else {}
    predicate = str(ctx.get("predicate") or "")
    pred_id = predicate.split("@")[0]
    who = (
        project.config.roles.reviewer
        if h["waits_on_role"] == "reviewer"
        else project.config.roles.owner
    )
    skill, note = load_skill(project, skills_dir)
    payload: dict[str, Any] = {
        "schema": "stringency.present/1",
        "kind": "hold",
        "hold_id": h["hold_id"],
        "hold_kind": h["kind"],
        "reason": h["reason"],
        "waits_on": who,
        "step_id": h["step_id"],
        "run_id": h["run_id"],
        "predicate": predicate or None,
        "evidence": ctx.get("evidence"),
        "review": {
            "accept": f'stringency review --verdict accept --hold {h["hold_id"]} --reason "<why>"',
            "reject": f'stringency review --verdict reject --hold {h["hold_id"]} --reason "<why>"',
        },
        "skill": note,
        "sections": [],
        "files": [],
        "never_show": [],
    }
    if h["kind"] == "confirm":
        echo = ctx.get("echo_path")
        if echo and Path(echo).exists():
            payload["sections"].append(
                {"title": "Echo-back", "kind": "text", "text": Path(echo).read_text()}
            )
    if skill is not None and h["run_id"]:
        raw_views = skill.get("hold_view")
        views: list[Any] = list(raw_views) if isinstance(raw_views, list) else []
        matching: list[dict[str, Any]] = [
            v
            for v in views
            if isinstance(v, dict) and str(v.get("predicate", "")).split("@")[0] == pred_id
        ]
        payload["sections"] += render_items(project, h["run_id"], matching, None)[0]
        ns = skill.get("never_show")
        payload["never_show"] = [str(x) for x in ns] if isinstance(ns, list) else []
    return payload


def present_rows(
    project: Site, run_id: str | None, skills_dir: Path | None = None
) -> list[dict[str, Any]]:
    """The sections of `present --run` before any rendering: what the markdown and the HTML
    renderers both consume (Track 1h), so the terminal and the page cannot disagree."""
    return list(present_run(project, run_id, skills_dir)["sections"])


_HTML_ENV = Environment(undefined=StrictUndefined, autoescape=True)

SECTIONS_HTML = _HTML_ENV.from_string(
    """{% for s in sections %}
<h2>{{ s.title }}</h2>
{% if s.get("error") %}<p class="note">(not shown: {{ s.error }})</p>
{% elif s.kind == "file" %}<p>file to send: <code>{{ s.path }}</code></p>
{% elif s.kind == "text" %}<pre>{{ s.text.rstrip() }}</pre>
{% elif not s.get("columns") %}<p class="note">(empty table)</p>
{% else %}<table>
<tr>{% for c in s.columns %}<th>{{ c }}</th>{% endfor %}</tr>
{% for r in s.rows %}<tr>{% for c in r %}<td>{{ c }}</td>{% endfor %}</tr>
{% endfor %}</table>
{% endif %}{% endfor %}
{% if files %}<h2>Files to send</h2><ul>{% for f in files %}<li><code>{{ f }}</code></li>{% endfor %}</ul>{% endif %}
{% if never_show %}<p class="note">Not shown, by the method's rule: {{ never_show | join(", ") }}.</p>{% endif %}
<p class="note">({{ skill }})</p>
"""
)


def render_html(payload: dict[str, Any]) -> str:
    """The same sections as `render_markdown`, as an HTML fragment (escaped; no script). The
    page that embeds it adds the heading, the links and the form."""
    return SECTIONS_HTML.render(
        sections=payload["sections"],
        files=payload["files"],
        never_show=payload["never_show"],
        skill=payload["skill"],
    )


def render_markdown(payload: dict[str, Any]) -> str:
    out: list[str] = []
    if payload["kind"] == "run":
        out.append(f"## {payload['pipeline']}: {payload['progress']}")
    else:
        out.append(
            f"## Hold {payload['hold_id']} ({payload['hold_kind']}) waits for {payload['waits_on']}"
        )
        out.append("")
        out.append(f"The engine recorded: {payload['reason']}")
        if payload.get("evidence"):
            out.append("")
            out.append(f"Evidence: {_fmt(payload['evidence'], None)}")
        out.append("")
        out.append("To resolve it, in the project directory, with your reason in your own words:")
        out.append("")
        out.append(f"    {payload['review']['accept']}")
        out.append(f"    {payload['review']['reject']}")
    for s in payload["sections"]:
        out.append("")
        out.append(f"### {s['title']}")
        out.append("")
        if "error" in s:
            out.append(f"(not shown: {s['error']})")
        elif s["kind"] == "file":
            out.append(f"file to send: {s['path']}")
        elif s["kind"] == "text":
            out.append(s["text"].rstrip())
        else:
            out.append(markdown_table(s["columns"], s["rows"]))
    if payload["kind"] == "run" and not payload["sections"]:
        out.append("")
        out.append("Deliverables:")
        out += [f"- {p}" for p in payload["deliverables"]] or ["- none"]
    if payload["files"]:
        out.append("")
        out.append("Files to send:")
        out += [f"- {p}" for p in payload["files"]]
    if payload["never_show"]:
        out.append("")
        out.append("Not shown, by the method's rule: " + ", ".join(payload["never_show"]) + ".")
    out.append("")
    out.append(f"({payload['skill']})")
    return "\n".join(out) + "\n"
