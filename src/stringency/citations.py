"""Citations on a proposal (`propose --cite`, backlog L55): a source in the delivery skill's
path form with an optional row and column, resolved against the run's files so the pre-gate and
the hold see the cell's value. Reads the run's output files through `present._resolve`; writes
nothing."""

from __future__ import annotations

from typing import Any

from stringency.exit_codes import ConfigError
from stringency.pipelines import normalise_source


def parse_cite(text: str) -> dict[str, Any]:
    """`<source>[:<row>[:<column>]]`: the source is `<step>/<output>[/<file>]` or
    `$inputs.<name>[/<file>]` (`<step>.<output>` accepted), the row is the row's key (its key
    columns' values joined with `|`, L138; the first column's value where that is unique), the
    column a column name."""
    parts = text.strip().split(":")
    if not parts or not parts[0]:
        raise ConfigError(f"--cite {text!r}: a source is required")
    if len(parts) > 3:
        raise ConfigError(f"--cite {text!r}: at most <source>:<row>:<column>")
    return {
        "source": normalise_source(parts[0]),
        "row": parts[1] if len(parts) > 1 and parts[1] != "" else None,
        "column": parts[2] if len(parts) > 2 and parts[2] != "" else None,
    }


def resolve_cites(rc: Any, cites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each citation with what it resolves to: `value` (the cell, or the row as `{column:
    value}` when no column was named, or the file's existence), or `missing` saying why not.
    A row is matched on the table's row key (`tables.row_keys`: the output's declared key, else
    the shortest unique prefix of the columns, L138), then on any column named `item`, `id`,
    `key`, `name` or `parameter`, then on the row's position (1-based)."""
    from stringency.present import Site, _resolve, _rows_from_table
    from stringency.tables import is_tabular

    site = Site(
        root=rc.project.root, config=rc.project.config, store=rc.store, pipeline=rc.pipeline
    )
    out: list[dict[str, Any]] = []
    for c in cites:
        entry: dict[str, Any] = dict(c)
        path = _resolve(site, rc.run_id, c["source"], None)
        if path is None:
            entry["missing"] = "no such file for this run"
            out.append(entry)
            continue
        entry["path"] = str(path)
        if path.suffix.lower() == ".json" and (
            c.get("row") is not None or c.get("column") is not None
        ):
            # a JSON object of named facts (a method's `analysis_summary`, 2026-10-22): the row
            # is the key, dotted for nesting; `src::key` (no row) reads the column as the key
            entry.update(_json_cell(path, c.get("row"), c.get("column")))
            out.append(entry)
            continue
        if c.get("row") is None:
            entry["value"] = "file present"
            out.append(entry)
            continue
        if not is_tabular("", path):
            entry["missing"] = "not a table; a row was cited"
            out.append(entry)
            continue
        try:
            rows = _rows_from_table(path)
        except (OSError, ValueError, ConfigError) as e:
            entry["missing"] = f"unreadable: {e}"
            out.append(entry)
            continue
        declared = _declared_key(rc, c["source"])
        row = _find_row(rows, str(c["row"]), declared)
        if row is None:
            entry["missing"] = f"no row {c['row']}{_form_hint(rows, declared)}"
            out.append(entry)
            continue
        if c.get("column") is None:
            entry["value"] = dict(row)
        elif c["column"] in row:
            entry["value"] = row[c["column"]]
        else:
            entry["missing"] = f"no column {c['column']}"
        out.append(entry)
    return out


def _json_cell(path: Any, row: Any, column: Any) -> dict[str, Any]:
    """`{"value": ...}` or `{"missing": ...}` for a key of a JSON file. An object: the key
    (`row`, else `column`) walks dotted parts; a column under an object-valued key reads that
    field. A list of objects: the row is found as in a table."""
    import json as _json

    try:
        node: Any = _json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return {"missing": f"unreadable: {e}"}
    if isinstance(node, list):
        rows = [r for r in node if isinstance(r, dict)]
        if row is None:
            return {"missing": "a list of rows; a row is needed"}
        found = _find_row(rows, str(row))
        if found is None:
            return {"missing": f"no row {row}"}
        if column is None:
            return {"value": dict(found)}
        return {"value": found[column]} if column in found else {"missing": f"no column {column}"}
    if not isinstance(node, dict):
        return {"missing": "not an object"}
    key = str(row) if row is not None else str(column)
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return {"missing": f"no key {key}"}
        node = node[part]
    if row is not None and column is not None:
        if isinstance(node, dict) and column in node:
            return {"value": node[column]}
        return {"missing": f"no key {key}.{column}"}
    return {"value": node}


def _declared_key(rc: Any, source: str) -> list[str] | None:
    """The key a step's module declares for the cited output (`<step>/<output>`), if any."""
    step, _, rest = source.partition("/")
    if step.startswith("$") or not rest:
        return None
    try:
        spec = rc.module_for(step).manifest.outputs.get(rest.split("/")[0])
    except Exception:  # noqa: BLE001  (an unknown step resolves by the prefix rule)
        return None
    return list(spec.key) if spec is not None and spec.key else None


def _form_hint(rows: list[dict[str, Any]], declared: list[str] | None) -> str:
    """` (rows are cited as <k1>|<k2>)` for a table whose key has more than one column."""
    from stringency.tables import KEY_SEP, row_keys

    if not rows:
        return ""
    try:
        kcols, _, _ = row_keys(list(rows[0]), rows, declared)
    except ConfigError:
        kcols, _, _ = row_keys(list(rows[0]), rows)
    if len(kcols) < 2:
        return ""
    return " (rows are cited as " + KEY_SEP.join(f"<{c}>" for c in kcols) + ")"


def _find_row(
    rows: list[dict[str, Any]], key: str, declared: list[str] | None = None
) -> dict[str, Any] | None:
    from stringency.tables import row_keys

    if not rows:
        return None
    try:
        kcols, keys, _ = row_keys(list(rows[0]), rows, declared)
    except ConfigError:
        kcols, keys, _ = row_keys(list(rows[0]), rows)
    for k, r in zip(keys, rows, strict=True):
        if k == key:
            return r
    if len(kcols) > 1 and any(str(r.get(kcols[0])) == key for r in rows):
        return None  # a part of a composite key names several rows, never one by position
    for col in ("item", "item_id", "id", "key", "name", "parameter"):
        if col in rows[0]:
            for r in rows:
                if str(r.get(col)) == key:
                    return r
    if key.isdigit() and 1 <= int(key) <= len(rows):
        return rows[int(key) - 1]
    return None


def cited_values(cited: list[dict[str, Any]]) -> list[Any]:
    """Every cell value the citations resolved to (a whole cited row contributes each cell)."""
    out: list[Any] = []
    for c in cited:
        v = c.get("value")
        if isinstance(v, dict):
            out.extend(v.values())
        elif v is not None and v != "file present":
            out.append(v)
    return out


def summary_line(cited: list[dict[str, Any]], considered: list[Any], sources: list[str]) -> str:
    """The sentence a hold opens with (L55): what kind of proposal this is. `sources` are the
    decision's evidence sources the proposal was expected to cite."""
    parts: list[str] = []
    if sources:
        for src in sources:
            n = sum(1 for c in cited if c.get("source") == src and "missing" not in c)
            parts.append(
                f"cites nothing from `{src}`" if n == 0 else f"cites {n} cell(s) of `{src}`"
            )
    elif cited:
        parts.append(f"cites {len(cited)} cell(s)")
    else:
        parts.append("cites nothing")
    if considered:
        parts.append("considered " + ", ".join(str(v) for v in considered))
    return "; ".join(parts)
