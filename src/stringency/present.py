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
from collections.abc import Callable
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

KINDS = ("table", "json_table", "jsonl", "text", "file", "figure", "figures", "chart")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".pdf")
FIGURES_MANIFEST = "figures.csv"  # `file,what` (or `step,file,what`): the method's captions


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


def inputs_of(project: Site) -> dict[str, Path]:
    """The bound inputs by name, from `inputs.yml` at the project root."""
    try:
        data = yaml.safe_load((project.root / "inputs.yml").read_text())
    except (OSError, yaml.YAMLError):
        return {}
    items = data.get("items") if isinstance(data, dict) else None
    return {
        str(it["name"]): Path(str(it["path"]))
        for it in items or []
        if isinstance(it, dict) and it.get("name") and it.get("path")
    }


def input_path(project: Site, name: str) -> Path | None:
    """The bound path of a project input."""
    return inputs_of(project).get(name)


def step_dir(project: Site, run_id: str, step_id: str) -> Path | None:
    """Where a step's outputs are for this run: `runs/<run>/<step>/` when it ran here, else the
    directory the `artifacts` table records for the step (a fork inherits the parent run's
    outputs, and the child's run directory has no copy). Reads: artifacts."""
    here = project.root / "runs" / run_id / step_id
    if here.is_dir():
        return here
    row = project.store.one(
        "SELECT path FROM artifacts WHERE run_id = ? AND step_id = ? AND status = 'produced' "
        "ORDER BY rowid LIMIT 1",
        (run_id, step_id),
    )
    return Path(str(row["path"])).parent if row is not None else None


def _resolve(project: Site, run_id: str, source: str, deliver_dir: Path | None) -> Path | None:
    """A skill source is relative to deliver/<run>/ (preferred) or runs/<run>/ (fallback); a
    source `<step>/<rest>` also resolves through the step's recorded output directory, so a
    forked run finds the outputs it inherited; `$inputs.<name>/<rest>` resolves through
    `inputs.yml`. A `<name>.dir` output directory may be written without its suffix."""
    if source.startswith("$inputs."):
        name, _, rest = source[len("$inputs.") :].partition("/")
        base = input_path(project, name)
        if base is None:
            return None
        target = base / rest if rest else base
        return target if target.exists() else None
    for base in (deliver_dir, project.root / "runs" / run_id):
        if base is None:
            continue
        for cand in _dir_variants(base / source):
            if cand.exists():
                return cand
    step, _, rest = source.partition("/")
    base = step_dir(project, run_id, step) if step and rest else None
    if base is not None:
        for cand in _dir_variants(base / rest):
            if cand.exists():
                return cand
    return None


def _dir_variants(path: Path) -> list[Path]:
    """`<step>/<out>/<file>` written by the method as `<step>/<out>.dir/<file>`: try both."""
    out = [path]
    parts = path.parts
    for i, part in enumerate(parts):
        if i > 0 and not part.endswith(".dir") and "." not in part:
            cand = Path(*parts[:i], part + ".dir", *parts[i + 1 :])
            if cand not in out:
                out.append(cand)
    return out


def _fill(source: str, hold: dict[str, Any] | None) -> str:
    """`{item}` and `{step}` in a source, from the hold the view is for."""
    if not hold:
        return source
    return source.replace("{item}", str(hold.get("item_id") or "")).replace(
        "{step}", str(hold.get("step_id") or "")
    )


def render_items(
    project: Site,
    run_id: str,
    items: list[dict[str, Any]],
    deliver_dir: Path | None,
    hold: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """The skill's items as sections. `hold` (item id, step id, the hold's evidence) fills
    `{item}` placeholders and gives a `chart` its marked parameter value."""
    sections: list[dict[str, Any]] = []
    files: list[str] = []
    for item in items:
        title = str(item.get("title") or item.get("source") or "")
        kind = str(item.get("kind") or "table")
        src = _fill(str(item.get("source") or ""), hold)
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
        if kind == "figure":
            beside_src = _fill(str(item.get("beside") or ""), hold)
            beside = _resolve(project, run_id, beside_src, deliver_dir) if beside_src else None
            sections.append(
                {
                    "title": title,
                    "kind": "figure",
                    "path": str(path),
                    "caption": _caption(path),
                    "beside": str(beside) if beside else None,
                    "beside_caption": _caption(beside) if beside else None,
                    "beside_missing": beside_src if beside_src and beside is None else None,
                }
            )
            continue
        if kind == "figures":
            select = item.get("select")
            wanted = [str(x) for x in select] if isinstance(select, list) else None
            sections.append(
                {
                    "title": title,
                    "kind": "figures",
                    "dir": str(path),
                    "images": _images(path, wanted),
                }
            )
            continue
        try:
            if kind == "table":
                rows = _rows_from_table(path)
            elif kind == "jsonl":
                rows = _rows_from_jsonl(path)
            elif kind == "chart":
                rows = _rows_from_table(path)
            else:
                rows = _rows_from_json(path, item.get("path"))
        except (OSError, ValueError, ConfigError) as e:
            sections.append({"title": title, "kind": kind, "error": f"{src}: {e}"})
            continue
        if kind == "chart":
            try:
                sections.append({"title": title, **chart_section(rows, item, hold)})
            except ConfigError as e:
                sections.append({"title": title, "kind": "chart", "error": f"{src}: {e}"})
            continue
        raw_cols = item.get("columns")
        cols: list[str] | None = [str(c) for c in raw_cols] if isinstance(raw_cols, list) else None
        raw_fmt = item.get("format")
        fmts: dict[str, str] = (
            {str(k): str(v) for k, v in raw_fmt.items()} if isinstance(raw_fmt, dict) else {}
        )
        sections.append({"title": title, "kind": kind, **_table(rows, cols, fmts)})
    return sections, files


def _captions(directory: Path) -> dict[str, str]:
    """The method's captions from `figures.csv` beside the images (`file,what`)."""
    f = directory / FIGURES_MANIFEST
    if not f.is_file():
        return {}
    try:
        return {
            str(r.get("file") or ""): str(r.get("what") or "")
            for r in csv.DictReader(f.read_text().splitlines())
        }
    except (OSError, csv.Error):
        return {}


def _caption(path: Path | None) -> str:
    if path is None:
        return ""
    return _captions(path.parent).get(path.name, "")


def _images(directory: Path, select: list[str] | None) -> list[dict[str, str]]:
    """The images of a figures directory, in the manifest's order (or sorted), each with its
    caption; `select` names a subset in its own order."""
    if not directory.is_dir():
        return []
    captions = _captions(directory)
    names = [n for n in captions if (directory / n).is_file()] or sorted(
        p.name for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES
    )
    for p in sorted(directory.iterdir()):
        if p.suffix.lower() in IMAGE_SUFFIXES and p.name not in names:
            names.append(p.name)
    if select is not None:
        names = [n for n in select if n in names]
    return [
        {"file": n, "path": str(directory / n), "what": captions.get(n, "")}
        for n in names
        if (directory / n).suffix.lower() in IMAGE_SUFFIXES
    ]


def _number(v: Any) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _true(v: Any) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "t")


def _marked_value(hold: dict[str, Any] | None, param: str) -> Any:
    """The value of a parameter in the hold's evidence: `decision_points.<p>.value` or
    `proposed.<p>.proposed`."""
    ev = (hold or {}).get("evidence")
    if not isinstance(ev, dict):
        return None
    for key, field in (("decision_points", "value"), ("proposed", "proposed")):
        d = ev.get(key)
        if isinstance(d, dict) and isinstance(d.get(param), dict):
            return d[param].get(field)
    return None


def chart_section(
    rows: list[dict[str, Any]], item: dict[str, Any], hold: dict[str, Any] | None
) -> dict[str, Any]:
    """A line of column `y` against column `x`, a vertical mark at the hold's value of
    `mark_param` (or the entry's `mark_value`), and a tick at every row where a `mark_true`
    column is true. Nothing is computed from the data beyond reading it."""
    x, y = str(item.get("x") or ""), str(item.get("y") or "")
    if not x or not y:
        raise ConfigError("a chart needs `x` and `y` column names")
    points: list[list[float]] = []
    for r in rows:
        xv, yv = _number(r.get(x)), _number(r.get(y))
        if xv is not None and yv is not None:
            points.append([xv, yv])
    if not points:
        raise ConfigError(f"no numeric rows for `{x}` and `{y}`")
    marks: list[dict[str, Any]] = []
    param = item.get("mark_param")
    value = _marked_value(hold, str(param)) if param else item.get("mark_value")
    mv = _number(value)
    if mv is not None:
        marks.append({"label": f"{param or 'mark'} = {value}", "x": mv})
    ticks: list[dict[str, Any]] = []
    flags = item.get("mark_true")
    for col in [str(c) for c in flags] if isinstance(flags, list) else []:
        for r in rows:
            xv = _number(r.get(x))
            if xv is not None and _true(r.get(col)):
                ticks.append({"label": f"{col} at {r.get(x)}", "x": xv})
    return {"kind": "chart", "x": x, "y": y, "points": points, "marks": marks, "ticks": ticks}


def chart_svg(section: dict[str, Any], width: int = 720, height: int = 300) -> str:
    """An inline SVG of a chart section: axes, the line, the marks and the ticks, nothing else.
    Escaped text; no script."""
    from markupsafe import escape

    pts: list[list[float]] = [[float(a), float(b)] for a, b in section["points"]]
    left, right, top, bottom = 52, 16, 22, 40
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y1 = max(ys)
    y0 = min(0.0, min(ys))
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1

    def sx(v: float) -> float:
        return left + (v - x0) / (x1 - x0) * (width - left - right)

    def sy(v: float) -> float:
        return top + (1 - (v - y0) / (y1 - y0)) * (height - top - bottom)

    out = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" role="img" '
        f'aria-label="{escape(section["y"])} against {escape(section["x"])}">'
    ]
    step = _nice_step((y1 - y0) / 5)
    v = y0
    while v <= y1 + 1e-9:
        out.append(
            f'<line class="grid" x1="{left}" x2="{width - right}" y1="{sy(v):.1f}" y2="{sy(v):.1f}"/>'
            f'<text class="muted" x="{left - 8}" y="{sy(v) + 4:.1f}" text-anchor="end">{_short(v)}</text>'
        )
        v += step
    out.append(
        f'<line class="axis" x1="{left}" x2="{width - right}" y1="{sy(y0):.1f}" y2="{sy(y0):.1f}"/>'
    )
    xstep = _nice_step((x1 - x0) / 8)
    v = x0
    while v <= x1 + 1e-9:
        out.append(
            f'<text class="muted" x="{sx(v):.1f}" y="{height - bottom + 16}" text-anchor="middle">{_short(v)}</text>'
        )
        v += xstep
    out.append(
        f'<text class="muted" x="{(left + width - right) / 2:.1f}" y="{height - 6}" text-anchor="middle">{escape(section["x"])}</text>'
    )
    out.append(f'<text class="muted" x="{left}" y="{top - 8}">{escape(section["y"])}</text>')
    for m in section["marks"]:
        mx = sx(m["x"])
        out.append(
            f'<line class="mark" x1="{mx:.1f}" x2="{mx:.1f}" y1="{top}" y2="{sy(y0):.1f}"/>'
            f'<text x="{mx + 6:.1f}" y="{top + 12}">{escape(m["label"])}</text>'
        )
    for i, t in enumerate(section["ticks"]):
        tx = sx(t["x"])
        ty = top + 34 + 16 * i
        out.append(
            f'<line class="tick" x1="{tx:.1f}" x2="{tx:.1f}" y1="{top + 30 + 16 * i}" y2="{sy(y0):.1f}"/>'
            f'<text class="muted" x="{tx + 5:.1f}" y="{ty}">{escape(t["label"])}</text>'
        )
    d = " ".join(
        f"{'M' if i == 0 else 'L'}{sx(p[0]):.1f} {sy(p[1]):.1f}" for i, p in enumerate(pts)
    )
    out.append(f'<path class="series" d="{d}"/>')
    for p in pts:
        out.append(
            f'<circle class="pt" cx="{sx(p[0]):.1f}" cy="{sy(p[1]):.1f}" r="3">'
            f"<title>{escape(section['x'])} {_short(p[0])}: {escape(section['y'])} {_short(p[1])}</title></circle>"
        )
    out.append("</svg>")
    return "".join(out)


def _nice_step(raw: float) -> float:
    if raw <= 0:
        return 1.0
    import math

    mag = float(10 ** math.floor(math.log10(raw)))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return float(m * mag)
    return 10 * mag


def _short(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


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
            if isinstance(v, dict)
            and (
                # by predicate, optionally narrowed to a step; or, with no predicate, every
                # hold on the named step (an item hold has no predicate)
                (v.get("predicate") and str(v.get("predicate", "")).split("@")[0] == pred_id)
                or (not v.get("predicate") and v.get("step") == h["step_id"])
            )
            and v.get("step") in (None, h["step_id"])  # an entry may name the step it is for
            and not ("{item}" in str(v.get("source", "")) and h["item_id"] is None)
        ]
        hold_info = {
            "item_id": h["item_id"],
            "step_id": h["step_id"],
            "evidence": ctx.get("evidence"),
        }
        payload["sections"] += render_items(project, h["run_id"], matching, None, hold_info)[0]
        ns = skill.get("never_show")
        payload["never_show"] = [str(x) for x in ns] if isinstance(ns, list) else []
    return payload


def present_step(
    project: Site, run_id: str, step_id: str, skills_dir: Path | None = None
) -> dict[str, Any]:
    """The method's `step_view` entries for one step of a run (console-and-fleet-plan 3.8):
    what a person sees of a step outside a hold, once the step has produced it."""
    skill, note = load_skill(project, skills_dir)
    payload: dict[str, Any] = {
        "schema": "stringency.present/1",
        "kind": "step",
        "run_id": run_id,
        "step_id": step_id,
        "skill": note,
        "sections": [],
        "files": [],
        "never_show": [],
    }
    if skill is None:
        return payload
    raw = skill.get("step_view")
    views = (
        [v for v in raw if isinstance(v, dict) and v.get("step") == step_id]
        if isinstance(raw, list)
        else []
    )
    if views:
        payload["sections"] += render_items(project, run_id, views, None)[0]
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
{% elif s.kind == "figure" %}<div class="figs{% if s.beside %} pair{% endif %}">
<figure><img class="fig" src="{{ url(s.path) }}" alt="{{ s.caption or s.title }}"><figcaption>{{ s.caption or s.path.rsplit("/", 1)[-1] }}</figcaption></figure>
{% if s.beside %}<figure><img class="fig" src="{{ url(s.beside) }}" alt="{{ s.beside_caption or s.beside }}"><figcaption>{{ s.beside_caption or s.beside.rsplit("/", 1)[-1] }}</figcaption></figure>
{% elif s.beside_missing %}<p class="note">(beside: {{ s.beside_missing }} not found for this run)</p>{% endif %}
</div>
{% elif s.kind == "figures" %}{% if s.images %}<div class="figs">
{% for im in s.images %}<figure><img class="fig" src="{{ url(im.path) }}" alt="{{ im.what or im.file }}"><figcaption>{{ im.what or im.file }}</figcaption></figure>
{% endfor %}</div>{% else %}<p class="note">(no images in {{ s.dir }})</p>{% endif %}
{% elif s.kind == "chart" %}{{ svg(s) }}
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


def render_html(payload: dict[str, Any], url_for: Callable[[str], str] | None = None) -> str:
    """The same sections as `render_markdown`, as an HTML fragment (escaped; no script). The
    page that embeds it adds the heading, the links and the form, and maps a figure's path on
    disk to a route it serves (`url_for`; the path itself by default)."""
    from markupsafe import Markup

    return SECTIONS_HTML.render(
        sections=payload["sections"],
        files=payload["files"],
        never_show=payload["never_show"],
        skill=payload["skill"],
        url=url_for or (lambda p: p),
        svg=lambda s: Markup(chart_svg(s)),  # noqa: S704 - built from numbers and escaped text
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
        elif s["kind"] == "figure":
            out.append(
                f"figure: {s['path']}" + (f" (beside: {s['beside']})" if s.get("beside") else "")
            )
        elif s["kind"] == "figures":
            out += [f"- {im['path']}: {im['what']}".rstrip(": ") for im in s["images"]] or [
                "(no images)"
            ]
        elif s["kind"] == "chart":
            words = [f"{s['y']} against {s['x']}, {len(s['points'])} points"]
            words += [m["label"] for m in s["marks"]] + [t["label"] for t in s["ticks"]]
            out.append("chart: " + "; ".join(words))
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
