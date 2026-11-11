"""Names (design 3.1, 2026-11-10, PLAN L163): what a `text:` parameter's value names in the
objects its step reads.

A name is a text parameter whose right value depends only on how this dataset labels its own
contents: a column, a value found in a column, an entry of some other list the object's
summary carries, a naming convention. The engine checks a column and a value against the
summaries the extractors wrote (`fields.columns`, 4.2): the column exists; the value is one of
the column's `levels` when the summary lists them. `text: {listed_in: <key>}` is the same
check against `fields.<key>`, a list the plugin's extractor writes and the engine does not
know by name. A convention (`prefix`) is not checked. Nothing here reads a data object: a name
is resolved against summaries already in the state, so the predicates that call this do no I/O.
"""

from __future__ import annotations

import difflib
import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from stringency.pipelines import UNSET, ParamDecl, Pipeline
from stringency.state import ObjectState

LISTED = 12  # how many columns or levels a message names before it says how many more


@dataclass(frozen=True)
class Resolution:
    """What one name's value resolves to. `status`: `resolved` (the column or value exists),
    `missing` (it names nothing, with the nearest names that exist), `unchecked` (no summary to
    check against, or a kind that is not checked; `why` says which), `empty` (the value is the
    empty string, the method's "none") or `unset`."""

    parameter: str
    kind: str  # column | listed | value | prefix
    value: str
    status: str
    where: str | None = None  # the object that holds the column
    column: str | None = None  # value: the column the value was looked for in
    listed_in: str | None = None  # listed: the key of `fields` the name was looked for under
    detail: dict[str, Any] = field(default_factory=dict)  # dtype, n_unique, levels
    nearest: tuple[str, ...] = ()
    why: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "parameter": self.parameter,
            "kind": self.kind,
            "value": self.value,
            "status": self.status,
        }
        for key in ("where", "column", "listed_in", "why"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        if self.detail:
            out["detail"] = dict(self.detail)
        if self.nearest:
            out["nearest"] = list(self.nearest)
        return out

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> Resolution:
        return cls(
            parameter=str(d.get("parameter", "")),
            kind=str(d.get("kind", "column")),
            value=str(d.get("value", "")),
            status=str(d.get("status", "unchecked")),
            where=d.get("where"),
            column=d.get("column"),
            listed_in=d.get("listed_in"),
            detail=dict(d.get("detail") or {}),
            nearest=tuple(str(x) for x in d.get("nearest") or ()),
            why=d.get("why"),
        )

    def says(self) -> str:
        """One phrase for the echo-back, a hold and a refusal."""
        if self.status == "unset":
            return f"{self.parameter} is unset"
        if self.status == "empty":
            return f"{self.parameter} is empty (none)"
        what = {
            "value": f"a value of {self.column or 'its column'}",
            "prefix": "a naming convention",
            "listed": f"an entry of {self.listed_in or 'a list'}",
        }.get(self.kind, "a column")
        head = f"{self.parameter} = {self.value!r}, {what}"
        if self.status == "resolved":
            where = f" of {self.where}" if self.where and self.kind in ("column", "listed") else ""
            return head + where + _detail_phrase(self.detail)
        if self.status == "missing":
            near = f"; nearest: {', '.join(self.nearest)}" if self.nearest else ""
            return f"{head} that does not exist{near}"
        return f"{head}, not checked ({self.why})"


def _detail_phrase(detail: Mapping[str, Any]) -> str:
    levels = detail.get("levels")
    if isinstance(levels, list) and levels:
        shown = ", ".join(str(x) for x in levels[:LISTED])
        more = f", and {len(levels) - LISTED} more" if len(levels) > LISTED else ""
        return f" ({len(levels)} values: {shown}{more})"
    if detail.get("n_unique") is not None:
        return f" ({detail['n_unique']} distinct values)"
    return ""


def listed_of(obj: ObjectState, key: str) -> dict[str, dict[str, Any]] | None:
    """The entries an object's summary lists under `fields.<key>`, each with what the extractor
    said of it (for a column: `dtype`, `n_unique`, `levels`); a mapping gives its keys, a plain
    list its items. None when the summary carries no such list."""
    entries = obj.fields.get(key)
    if isinstance(entries, dict):
        return {str(k): dict(v) if isinstance(v, dict) else {} for k, v in entries.items()}
    if isinstance(entries, list):
        return {str(c): {} for c in entries}
    return None


def columns_of(obj: ObjectState) -> dict[str, dict[str, Any]] | None:
    """The columns an object's summary lists (`fields.columns`); None when it lists none."""
    return listed_of(obj, "columns")


def objects_read(
    pipeline: Pipeline,
    step_id: str,
    objects: Mapping[str, ObjectState],
    input_names: Iterable[str],
) -> dict[str, ObjectState]:
    """The summaries of what a step reads, nearest first: each project input it binds, each
    upstream output it binds that the state holds a summary of, then the project inputs its
    ancestors bind (a column of the raw object is carried down the pipeline; a column a step
    writes is not a name). Globs expand against the manifest's input names."""
    names = list(input_names)
    out: dict[str, ObjectState] = {}

    def take_inputs(sid: str) -> None:
        for refs in pipeline.step(sid).refs().values():
            for ref in refs:
                if ref.kind != "inputs":
                    continue
                matched = fnmatch.filter(names, ref.name) if ref.pattern else [ref.name]
                for name in matched:
                    if name in objects and name not in out:
                        out[name] = objects[name]

    if not pipeline.has_step(step_id):
        return out
    take_inputs(step_id)
    for refs in pipeline.step(step_id).refs().values():
        for ref in refs:
            if ref.kind == "steps" and ref.output in objects and ref.output not in out:
                out[str(ref.output)] = objects[str(ref.output)]
    order = pipeline.order()
    for sid in sorted(pipeline.ancestors(step_id), key=order.index, reverse=True):
        take_inputs(sid)
    return out


def _nearest(value: str, among: Iterable[str]) -> tuple[str, ...]:
    pool = sorted({str(a) for a in among})
    close = difflib.get_close_matches(value, pool, n=3, cutoff=0.5)
    lowered = [a for a in pool if a.lower() == value.lower() and a not in close]
    return tuple(lowered + close) or tuple(pool[:LISTED])


def resolve(
    parameter: str,
    decl: ParamDecl,
    value: Any,
    values: Mapping[str, Any],
    read: Mapping[str, ObjectState],
) -> Resolution:
    """Resolve one name against the summaries of what its step reads. `values` is the step's
    whole parameter set, for a `value_of` name's column. Pure."""
    kind = decl.name_kind or "column"
    text = "" if value is None else str(value)
    if text == UNSET:
        return Resolution(parameter, kind, text, "unset")
    if text == "":
        return Resolution(parameter, kind, text, "empty")
    if kind == "prefix":
        return Resolution(
            parameter,
            kind,
            text,
            "unchecked",
            why="a naming convention is not checked against the object",
        )
    if kind in ("column", "listed"):
        key = decl.listed_in or "columns"
        named = key if kind == "listed" else None
        found = {
            name: got for name, obj in read.items() if (got := listed_of(obj, key)) is not None
        }
        if not found:
            return Resolution(
                parameter,
                kind,
                text,
                "unchecked",
                listed_in=named,
                why=(
                    "no object this step reads has its columns summarised"
                    if kind == "column"
                    else f"no object this step reads lists `{key}` in its summary"
                ),
            )
        for name, got in found.items():
            if text in got:
                return Resolution(
                    parameter,
                    kind,
                    text,
                    "resolved",
                    where=name,
                    listed_in=named,
                    detail=got[text],
                )
        return Resolution(
            parameter,
            kind,
            text,
            "missing",
            listed_in=named,
            nearest=_nearest(text, [c for got in found.values() for c in got]),
        )
    listed = {name: cols for name, obj in read.items() if (cols := columns_of(obj)) is not None}
    column = str(values.get(decl.value_of or "", "") or "")
    if column in ("", UNSET):
        return Resolution(
            parameter, kind, text, "unchecked", column=column or None, why="its column is not named"
        )
    for name, cols in listed.items():
        if column not in cols:
            continue
        levels = cols[column].get("levels")
        if not isinstance(levels, list):
            return Resolution(
                parameter,
                kind,
                text,
                "unchecked",
                where=name,
                column=column,
                why="the summary does not list the column's values",
            )
        have = {str(x) for x in levels}
        parts = [text] if text in have else [p.strip() for p in text.split(",") if p.strip()]
        gone = [p for p in parts if p not in have]
        if not gone:
            return Resolution(parameter, kind, text, "resolved", where=name, column=column)
        return Resolution(
            parameter,
            kind,
            text,
            "missing",
            where=name,
            column=column,
            detail={"missing": gone},
            nearest=tuple(dict.fromkeys(n for g in gone for n in _nearest(g, have))),
        )
    return Resolution(
        parameter,
        kind,
        text,
        "unchecked",
        column=column,
        why="its column is not in any summarised object",
    )


def resolve_step(
    pipeline: Pipeline,
    step_id: str,
    values: Mapping[str, Any],
    objects: Mapping[str, ObjectState],
    input_names: Iterable[str],
    only: Iterable[str] | None = None,
) -> list[Resolution]:
    """Every name of a step (or `only` those parameters) resolved against what the step reads,
    in the pipeline's order. `values` holds the step's parameter values; a name absent from it
    is read at its default."""
    if not pipeline.has_step(step_id):
        return []
    step = pipeline.step(step_id)
    wanted = set(only) if only is not None else None
    read = objects_read(pipeline, step_id, objects, input_names)
    merged = {**step.defaults(), **dict(values)}
    return [
        resolve(name, decl, merged.get(name), merged, read)
        for name, decl in step.params.items()
        if decl.is_name and (wanted is None or name in wanted)
    ]


def echo_lines(
    pipeline: Pipeline,
    declared: Mapping[str, Mapping[str, Any]],
    objects: Mapping[str, ObjectState],
    input_names: Iterable[str],
) -> list[str]:
    """The echo-back's lines on names (design 2.7): per step that declares any, what each
    name's value resolves to in the inputs and who set it (the declaration or the pipeline's
    default), and what the run will do about a name that is unset or names nothing. Empty for
    a pipeline with no names."""
    names = list(input_names)
    lines: list[str] = []
    for sid in pipeline.order():
        given = declared.get(sid) or {}
        parts: list[str] = []
        waits: list[str] = []
        for r in resolve_step(pipeline, sid, given, objects, names):
            who = "declared" if r.parameter in given else "the pipeline's default"
            parts.append(f"{r.says()} ({who})")
            if r.status == "unset":
                waits.append(f"{r.parameter} is unset, so the run stops there for a proposal")
            elif r.status == "missing":
                waits.append(f"{r.parameter} names nothing, so the step will be blocked")
        if parts:
            line = f"Names in step {sid}: " + "; ".join(parts) + "."
            if waits:
                line += " Unless declared here: " + "; ".join(waits) + "."
            lines.append(line)
    return lines
