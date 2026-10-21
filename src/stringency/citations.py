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
    `$inputs.<name>[/<file>]` (`<step>.<output>` accepted), the row is the value of the table's
    first column, the column a column name."""
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
    A row is matched on the table's first column, then on any column named `item`, `id`,
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
        row = _find_row(rows, str(c["row"]))
        if row is None:
            entry["missing"] = f"no row {c['row']}"
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


def _find_row(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not rows:
        return None
    first = next(iter(rows[0]))
    for r in rows:
        if str(r.get(first)) == key:
            return r
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
