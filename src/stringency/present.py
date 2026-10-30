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
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

from stringency.config import Design, StringencyConfig, load_model
from stringency.db.store import Store
from stringency.exit_codes import ConfigError
from stringency.modules import ModuleIndex
from stringency.pipelines import (
    Pipeline,
    find_pipeline,
    load_pipeline,
    normalise_source,
    open_pipeline,
)
from stringency.plain import progress_sentence
from stringency.predicates.engine.judg import NUMERAL, numeral_matches
from stringency.tables import KEY_SEP, is_tabular

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
    # another checkout of a method to read the tools and skill files from (`tools list
    # --method`, L135); the project's own `method/` when None
    method_dir: Path | None = None

    @property
    def method_root(self) -> Path:
        return self.method_dir if self.method_dir is not None else self.root / "method"

    @classmethod
    def load(cls, root: Path) -> Site:
        root = Path(root).resolve()
        if not (root / "stringency.yml").exists():
            raise ConfigError(f"{root} is not a stringency project (no stringency.yml)")
        cfg = load_model(StringencyConfig, root / "stringency.yml")
        store = Store.open(root / "prov" / "run.db", create=False)
        if cfg.pipeline is None:
            # an open project: the empty topology, built without the plugin (its questions are
            # not needed to read results)
            pipeline = open_pipeline(cfg.domain or "", cfg.method.tag, [])
        else:
            pipeline = load_pipeline(find_pipeline(root / "method", cfg.pipeline))
        return cls(root, cfg, store, pipeline)

    @property
    def open_ended(self) -> bool:
        return self.config.pipeline is None

    @property
    def skill_name(self) -> str:
        """The delivery skill file's stem: the pipeline's name, or `open` for an open project."""
        return self.config.pipeline or "open"

    def tools(self) -> list[Any]:
        """The method's modules that list `open` (open_mode_plan.md 1). Reads the module index."""
        return [m for m in ModuleIndex(self.method_root).all() if "open" in m.manifest.modes]

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
    f = d / f"{project.skill_name}.yml"
    if not f.exists():
        return None, f"no delivery skill at {f}; showing the engine default"
    try:
        data = yaml.safe_load(f.read_text())
    except yaml.YAMLError as e:
        return None, f"delivery skill {f} is not valid YAML ({e}); showing the engine default"
    if not isinstance(data, dict) or data.get("skill") != 1:
        return None, f"delivery skill {f} is not a `skill: 1` document; showing the engine default"
    if data.get("pipeline") not in (None, project.skill_name):
        return None, (
            f"delivery skill {f} is for pipeline {data.get('pipeline')}, not "
            f"{project.skill_name}; showing the engine default"
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


def _data_lines(text: str) -> list[str]:
    """The lines of a delimited file without its leading `#` comment lines (a draft file opens
    with one; read as the header it drew fifty blank rows, backlog L25)."""
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return lines


def _rows_from_table(path: Path) -> list[dict[str, Any]]:
    lines = _data_lines(path.read_text())
    delim = (
        "\t"
        if path.suffix.lower() in (".tsv", ".tab") or ("\t" in lines[0] if lines else False)
        else ","
    )
    return [dict(r) for r in csv.DictReader(lines, delimiter=delim)]


def _flat_json_object(path: Path) -> dict[str, Any] | None:
    """The file's content when it is a JSON object whose values are all scalars (a method's
    `analysis_summary`); None for anything else, read errors included."""
    if path.suffix.lower() != ".json":
        return None
    try:
        node = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(node, dict) or not node:
        return None
    if all(v is None or isinstance(v, (str, int, float, bool)) for v in node.values()):
        return node
    return None


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
    if step and rest and "/" not in rest:
        # `<step>/<output>` by the output's name, whatever file the module wrote it to (the
        # decision block and `propose --cite` name outputs this way; L61, L55)
        row = project.store.one(
            "SELECT path FROM artifacts WHERE run_id = ? AND step_id = ? AND name = ? AND "
            "status = 'produced' ORDER BY rowid DESC LIMIT 1",
            (run_id, step, rest.split(".")[0]),
        )
        if row is not None and Path(str(row["path"])).exists():
            return Path(str(row["path"]))
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
    before = 0
    prev_src = ""
    for item in items:
        for s in sections[before:]:
            s.setdefault("source", prev_src)  # the source each section came from (L62)
        before = len(sections)
        title = str(item.get("title") or item.get("source") or "")
        kind = str(item.get("kind") or "table")
        src = _fill(str(item.get("source") or ""), hold)
        prev_src = src
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
            facts = _flat_json_object(path)
            if facts is not None:
                # a JSON object of named facts reads as a two-column table, not as JSON
                rows = [{"fact": k, "value": v} for k, v in facts.items()]
                sections.append(
                    {"title": title, "kind": "table", **_table(rows, ["fact", "value"], {})}
                )
                continue
            sections.append(
                {
                    "title": title,
                    "kind": "text",
                    "markdown": path.suffix.lower() == ".md",
                    "text": path.read_text(),
                }
            )
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
        note: str | None = None
        where = item.get("where")
        if isinstance(where, dict) and where.get("column"):
            rows, note = _where(rows, where, hold)
        elif isinstance(where, str):
            try:
                rows = apply_where(rows, where)
            except ValueError as e:
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
        section = {"title": title, "kind": kind, **_table(rows, cols, fmts)}
        if note:
            section["note"] = note
        sections.append(section)
    for s in sections[before:]:
        s.setdefault("source", prev_src)
    return sections, files


def _where(
    rows: list[dict[str, Any]], where: dict[str, Any], hold: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], str | None]:
    """`where: {column, equals}` on a table entry keeps the rows whose column equals the value;
    `equals: $param.<name>` is the hold's proposed value of that parameter, so a sign-off shows
    the rows the proposed value keeps (backlog L26). When this hold proposes no such value every
    row is kept and the section says so."""
    col = str(where["column"])
    eq = where.get("equals")
    if isinstance(eq, str) and eq.startswith("$param."):
        name = eq[len("$param.") :]
        value = _marked_value(hold, name)
        if value is None:
            return (
                rows,
                f"where {col} = {eq}: this hold proposes no value for {name}; every row is shown",
            )
    else:
        value = eq
    return [r for r in rows if str(r.get(col)) == str(value)], None


def parse_where(clause: str) -> tuple[str, list[str]]:
    """A view's `where:` clause (L134 e), one clause: `<column> = <value>` or `<column> in
    <v1>,<v2>`. Returns the column and the values a row's cell may equal; a value may be quoted.
    Raises ValueError naming the forms when the clause is neither."""
    text = clause.strip()
    one = re.fullmatch(r"([^\s=]+)\s*=\s*(.+)", text)
    many = None if one else re.fullmatch(r"([^\s=]+)\s+in\s+(.+)", text)
    m = one or many
    if m is None:
        raise ValueError(f"where `{clause}` is not `<column> = <value>` or `<column> in <v1>,<v2>`")
    column = m.group(1)
    raw = m.group(2).split(",") if many else [m.group(2)]
    values = [v.strip().strip("'\"") for v in raw]
    if not all(values):
        raise ValueError(f"where `{clause}` names an empty value")
    return column, values


def apply_where(rows: list[dict[str, Any]], clause: str) -> list[dict[str, Any]]:
    """The rows whose `column` cell is one of the clause's values, compared as text. Raises
    ValueError when the clause does not parse or the table has rows but no such column."""
    column, values = parse_where(clause)
    if rows and column not in rows[0]:
        raise ValueError(f"where `{clause}`: the table has no column {column}")
    wanted = set(values)
    return [r for r in rows if str(r.get(column)) in wanted]


def _captions(directory: Path) -> dict[str, str]:
    """The method's captions from `figures.csv` beside the images (`file,what`)."""
    f = directory / FIGURES_MANIFEST
    if not f.is_file():
        return {}
    try:
        return {
            str(r.get("file") or ""): str(r.get("what") or "")
            for r in csv.DictReader(_data_lines(f.read_text()))
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
    """The after-delivery view of a run (the latest completed run by default; on an open
    project the latest run with a delivery, since an open run never completes)."""
    if run_id is None:
        row = (
            project.store.one("SELECT run_id FROM deliveries ORDER BY ts DESC, rowid DESC LIMIT 1")
            if project.open_ended
            else project.store.one(
                "SELECT run_id FROM runs WHERE status = 'completed' ORDER BY ended DESC, rowid DESC LIMIT 1"
            )
        )
        if row is None:
            raise ConfigError(
                "no delivered run to present"
                if project.open_ended
                else "no completed run to present"
            )
        run_id = row["run_id"]
    if project.store.one("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)) is None:
        raise ConfigError(f"no run {run_id}")
    deliver_dir = _deliver_dir(project, run_id)
    skill, note = load_skill(project, skills_dir)
    payload: dict[str, Any] = {
        "schema": "stringency.present/1",
        "kind": "run",
        "run_id": run_id,
        "pipeline": project.skill_name,
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


def record_presented(project: Site, payload: dict[str, Any]) -> int | None:
    """`present` writes one `run_events` row `presented` (backlog L62): the sources it rendered,
    the hold if any, the step, the OS user and the operator session. Rendering is not reading;
    the absence of this event is what the hold's line reports. Writes: run_events. Returns the
    event's seq, or None when the payload names no run."""
    import getpass
    import os

    from stringency.operator_id import operator_env

    run_id = payload.get("run_id")
    if not run_id:
        return None
    sources: list[str] = []
    for s in payload.get("sections") or []:
        src = s.get("source")
        if src and src not in sources:
            sources.append(str(src))
    return project.store.run_event(
        str(run_id),
        "presented",
        {
            "kind": payload.get("kind"),
            "hold_id": payload.get("hold_id"),
            "step_id": payload.get("step_id"),
            "sources": sources,
            "user": os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser(),
            "session_ref": operator_env().get("session_ref"),
        },
    )


def presented_line(
    store: Store, run_id: str, proposed_at: str, sources: list[str], steps: list[str]
) -> str:
    """The parameter hold's provenance line (L62, L131). First a `rendered` event in
    `step_events` on one of `steps` (the evidence's steps) at or before `proposed_at`: "rendered by
    present --step <step> at <ts>". Then the latest `presented` event before `proposed_at` that
    rendered one of `sources` or any output of `steps`. Else the statement that the evidence was
    not rendered, naming its steps. Reads: step_events, run_events."""
    if steps:
        marks = ",".join("?" for _ in steps)
        rendered = store.one(
            f"SELECT step_id, ts FROM step_events WHERE run_id=? AND event='rendered' AND "  # noqa: S608
            f"step_id IN ({marks}) AND ts <= ? ORDER BY ts DESC, seq DESC LIMIT 1",
            (run_id, *steps, proposed_at),
        )
        if rendered is not None:
            return f"rendered by present --step {rendered['step_id']} at {rendered['ts']}"
    rows = store.all(
        "SELECT payload_json, ts FROM run_events WHERE run_id=? AND event='presented' AND ts <= ? "
        "ORDER BY seq DESC",
        (run_id, proposed_at),
    )
    wanted = {normalise_source(s) for s in sources}
    for r in rows:
        p = json.loads(r["payload_json"] or "{}")
        got = [normalise_source(str(s)) for s in p.get("sources") or []]
        hit = any(g in wanted or g.split("/")[0] in steps for g in got) or (
            p.get("step_id") in steps
        )
        if hit:
            who = "the operator session" if p.get("session_ref") else f"user {p.get('user')}"
            return f"evidence rendered {_hhmm(r['ts'])} by {who}, proposed {_hhmm(proposed_at)}"
    where = f" of {', '.join(steps)}" if steps else ""
    return (
        f"not rendered: the operator proposed without rendering the evidence{where} through "
        "`present` (it read the table another way, or not at all)"
    )


def _hhmm(ts: str) -> str:
    return ts[11:16] if len(ts) >= 16 else ts


def decision_sections(
    project: Site, run_id: str, step_id: str, proposed: dict[str, Any]
) -> list[dict[str, Any]]:
    """The default hold view of a parameter hold (L61), with the method's skill silent: for
    each proposed parameter, its declared evidence (a source rendered as a table, figure or
    text by its extension; a `text:` sentence; the method's `because` for none), then the
    parameter table. Reads the run's files; writes nothing."""
    if not project.pipeline.has_step(step_id):
        return []
    step = project.pipeline.step(step_id)
    sections: list[dict[str, Any]] = []
    for name in proposed:
        decl = step.params.get(name)
        if decl is None or decl.decision is None:
            continue
        ev = decl.decision.evidence
        if ev.source:
            suffix = Path(ev.source).suffix.lower()
            kind = (
                "figure"
                if suffix in (".png", ".svg", ".jpg", ".jpeg", ".pdf")
                else ("table" if suffix in (".csv", ".tsv", ".txt", "") else "text")
            )
            sections += render_items(
                project,
                run_id,
                [
                    {
                        "title": f"{name}: the evidence the method names ({ev.source})",
                        "source": ev.source,
                        "kind": kind,
                    }
                ],
                None,
                {"step_id": step_id, "evidence": {"proposed": proposed}},
            )[0]
        elif ev.text:
            sections.append(
                {"title": f"{name}: the evidence the method names", "kind": "text", "text": ev.text}
            )
        else:
            sections.append(
                {
                    "title": f"{name}: no evidence, by the method's own words",
                    "kind": "text",
                    "text": str(ev.because),
                }
            )
    rows = [
        {
            "parameter": name,
            "default": p.get("default") if isinstance(p, dict) else None,
            "proposed": p.get("proposed") if isinstance(p, dict) else p,
        }
        for name, p in proposed.items()
    ]
    if rows:
        sections.append(
            {
                "title": "The decision",
                "kind": "table",
                **_table(rows, ["parameter", "default", "proposed"], {}),
            }
        )
    return sections


def present_hold(
    project: Site, hold_id: str | None, skills_dir: Path | None = None
) -> dict[str, Any]:
    """The hold view: kind, reason, the review commands, and the skill's tables for the predicate
    that opened it. A hold a predicate opened carries its packet (L133): the question, the rule
    with the facts, the evidence scoped to the items it names, and what each verdict does. An
    open project's confirm hold carries the bound delivery as rows (L137). Reads: holds,
    actions, messages, judgments, artifacts, step_events, run_events; the files the views name."""
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
    if h["kind"] == "confirm" and project.open_ended and not isinstance(ctx.get("bound"), dict):
        bound = _bound_now(project)  # a confirm hold written before L137 carries no rows
        if bound is not None:
            ctx = {**ctx, "bound": bound}
    predicate = str(ctx.get("predicate") or "")
    pred_id = predicate.split("@")[0]
    who = (
        project.config.roles.reviewer
        if h["waits_on_role"] == "reviewer"
        else project.config.roles.owner
    )
    skill, note = load_skill(project, skills_dir)
    from stringency.console import plain_block
    from stringency.notify import console_url

    plain = plain_block(h, ctx)
    payload: dict[str, Any] = {
        "schema": "stringency.present/1",
        "kind": "hold",
        "hold_id": h["hold_id"],
        "hold_kind": h["kind"],
        "reason": h["reason"],
        "check": plain["check"],
        "found": plain["found"],
        "compared": plain["compared"],
        "guidance": plain.get("guidance") or [],
        "waits_on": who,
        "step_id": h["step_id"],
        "run_id": h["run_id"],
        "predicate": predicate or None,
        "evidence": ctx.get("evidence"),
        # the console's page for the hold when `page_url` is set (L134 b)
        "console_url": console_url(str(h["hold_id"])),
        "review": {
            "accept": f'stringency review --verdict accept --hold {h["hold_id"]} --reason "<why>"',
            "reject": f'stringency review --verdict reject --hold {h["hold_id"]} --reason "<why>"',
        },
        "skill": note,
        "sections": [],
        "files": [],
        "never_show": [],
    }
    if pred_id:
        from stringency.packets import flag_packet
        from stringency.review_render import verdicts_for

        verdicts = verdicts_for(
            "flag", h["hold_id"], str(ctx.get("phase") or "post"), predicate=predicate
        )
        payload["packet"] = flag_packet(
            h, ctx, verdicts, criteria=_criteria(project), store=project.store
        )
        for v in verdicts:
            if v["verdict"] == "override":
                payload["review"]["override"] = v["command"]
    if h["kind"] == "egress":
        report = ctx.get("report_path")
        if report and Path(report).exists():
            payload["sections"].append(
                {
                    "title": "Data egress",
                    "kind": "text",
                    "markdown": True,
                    "folded": "The full report",
                    "text": Path(report).read_text(),
                }
            )
    if h["kind"] == "confirm" and isinstance(ctx.get("bound"), dict):
        payload["bound"] = ctx["bound"]
        payload["sections"] += _open_confirm_sections(ctx["bound"], ctx.get("hashes") or {})
    elif h["kind"] == "confirm":
        echo = ctx.get("echo_path")
        if echo and Path(echo).exists():
            payload["sections"].append(
                {
                    "title": "Echo-back",
                    "kind": "text",
                    "markdown": True,
                    "text": Path(echo).read_text(),
                }
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
        named, why = _named_columns(project, h, ctx) if pred_id.startswith("param.") else ([], "")
        widened = [_widen(project, h["run_id"], v, hold_info, named, why) for v in matching]
        sections = render_items(project, h["run_id"], [w[0] for w in widened], None, hold_info)[0]
        items = (payload.get("packet") or {}).get("evidence", {}).get("items") or (
            [str(h["item_id"])] if h["item_id"] is not None else []
        )
        for (view, added), section in zip(widened, sections, strict=False):
            if added:
                section["note"] = f"beside the method's columns, {', '.join(added)}: named by {why}"
            if view.get("scope") == "item" and items:
                _scope_to_items(section, view, items)
        payload["sections"] += _figures_once(sections)
        ns = skill.get("never_show")
        payload["never_show"] = [str(x) for x in ns] if isinstance(ns, list) else []
    if h["run_id"] and h["step_id"] and not payload["sections"] and pred_id.startswith("param."):
        # a parameter hold with no view from the method's skill (backlog L61): the declared
        # evidence, then the parameter table
        ev = ctx.get("evidence") or {}
        proposed = ev.get("proposed") if isinstance(ev, dict) else None
        if isinstance(proposed, dict):
            payload["sections"] += decision_sections(project, h["run_id"], h["step_id"], proposed)
    if h["run_id"] and h["step_id"] and not payload["sections"]:
        # a judgment hold with no view from the method's skill (backlog K5): the replicates'
        # calls, as written at judgment time, are what the person decides on
        sec = _judgments_section(project, h["run_id"], h["step_id"], h["item_id"])
        if sec is not None:
            payload["sections"].append(sec)
    if h["run_id"] and h["step_id"] and pred_id.startswith("param."):
        payload["presented"] = _presented_for_hold(project, h)
    return payload


def _criteria(project: Site) -> dict[str, dict[str, Any]]:
    """The method policy's confidence bands, for a packet's rule; empty when the policy cannot
    be read (present loads no plugin and must not fail on a policy it cannot parse)."""
    from stringency.packets import criteria_of
    from stringency.policy import load_policy

    try:
        return criteria_of(load_policy(project.root / project.config.policy))
    except (ConfigError, OSError, ValueError):
        return {}


def _bound_now(project: Site) -> dict[str, Any] | None:
    """The bound delivery as rows for an open project's confirm hold written before the hold
    carried them (L137): from `inputs.yml`, `objective.yml` and the method's tools as they are
    now. None when the declarations cannot be read."""
    from stringency.config import InputsManifest, Objective
    from stringency.echo import bound_structure

    try:
        inputs = load_model(InputsManifest, project.root / "inputs.yml")
        objective = load_model(Objective, project.root / "objective.yml")
        tools = [m.manifest.name for m in project.tools()]
    except (ConfigError, OSError, ValueError):
        return None
    return bound_structure(objective, inputs, tools, project.method_root)


def _open_confirm_sections(bound: dict[str, Any], hashes: dict[str, Any]) -> list[dict[str, Any]]:
    """An open project's confirm hold as sections (L137): the switch paragraph once, the bound
    files as a table grouped by step, the upstream input, question and tools as lines, and the
    digests the accept binds to. Nothing is parsed out of the echo file."""
    from stringency.echo import OPEN_SWITCH, bound_rest, bound_table

    rows = bound_table(bound)
    out: list[dict[str, Any]] = [
        {"title": "What opening means", "kind": "text", "text": OPEN_SWITCH},
    ]
    start = 0
    for dv in bound.get("deliveries") or []:
        n = len(dv.get("rows") or [])
        out.append(
            {
                "title": f"The delivery: run {dv['run_id']} of {dv['project']}, by step",
                "kind": "table",
                **_table(rows[start : start + n], ["step", "name", "type", "what"], {}),
            }
        )
        start += n
    out.append(
        {
            "title": "Also bound",
            "kind": "text",
            "markdown": True,
            "text": "\n".join(f"- {line}" for line in bound_rest(bound)),
        }
    )
    if hashes:
        out.append(
            {
                "title": "Bound to",
                "kind": "text",
                "markdown": True,
                "text": "The accept binds to these declaration digests:\n"
                + "\n".join(f"  {k}: {v}" for k, v in sorted(hashes.items())),
            }
        )
    return out


def _named_columns(project: Site, h: Any, ctx: dict[str, Any]) -> tuple[list[str], str]:
    """What a proposal names that could be a column (L131): the columns its citations name and
    the words of the operator's reason and the hold's reason, with a phrase saying where they
    came from. Reads: actions, messages."""
    from stringency.actions import rationale_record

    raw = ctx.get("evidence")
    ev: dict[str, Any] = raw if isinstance(raw, dict) else {}
    cited = [
        str(c["column"]) for c in (ev.get("cited") or []) if isinstance(c, dict) and c.get("column")
    ]
    a = project.store.one(
        "SELECT rationale_ref FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (h["run_id"], h["step_id"]),
    )
    record = (
        rationale_record(project.store.message(a["rationale_ref"]))
        if a is not None and a["rationale_ref"]
        else None
    )
    text = " ".join([str(h["reason"] or ""), str((record or {}).get("text") or "")])
    for c in (record or {}).get("cited") or []:
        if isinstance(c, dict) and c.get("column"):
            cited.append(str(c["column"]))
    return cited + [text], "the proposal's citations or reason"


def _header_of(path: Path) -> list[str]:
    """A delimited file's column names (its first data line); empty when unreadable."""
    if path.is_dir() or path.suffix.lower() not in (".csv", ".tsv", ".tab", ".txt", ""):
        return []
    try:
        with path.open() as fh:
            for line in fh:
                if line.startswith("#") or not line.strip():
                    continue
                delim = "\t" if "\t" in line else ","
                return next(csv.reader([line], delimiter=delim))
    except (OSError, UnicodeDecodeError, StopIteration):
        return []
    return []


def _widen(
    project: Site,
    run_id: str,
    view: dict[str, Any],
    hold: dict[str, Any],
    named: list[str],
    why: str,
) -> tuple[dict[str, Any], list[str]]:
    """A table view with the columns the proposal names added after the view's own (L131): a
    column of the output's header that a citation names, or whose name stands as a word in the
    operator's or the hold's reason. Returns the view to render and the columns added."""
    import re

    cols = view.get("columns")
    if not named or not isinstance(cols, list) or str(view.get("kind") or "table") != "table":
        return view, []
    path = _resolve(project, run_id, _fill(str(view.get("source") or ""), hold), None)
    header = _header_of(path) if path is not None else []
    text = named[-1]
    cited = set(named[:-1])
    added = [
        c
        for c in header
        if c not in cols
        and (c in cited or re.search(rf"(?<![A-Za-z0-9_]){re.escape(c)}(?![A-Za-z0-9_])", text))
    ]
    if not added:
        return view, []
    return {**view, "columns": [*cols, *added]}, added


def _scope_to_items(section: dict[str, Any], view: dict[str, Any], items: list[str]) -> None:
    """`scope: item` on a hold view (L133): a table keeps the rows of the hold's items (by the
    view's `item_column`, else the first column holding one of them); a figures section keeps
    the images whose file or caption names an item, all of them when none does."""
    wanted = set(items)
    section["scope"] = "item"
    if section.get("kind") == "figures":
        images = list(section.get("images") or [])
        mine = [
            im
            for im in images
            if any(
                _names(str(im.get("file") or im.get("path") or ""), i)
                or _names(str(im.get("what") or ""), i)
                for i in wanted
            )
        ]
        if mine:
            section["images"] = mine
        return
    cols = list(section.get("columns") or [])
    rows = list(section.get("rows") or [])
    col = view.get("item_column")
    idx = cols.index(col) if isinstance(col, str) and col in cols else None
    if idx is None:
        idx = next(
            (i for i in range(len(cols)) if any(r[i] in wanted for r in rows)),
            None,
        )
    if idx is None:
        section["note"] = f"no column names {', '.join(items)}; every row is shown"
        return
    section["rows"] = [r for r in rows if r[idx] in wanted]


def _names(text: str, item: str) -> bool:
    import re

    return re.search(rf"(?<![A-Za-z0-9]){re.escape(item)}(?![A-Za-z0-9])", text) is not None


def _figures_once(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each image once across a hold's sections: a later figures section drops images an
    earlier one shows (L133, the maps listed twice)."""
    seen: set[str] = set()
    for s in sections:
        if s.get("kind") != "figures":
            continue
        keep = []
        for im in s.get("images") or []:
            key = str(Path(str(im.get("path"))).resolve())
            if key not in seen:
                seen.add(key)
                keep.append(im)
        s["images"] = keep
    return sections


def _presented_for_hold(project: Site, h: Any) -> str | None:
    """The `presented` line for a parameter hold: from the action behind the hold and the
    decision evidence of its proposed parameters. Reads: actions, run_events."""
    a = project.store.one(
        "SELECT proposed_at, params_json FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (h["run_id"], h["step_id"]),
    )
    if a is None or not project.pipeline.has_step(h["step_id"]):
        return None
    step = project.pipeline.step(h["step_id"])
    sources = [
        d.decision.evidence.source
        for d in step.params.values()
        if d.decision is not None and d.decision.evidence.source
    ]
    steps = sorted({s.split("/")[0] for s in sources if not s.startswith("$inputs.")})
    return presented_line(project.store, h["run_id"], a["proposed_at"], sources, steps)


def _judgments_section(
    project: Site, run_id: str, step_id: str, item_id: str | None
) -> dict[str, Any] | None:
    """The step's `judgments` output (one line per item and replicate) as a table, narrowed to
    the hold's item when it has one. Reads: artifacts, the file. None when the step has none."""
    art = project.store.one(
        "SELECT path FROM artifacts WHERE run_id=? AND step_id=? AND kind='judgments' AND "
        "status='produced' ORDER BY rowid DESC LIMIT 1",
        (run_id, step_id),
    )
    if art is None:
        return None
    try:
        lines = Path(str(art["path"])).read_text().splitlines()
    except OSError:
        return None
    rows: list[dict[str, Any]] = []
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        if item_id is not None and str(d.get("item_id", d.get("item"))) != str(item_id):
            continue
        rows.append(d)
    if not rows:
        return None
    # who answered each replicate (backlog L70), from its latest invocation on the step
    judges = {
        int(i["replicate"]): i
        for i in project.store.all(
            "SELECT replicate, model_resolved, via, isolation FROM invocations WHERE run_id=? AND "
            "step_id=? ORDER BY rowid",
            (run_id, step_id),
        )
    }
    for r in rows:
        j = judges.get(int(r["replicate"])) if str(r.get("replicate", "")).isdigit() else None
        if j is not None:
            r["judge"] = f"{j['model_resolved']} via {j['via']}, isolation {j['isolation']}"
    preferred = [
        "item_id",
        "item",
        "replicate",
        "judge",
        "label",
        "confidence",
        "abstain",
        "rationale",
    ]
    cols = [c for c in preferred if any(c in r for r in rows)]
    title = "The replicates' judgments" + (f" for {item_id}" if item_id is not None else "")
    return {"title": title, "kind": "table", **_table(rows, cols, {})}


# -- answers (open mode, open_mode_plan.md 2.7) ------------------------------------------------


def _answer_rows(project: Site, run_id: str | None) -> list[Any]:
    if run_id is None:
        return project.store.all(
            "SELECT a.*, q.seq, q.origin, q.text_ref AS q_ref FROM answers a JOIN questions q ON "
            "q.question_id = a.question_id ORDER BY a.ts, a.rowid"
        )
    return project.store.all(
        "SELECT a.*, q.seq, q.origin, q.text_ref AS q_ref FROM answers a JOIN questions q ON "
        "q.question_id = a.question_id WHERE a.run_id = ? ORDER BY a.ts, a.rowid",
        (run_id,),
    )


def _answer_views(project: Site, skills_dir: Path | None) -> list[dict[str, Any]]:
    """The method's `answer_view` entries from `skills/open.yml`: `{tool, title, output, kind,
    columns, head}`; a malformed file yields none."""
    d = Path(skills_dir) if skills_dir else project.method_root / "skills"
    f = d / "open.yml"
    if not f.is_file():
        return []
    try:
        data = yaml.safe_load(f.read_text())
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict) or data.get("skill") != 1:
        return []
    raw = data.get("answer_view")
    return [v for v in raw if isinstance(v, dict)] if isinstance(raw, list) else []


def _report_entry(project: Site, run_id: str, answer_id: str) -> dict[str, Any] | None:
    """The report's entry for an answer (the latest `index.json` of the run that lists it):
    its file, and whether it is a finding, by whom and when. Every admissible answer is in
    the report once it is filed (2026-10-19). Reads: deliveries and `index.json`."""
    for d in project.store.all(
        "SELECT path FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC", (run_id,)
    ):
        idx = Path(d["path"]) / "index.json"
        if not idx.exists():
            continue
        try:
            data = json.loads(idx.read_text())
        except json.JSONDecodeError:
            continue
        for a in data.get("answers", []):
            if a.get("answer_id") == answer_id:
                return {**a, "path": str(Path(d["path"]) / str(a.get("file")))}
    return None


def answer_sections(
    project: Site,
    run_id: str,
    prov: dict[str, Any],
    cited: list[dict[str, Any]],
    skills_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The tables and figures shown beside an answer: those the method's `answer_view` names
    for the tools on the answer's path, else every cited table's cited rows with their row
    names, and every cited figure. Shared by `present --answer` and the open project's
    `report.md` (2026-10-19). Returns (sections, the views read). Reads: artifacts, steps."""
    sections: list[dict[str, Any]] = []
    views = _answer_views(project, skills_dir)
    tools = [str(t) for t in prov.get("tools", [])]
    shown: set[str] = set()
    for v in views:
        tool = str(v.get("tool") or "")
        if not any(t.split("@")[0] == tool for t in tools):
            continue
        art = project.store.one(
            "SELECT * FROM artifacts WHERE run_id = ? AND name = ? AND status = 'produced' AND step_id IN "
            "(SELECT step_id FROM steps WHERE run_id = ? AND module = ?) ORDER BY rowid DESC LIMIT 1",
            (run_id, str(v.get("output") or ""), run_id, tool),
        )
        if art is None:
            sections.append(
                {
                    "title": str(v.get("title") or tool),
                    "kind": str(v.get("kind") or "table"),
                    "error": f"output {v.get('output')} of {tool} not found",
                }
            )
            continue
        sections.append(_artifact_section(project, art, v))
        shown.add(str(art["artifact_id"]))
    for c in cited:
        aid = str(c.get("artifact_id"))
        if aid in shown:
            continue
        art = project.store.one("SELECT * FROM artifacts WHERE artifact_id = ?", (aid,))
        if art is None:
            continue
        shown.add(aid)
        cells = (prov.get("cells") or {}).get(aid)
        if is_tabular(str(art["kind"]), str(art["path"])) and cells:
            # the row names lead the table: without them a column of counts says nothing; the
            # key the answer was filed under (L138), the first column for an answer filed
            # before keys were recorded
            key = str((prov.get("keys") or {}).get(aid) or "") or _key_column(
                Path(str(art["path"]))
            )
            rows = [{key: k, **dict(r)} for k, r in cells.items()]
            cols = list(rows[0].keys()) if rows else []
            sections.append(
                {"title": f"{art['name']} (cited rows)", "kind": "table", **_table(rows, cols, {})}
            )
        else:
            sections.append(
                _artifact_section(
                    project,
                    art,
                    {"title": art["name"], "kind": "figure" if art["kind"] == "figure" else "file"},
                )
            )
    return sections, views


def _said(written: str, value: Any) -> bool:
    """`written` is `value` as the text says it: the gate's rule (`numeral_matches`), except a
    numeral in exponent form, which matches at its written significant digits only (the gate's
    absolute tolerance would match any two values below 1e-12, every p value of a table)."""
    if "e" not in written.lower():
        return numeral_matches(written, value)
    try:
        fw, fv = float(written), float(value)
    except (TypeError, ValueError):
        return False
    mantissa = written.lower().split("e", 1)[0]
    d = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return f"{fv:.{d}e}" == f"{fw:.{d}e}"


def _design_levels(project: Site) -> set[str]:
    """The numerals of the design's factor levels as written (`6`, `24`): a time point named in
    the text says which rows, not a cell, so it selects no column. Reads design.yml."""
    try:
        design = load_model(Design, project.root / "design.yml")
    except Exception:  # noqa: BLE001  (a reading view never fails on the design)
        return set()
    out: set[str] = set()
    for f in (design.factors or {}).values():
        for lv in f.levels:
            out.update(NUMERAL.findall(str(lv)))
    return out


def chat_tables(
    project: Site, prov: dict[str, Any], cited: list[dict[str, Any]], text: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The relay-ready part of an answer (L141): one table per cited table, its key columns and
    the cited cells only, and the cited figures. A table's rows are the rows cited by key, and
    for a table cited whole the rows holding a cell a numeral of the text matches; its columns
    are the columns cited by name and those holding such a cell, or every cited column when no
    numeral matches one, in the table's order. A numeral that is a level of a design factor or a
    value of a cited row's key names rows, and selects nothing. A cited table with no row to show is listed by name with no rows.
    Returns (tables, cited figures). Reads: artifacts."""
    cells: dict[str, dict[str, dict[str, Any]]] = prov.get("cells") or {}
    keys: dict[str, str] = prov.get("keys") or {}
    # a numeral that names rows (a design level, a value of a cited row's key) selects nothing
    naming = _design_levels(project) | {
        n for rows in cells.values() for k in rows for n in NUMERAL.findall(str(k))
    }
    nums = [m.group(0) for m in NUMERAL.finditer(text) if m.group(0) not in naming]

    def hit(v: Any) -> bool:
        return any(_said(n, v) for n in nums)

    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    for aid in dict.fromkeys(str(c.get("artifact_id")) for c in cited):
        art = project.store.one("SELECT * FROM artifacts WHERE artifact_id = ?", (aid,))
        if art is None:
            continue
        if not is_tabular(str(art["kind"]), str(art["path"])):
            if str(art["kind"]) == "figure":
                figures.append({"artifact_id": aid, "name": art["name"], "path": art["path"]})
            continue
        mine = [c for c in cited if str(c.get("artifact_id")) == aid]
        whole = any(not c.get("row") for c in mine)
        named_rows = [str(c["row"]) for c in mine if c.get("row")]
        stored = cells.get(aid) or {}
        # in the order the answer cited them (the stored cells are keyed in sorted order)
        rows = {k: stored[k] for k in named_rows if k in stored} | stored
        key_names = (keys.get(aid) or _key_column(Path(str(art["path"])))).split(KEY_SEP)
        shown = {
            k: r
            for k, r in rows.items()
            if not whole or k in named_rows or any(map(hit, r.values()))
        }
        cols: list[str] = []
        for c in mine:
            if c.get("column") and c["column"] not in cols:
                cols.append(str(c["column"]))
        for r in shown.values():
            cols += [c for c, v in r.items() if c not in key_names and c not in cols and hit(v)]
        if not cols:
            for r in shown.values():
                cols += [c for c in r if c not in key_names and c not in cols]
        header = _header(Path(str(art["path"])))
        cols.sort(key=lambda c: header.index(c) if c in header else len(header))
        out_rows: list[dict[str, Any]] = []
        for k, r in shown.items():
            parts = k.split(KEY_SEP)
            names = key_names if len(parts) == len(key_names) else [KEY_SEP.join(key_names)]
            vals = parts if len(parts) == len(key_names) else [k]
            out_rows.append({**dict(zip(names, vals, strict=True)), **{c: r.get(c) for c in cols}})
        head = (
            key_names
            if all(len(k.split(KEY_SEP)) == len(key_names) for k in shown)
            else [KEY_SEP.join(key_names)]
        )
        tables.append(
            {
                "artifact_id": aid,
                "title": str(art["name"]),
                "kind": "table",
                **_table(out_rows, head + cols, {}),
            }
        )
    return tables, figures


def render_chat(payload: dict[str, Any]) -> str:
    """`present --answer --chat` (L141): the block the operator pastes under its reply, the
    cited rows first, then each cited or attached figure's path (an attached figure with its own
    label), then the label sentence."""
    chat = payload["chat"]
    out: list[str] = []
    for t in chat["tables"]:
        out.append(f"**{t['title']}**")
        out.append("")
        if t["rows"]:
            out.append(markdown_table(t["columns"], t["rows"]))
        else:
            out.append("(cited; no number in the text comes from it)")
        out.append("")
    for f in chat["figures"]:
        out.append(f"Figure {f['name']}: {f['path']}")
    for f in payload.get("figures") or []:
        out.append(f"Figure {f['name']}: {f['path']}")
        out.append(str(f.get("label_line") or ""))
    if chat["figures"] or payload.get("figures"):
        out.append("")
    out.append(payload["label_sentence"] or "")
    return "\n".join(out) + "\n"


def present_answer(
    project: Site,
    answer_id: str,
    skills_dir: Path | None = None,
    *,
    details: bool = False,
    chat: bool = False,
) -> dict[str, Any]:
    """One answer as the operator reads it to compose the reply (open_mode_plan.md 2.7;
    2026-10-19, the owner's second drive): the question, the text, the tables and figures the
    method's `answer_view` names for the tool (else every cited table's cited rows, with the
    row names), the label sentence, the parameters the person settled, and the delivered file
    when there is one; with `details`, also the qualifier line, the cells the numbers were
    checked against, every decision with its source and the ids. The figures attached to the
    answer (L143) are listed with their own labels. With `chat` (L141), `chat` holds the
    relay-ready block (`chat_tables`) and the full view renders only with `details`. Loads no
    plugin. Reads: answers, questions, messages, artifacts, deliveries."""
    row = project.store.one(
        "SELECT a.*, q.seq, q.origin, q.text_ref AS q_ref FROM answers a JOIN questions q ON "
        "q.question_id = a.question_id WHERE a.answer_id = ?",
        (answer_id,),
    )
    if row is None:
        raise ConfigError(f"no answer {answer_id}")
    prov = json.loads(row["provenance_json"] or "{}")
    cited = json.loads(row["cited_json"] or "[]")
    tools = [str(t) for t in prov.get("tools", [])]
    sections, views = answer_sections(project, row["run_id"], prov, cited, skills_dir)
    entry = _report_entry(project, row["run_id"], answer_id)
    text = project.store.message(row["text_ref"]) or ""
    block = None
    if chat:
        tables, cited_figures = chat_tables(project, prov, cited, text)
        block = {"tables": tables, "figures": cited_figures}
    return {
        "schema": "stringency.present/1",
        "kind": "answer",
        "run_id": row["run_id"],
        "answer_id": answer_id,
        "question_id": row["question_id"],
        "question": project.store.message(row["q_ref"]) or "",
        "seq": row["seq"],
        "origin": row["origin"],
        "status": row["status"],
        "label": row["label"],
        "label_sentence": prov.get("label_sentence"),
        "qualifier": prov.get("qualifier_line"),
        "route": prov.get("route"),
        "tools": tools,
        "text": text,
        # the question's wants beside the cited steps' gives (L139); None before 0.2.35
        "fit": prov.get("fit"),
        "sections": sections,
        "figures": [
            {k: f.get(k) for k in ("artifact_id", "name", "path", "label", "label_line")}
            for f in prov.get("figures") or []
        ],
        "cited": cited,
        "cells": prov.get("cells") or {},
        "decisions": prov.get("decisions") or [],
        "files": [entry["path"]] if entry else [],
        "report": entry,
        "never_show": [],
        "details": details,
        **({"chat": block} if block is not None else {}),
        "skill": "answer view from skills/open.yml" if views else "the engine default answer view",
    }


def _finding_words(entry: dict[str, Any]) -> str:
    """`a finding, marked by X on <date>` or `not marked as a finding`."""
    if not entry.get("finding"):
        return "not marked as a finding"
    by, ts = entry.get("finding_by") or "the person", str(entry.get("finding_ts") or "")[:10]
    return f"a finding, marked by {by} on {ts}" if ts else f"a finding, marked by {by}"


def _header(path: Path) -> list[str]:
    """A delimited table's column names; none when it cannot be read."""
    try:
        lines = _data_lines(path.read_text())
        delim = "\t" if path.suffix.lower() in (".tsv", ".tab") or "\t" in lines[0] else ","
        return next(csv.reader(lines[:1], delimiter=delim))
    except Exception:  # noqa: BLE001  (a reading view never fails on one table)
        return []


def _key_column(path: Path) -> str:
    """The first column's name, the row key of an answer filed before the answer recorded its
    keys (0.2.35, L138); `row` when it cannot be read."""
    header = _header(path)
    return header[0] if header and header[0] else "row"


def _settled_lines(decisions: list[dict[str, Any]]) -> list[str]:
    """The parameters the person settled, and the ones the assistant proposed and the person
    approved at a hold, in words; defaults and declared values are left to `--details`."""
    you = [f"{d['param']} = {d['value']}" for d in decisions if d.get("source") == "person"]
    agent = [f"{d['param']} = {d['value']}" for d in decisions if d.get("source") == "agent"]
    out = []
    if you:
        out.append("You set: " + "; ".join(you) + ".")
    if agent:
        out.append("Proposed by the assistant and approved at a hold: " + "; ".join(agent) + ".")
    return out


def _artifact_section(project: Site, art: Any, view: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(art["path"]))
    title = str(view.get("title") or art["name"])
    kind = str(view.get("kind") or ("figure" if art["kind"] == "figure" else "table"))
    if kind == "figure":
        return {
            "title": title,
            "kind": "figure",
            "path": str(path),
            "caption": None,
            "beside": None,
            "beside_caption": None,
            "beside_missing": None,
        }
    if kind == "file" or not is_tabular(str(art["kind"]), path):
        return {"title": title, "kind": "file", "path": str(path)}
    try:
        rows = _rows_from_table(path)
    except (OSError, ValueError) as e:
        return {"title": title, "kind": "table", "error": f"{path.name}: {e}"}
    if isinstance(view.get("where"), str):  # the view's filter (L134 e)
        try:
            rows = apply_where(rows, str(view["where"]))
        except ValueError as e:
            return {"title": title, "kind": "table", "error": f"{path.name}: {e}"}
    head = view.get("head")
    note = None
    if isinstance(head, int) and len(rows) > head:
        note = f"first {head} of {len(rows)} rows"
        rows = rows[:head]
    raw_cols = view.get("columns")
    cols = [str(c) for c in raw_cols] if isinstance(raw_cols, list) else None
    sec = {"title": title, "kind": "table", **_table(rows, cols, {})}
    if note:
        sec["note"] = note
    return sec


def present_answers(project: Site, run_id: str | None = None) -> dict[str, Any]:
    """Every answer, newest last: id, question, label, status, whether it is in the report
    and whether it is a finding."""
    items = []
    for r in _answer_rows(project, run_id):
        items.append(
            {
                "answer_id": r["answer_id"],
                "run_id": r["run_id"],
                "question_id": r["question_id"],
                "seq": r["seq"],
                "origin": r["origin"],
                "question": project.store.message(r["q_ref"]) or "",
                "label": r["label"],
                "status": r["status"],
                "ts": r["ts"],
                "in_report": (entry := _report_entry(project, r["run_id"], r["answer_id"]))
                is not None,
                "finding": bool(entry and entry.get("finding")),
            }
        )
    return {"schema": "stringency.present/1", "kind": "answers", "answers": items}


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


STEP_TABLE_HEAD = 20  # rows of an output table `present --step` prints when no view names it


def _step_of(source: str) -> str:
    """The step a view's source lies under: `<step>/<rest>` or `<step>.<output>...`."""
    s = normalise_source(source)
    return s.split("/", 1)[0] if "/" in s else s.split(".", 1)[0]


def present_completed_step(
    project: Site, run_id: str | None, step_id: str, skills_dir: Path | None = None
) -> dict[str, Any]:
    """`present --step <id>` (L134 a): a completed step's outputs and the method's views of
    them, while the run is in any state, a held run included (the evidence a later proposal is
    read from). In order: the method's `step_view` entries for the step; its `hold_view`
    entries whose source lies under the step (none with an `{item}`); the declared decision
    evidence of any step whose source lies under it; and, when none of these shows anything,
    each output itself (a table's first rows, a figure, a file). Defaults to the latest run.
    Refuses a step that is not completed (15). Reads: runs, steps, artifacts, the skill file
    and the step's files. Writes nothing; the CLI records the rendering (`record_rendered`)."""
    if run_id is None:
        row = project.store.one(
            "SELECT run_id FROM runs WHERE kind = 'run' ORDER BY started DESC, rowid DESC LIMIT 1"
        )
        if row is None:
            raise ConfigError("no run to present a step of")
        run_id = str(row["run_id"])
    st = project.store.one(
        "SELECT status FROM steps WHERE run_id = ? AND step_id = ?", (run_id, step_id)
    )
    if st is None:
        raise ConfigError(f"no step {step_id} in run {run_id}")
    if st["status"] != "completed":
        raise ConfigError(
            f"step {step_id} is {st['status']}; present --step renders a completed step"
        )
    payload = present_step(project, run_id, step_id, skills_dir)
    payload["title"] = (
        project.pipeline.title(step_id) if project.pipeline.has_step(step_id) else step_id
    )
    payload["status"] = "completed"
    payload["run_status"] = project.store.scalar(
        "SELECT status FROM runs WHERE run_id = ?", (run_id,)
    )
    shown = {str(s.get("source") or "") for s in payload["sections"]}
    skill, _note = load_skill(project, skills_dir)
    raw = skill.get("hold_view") if skill is not None else None
    views = [
        v
        for v in (raw if isinstance(raw, list) else [])
        if isinstance(v, dict)
        and v.get("source")
        and "{item}" not in str(v["source"])
        and _step_of(str(v["source"]).replace("{step}", step_id)) == step_id
        and str(v["source"]) not in shown
    ]
    if views:
        payload["sections"] += render_items(
            project, run_id, views, None, {"step_id": step_id, "evidence": None}
        )[0]
        shown |= {str(v["source"]) for v in views}
    for sid in project.pipeline.order():
        for name, decl in project.pipeline.step(sid).params.items():
            src = decl.decision.evidence.source if decl.decision is not None else None
            if not src or _step_of(src) != step_id or src in shown:
                continue
            shown.add(src)
            suffix = Path(src).suffix.lower()
            kind = (
                "figure"
                if suffix in IMAGE_SUFFIXES
                else ("table" if suffix in (".csv", ".tsv", ".txt", "") else "text")
            )
            payload["sections"] += render_items(
                project,
                run_id,
                [{"title": f"the evidence for {sid}.{name} ({src})", "source": src, "kind": kind}],
                None,
            )[0]
    arts = project.store.all(
        "SELECT name, kind, path FROM artifacts WHERE run_id = ? AND step_id = ? AND "
        "status = 'produced' ORDER BY rowid",
        (run_id, step_id),
    )
    payload["outputs"] = [{"name": a["name"], "kind": a["kind"], "path": a["path"]} for a in arts]
    if not any("error" not in s for s in payload["sections"]):
        for a in arts:
            payload["sections"].append(_output_section(a, step_id))
    return payload


def _output_section(art: Any, step_id: str) -> dict[str, Any]:
    """One output of a step as `present --step` shows it with no view naming it; its source in
    the skill's form, `<step>/<file>`."""
    path = Path(str(art["path"]))
    title = f"{art['name']} ({path.name})"
    src = f"{step_id}/{path.name}"
    if path.suffix.lower() in IMAGE_SUFFIXES or art["kind"] == "figure":
        return {
            "title": title,
            "kind": "figure",
            "path": str(path),
            "caption": _caption(path),
            "beside": None,
            "beside_caption": None,
            "beside_missing": None,
            "source": src,
        }
    if is_tabular(str(art["kind"]), path) and path.is_file():
        try:
            rows = _rows_from_table(path)
        except (OSError, ValueError) as e:
            return {"title": title, "kind": "table", "error": f"{path.name}: {e}"}
        sec = {
            "title": title,
            "kind": "table",
            "source": src,
            **_table(rows[:STEP_TABLE_HEAD], None, {}),
        }
        if len(rows) > STEP_TABLE_HEAD:
            sec["note"] = f"first {STEP_TABLE_HEAD} of {len(rows)} rows; the file is {path}"
        return sec
    return {"title": title, "kind": "file", "path": str(path), "source": src}


def record_rendered(project: Site, payload: dict[str, Any], verb: str = "present --step") -> int:
    """`present --step` marks the step it rendered (L134 a): one `step_events` row `rendered`
    on that step with `{verb, ts}` and the sources shown, the OS user and the operator session.
    A hold's provenance line reads it ("rendered by present --step at <ts>") and `propose`
    copies the latest ones onto its `proposed` event. Writes: step_events. Returns the seq."""
    import getpass
    import os

    from stringency.clock import now_iso
    from stringency.operator_id import operator_env

    sources: list[str] = []
    for s in payload.get("sections") or []:
        src = s.get("source")
        if src and src not in sources:
            sources.append(str(src))
    return project.store.step_event(
        str(payload["run_id"]),
        str(payload["step_id"]),
        "rendered",
        {
            "verb": verb,
            "ts": now_iso(),
            "sources": sources,
            "user": os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser(),
            "session_ref": operator_env().get("session_ref"),
        },
    )


def rendered_marks(store: Store, run_id: str) -> list[dict[str, Any]]:
    """The latest `rendered` mark of each step of a run, oldest first: `{step_id, verb, ts}`.
    Reads: step_events."""
    rows = store.all(
        "SELECT step_id, payload_json, ts FROM step_events WHERE run_id = ? AND event = 'rendered' "
        "ORDER BY ts, seq",
        (run_id,),
    )
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        p = json.loads(r["payload_json"] or "{}")
        latest[str(r["step_id"])] = {
            "step_id": str(r["step_id"]),
            "verb": p.get("verb"),
            "ts": p.get("ts") or r["ts"],
        }
    return sorted(latest.values(), key=lambda m: str(m["ts"]))


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
{% if s.get("note") %}<p class="note">({{ s.note }})</p>{% endif %}
{% if s.get("error") %}<p class="note">(not shown: {{ s.error }})</p>
{% elif s.kind == "file" %}<p>file to send: <code>{{ s.path }}</code></p>
{% elif s.kind == "text" %}{% if s.get("folded") %}<details><summary>{{ s.folded }}</summary>{% endif %}{% if s.get("markdown") %}{{ md(s) }}{% else %}<pre>{{ s.text.rstrip() }}</pre>{% endif %}{% if s.get("folded") %}</details>{% endif %}
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


def _h(v: object) -> str:
    import html

    return html.escape(str(v), quote=False)


def md_html(text: str, drop_title: str | None = None) -> str:
    """The engine's own markdown (the echo-back, the egress report, a method's prose section)
    as escaped HTML: `#`/`##` headings (h3/h4; a leading heading equal to `drop_title` is
    dropped, the section already carries it), paragraphs, `- ` lists with indented
    continuation lines, `key: value` lines indented under a paragraph as a definition table,
    and fenced code. Nothing else is interpreted; no third-party markdown."""
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    defs: list[tuple[str, str]] = []
    code: list[str] | None = None

    def flush() -> None:
        nonlocal para, items, defs
        if para:
            out.append("<p>" + _h(" ".join(x.strip() for x in para)) + "</p>")
            para = []
        if items:
            out.append("<ul>" + "".join(f"<li>{_h(i)}</li>" for i in items) + "</ul>")
            items = []
        if defs:
            out.append(
                '<table class="defs">'
                + "".join(f"<tr><th>{_h(k)}</th><td>{_h(v)}</td></tr>" for k, v in defs)
                + "</table>"
            )
            defs = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre>" + _h("\n".join(code)) + "</pre>")
                code = None
            else:
                code.append(line)
            continue
        if line.strip().startswith("```"):
            flush()
            code = []
            continue
        if not line.strip():
            flush()
            continue
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            if drop_title and title == drop_title and not out:
                continue
            out.append(f"<h{min(level + 2, 6)}>{_h(title)}</h{min(level + 2, 6)}>")
            continue
        if line.startswith("- "):
            if para:
                flush()
            items.append(line[2:].strip())
            continue
        if line.startswith("  ") and items:
            items[-1] = items[-1] + " " + line.strip()
            continue
        if line.startswith("  ") and ": " in line.strip():
            if para:
                flush()
            k, _, v = line.strip().partition(": ")
            defs.append((k, v))
            continue
        if defs:
            flush()
        para.append(line)
    flush()
    if code is not None:
        out.append("<pre>" + _h("\n".join(code)) + "</pre>")
    return "\n".join(out)


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
        md=lambda s: Markup(md_html(s["text"], s.get("title"))),  # noqa: S704 - escaped by md_html
    )


def render_markdown(payload: dict[str, Any]) -> str:
    out: list[str] = []
    if payload["kind"] == "answer" and payload.get("chat") is not None:
        block = render_chat(payload)
        if not payload["details"]:
            return block
        return block + "\n---\n\n" + render_markdown({**payload, "chat": None})
    if payload["kind"] == "answers":
        if not payload["answers"]:
            return "no answers filed\n"
        for a in payload["answers"]:
            mark = a["label"] or a["status"]
            out.append(
                f"- {a['answer_id']} ({mark}{', finding' if a['finding'] else ''}): "
                f"question {a['seq']} ({a['origin']}): {a['question']}"
            )
        return "\n".join(out) + "\n"
    if payload["kind"] == "answer":
        out.append(f"## Question {payload['seq']}: {payload['question']}")
        out.append("")
        if payload["status"] != "admissible":
            out.append(f"(this answer was {payload['status']} and is not shown as an answer)")
            out.append("")
        out.append(payload["text"].rstrip())
        if payload.get("fit"):
            out.append("")
            out.append(payload["fit"]["line"])
    elif payload["kind"] == "run":
        out.append(f"## {payload['pipeline']}: {payload['progress']}")
    elif payload["kind"] == "step":
        out.append(
            f"## {payload.get('title') or payload['step_id']}: completed"
            + (f" (the run is {payload['run_status']})" if payload.get("run_status") else "")
        )
        if payload.get("outputs"):
            out.append("")
            out.append("Outputs:")
            out += [f"- {o['name']}: {o['path']}" for o in payload["outputs"]]
    else:
        packet = payload.get("packet")
        heading = f": {packet['heading']}" if packet and packet.get("heading") else ""
        out.append(
            f"## Hold {payload['hold_id']} ({payload['hold_kind']}) waits for "
            f"{payload['waits_on']}{heading}"
        )
        out.append("")
        if packet:
            # the packet (L133): the question, the rule with the facts, then (below) the
            # evidence, then what each verdict does
            out.append(f"Question: {packet['question']}")
            out.append("")
            out.append("The rule and the facts:")
            out.extend(f"- {line}" for line in packet["rule"])
            if payload.get("presented"):
                out.append("")
                out.append(f"The evidence: {payload['presented']}.")
        elif payload.get("found"):
            if payload.get("check"):
                out.append(f"What was checked: {payload['check']}")
            out.append(f"What the engine found: {payload['found']}")
            if payload.get("guidance"):
                out.append("")
                out.append("What to check:")
                out.extend(f"- {g}" for g in payload["guidance"])
            if payload.get("compared"):
                out.append("")
                out.append("The numbers it compared:")
                out.append("")
                out.append(
                    markdown_table(
                        ["what", "value"], [[r["name"], r["value"]] for r in payload["compared"]]
                    )
                )
        else:
            out.append(f"The engine recorded: {payload['reason']}")
            if payload.get("evidence"):
                out.append("")
                out.append(f"Evidence: {_fmt(payload['evidence'], None)}")
        if not packet:
            out.append("")
            out.append(
                "To resolve it, in the project directory, with your reason in your own words:"
            )
            out.append("")
            out.append(f"    {payload['review']['accept']}")
            out.append(f"    {payload['review']['reject']}")
    for s in payload["sections"]:
        out.append("")
        out.append(f"### {s['title']}")
        out.append("")
        if s.get("note"):
            out.append(f"({s['note']})")
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
    if payload["kind"] == "hold" and payload.get("packet"):
        out.append("")
        out.append("What each verdict does (in the project directory, your reason in your words):")
        for v in payload["packet"]["verdicts"]:
            out.append(f"- {v['verdict']}: {v['effect']}")
            out.append(f"      {v['command']}")
    if payload["kind"] == "run" and not payload["sections"]:
        out.append("")
        out.append("Deliverables:")
        out += [f"- {p}" for p in payload["deliverables"]] or ["- none"]
    if payload["kind"] == "answer":
        for f in payload.get("figures") or []:
            out.append("")
            out.append(f"### Figure attached: {f['name']}")
            out.append("")
            out.append(f"figure: {f['path']}")
            out.append(str(f.get("label_line") or ""))
        out.append("")
        out.append(payload["label_sentence"] or "")
        out += _settled_lines(payload["decisions"])
    if payload["kind"] == "answer" and payload["details"]:
        out.append("")
        out.append(payload["qualifier"] or "")
        out.append(
            f"Answer {payload['answer_id']} to question {payload['question_id']} "
            f"({payload['origin']}), run {payload['run_id']}."
        )
        if payload["cells"]:
            out.append("")
            out.append("Cells the numbers were checked against:")
            for aid, rows in payload["cells"].items():
                for key, row in rows.items():
                    out.append(f"- {aid}:{key}: " + ", ".join(f"{c}={v}" for c, v in row.items()))
        if payload["decisions"]:
            out.append("")
            out.append("Decisions:")
            out += [
                f"- {d['step']}.{d['param']} = {d['value']} ({d['source']})"
                for d in payload["decisions"]
            ]
    if payload["kind"] == "answer" and payload["report"]:
        e = payload["report"]
        out.append("")
        out.append(f"In the report as {e['file']} ({_finding_words(e)}).")
    if payload["files"] and payload["kind"] != "answer":
        out.append("")
        out.append("Files to send:")
        out += [f"- {p}" for p in payload["files"]]
    if payload["never_show"]:
        out.append("")
        out.append("Not shown, by the method's rule: " + ", ".join(payload["never_show"]) + ".")
    if payload["kind"] != "answer" or payload["details"]:
        out.append("")
        out.append(f"({payload['skill']})")
    return "\n".join(out) + "\n"
