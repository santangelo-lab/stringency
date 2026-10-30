"""Delimited tables as evidence (design 8.3): rows keyed by the row key.

The row key (L138, 2026-10-29) is the shortest prefix of the table's columns whose values,
joined with `|`, are unique over the table: the first column alone where it is unique (every
table keyed before 0.2.35 keeps its keys), `cluster|stratum` for a table stratified after its
first column. A module output may declare its key columns in `module.yml`
(`outputs.<name>.key`), which replaces the prefix rule. Every value of a key is the text as
read, never coerced (L12).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from stringency.exit_codes import ConfigError
from stringency.predicates.context import EvidenceTable

KEY_SEP = "|"

# A cell is a number only when it reads as one plainly: optional sign, no leading zeros, an
# optional decimal part and exponent. `int()` and `float()` also accept underscores
# (`0076570_24` -> 7657024), leading zeros (`0076581` -> 76581), `nan` and `inf`; an id written
# like that stays text (L12, 2026-10-07).
_NUMBER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?P<frac>\.[0-9]+)?(?P<exp>[eE][+-]?[0-9]+)?")


def _coerce(v: str) -> Any:
    m = _NUMBER.fullmatch(v)
    if m is None:
        return v
    if m.group("frac") is None and m.group("exp") is None:
        return int(v)
    return float(v)


TABULAR_SUFFIXES = (".csv", ".tsv", ".tab")


def is_tabular(kind: str, path: str | Path) -> bool:
    """Whether an artifact can be read as a table: kind `table`, or any csv or tsv file whatever
    its kind (a method's own table types such as `punch_table`, open mode 2026-10-20). Cited
    cells and the answer views of kind table come from these."""
    return kind == "table" or Path(path).suffix.lower() in TABULAR_SUFFIXES


def _joined(row: Mapping[str, Any], cols: Sequence[str]) -> str:
    return KEY_SEP.join(str(row.get(c)) for c in cols)


def _numbered(keys: list[str]) -> tuple[list[str], int]:
    """Repeats of a key get `#<n>`, the second occurrence `#2`; returns the keys and how many
    rows were renamed."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
        out.append(k if seen[k] == 1 else f"{k}#{seen[k]}")
    return out, sum(n - 1 for n in seen.values())


def row_keys(
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    declared: Sequence[str] | None = None,
) -> tuple[list[str], list[str], str | None]:
    """(the key columns, each row's key, a note when a key had to be numbered). With `declared`,
    those columns; otherwise the shortest prefix of `columns` whose joined values are unique.
    When no prefix is unique (rows repeated in full) or the declared columns repeat, the key is
    every column (or the declared ones) and a repeat carries `#<n>`."""
    cols = list(columns)
    if declared:
        absent = [c for c in declared if c not in cols]
        if absent:
            raise ConfigError(f"declared key column(s) {', '.join(absent)} not in the table")
        keys, renamed = _numbered([_joined(r, declared) for r in rows])
        note = (
            f"the declared key {KEY_SEP.join(declared)} repeats on {renamed} row(s); "
            "a repeat's key carries #<n>"
            if renamed
            else None
        )
        return list(declared), keys, note
    if not cols:
        return [], [], None
    for i in range(1, len(cols) + 1):
        keys = [_joined(r, cols[:i]) for r in rows]
        if len(set(keys)) == len(keys):
            return cols[:i], keys, None
    keys, renamed = _numbered([_joined(r, cols) for r in rows])
    return cols, keys, f"{renamed} row(s) repeat another row in full; a repeat's key carries #<n>"


def load_table(
    path: Path,
    name: str,
    key_column: str | None = None,
    *,
    key: Sequence[str] | None = None,
) -> EvidenceTable:
    """Rows keyed by the row key, each value of the key exactly as read (never coerced), so a
    citation of the key as rendered cites the row (L12, L138). `key_column` is a judgment's
    `item_key`: that one column, as before, a repeated item id keeping its last row. `key` is
    an output's declared key (`module.yml` `outputs.<name>.key`); without either, the shortest
    unique prefix of the columns."""
    delim = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        columns = tuple(reader.fieldnames or ())
        raw = list(reader)
    note: str | None = None
    if key_column is not None:
        kcols = [key_column]
        keys = [str(r[key_column]) for r in raw]
    else:
        kcols, keys, note = row_keys(columns, raw, key)
    kset = set(kcols)
    rows: dict[str, dict[str, Any]] = {}
    for k, r in zip(keys, raw, strict=True):
        rows[k] = {c: r[c] if c in kset else _coerce(r[c]) for c in columns}
    return EvidenceTable(
        name=name,
        key_column=KEY_SEP.join(kcols),
        columns=columns,
        rows=rows,
        key_columns=tuple(kcols),
        note=note,
    )


def key_form(table: EvidenceTable) -> str:
    """How a row of this table is cited: `<k1>|<k2>` over its key columns."""
    cols = table.key_columns or ((table.key_column,) if table.key_column else ())
    return KEY_SEP.join(f"<{c}>" for c in cols) or "<row>"


def nearest_keys(keys: Sequence[str], miss: str, n: int = 5) -> list[str]:
    """Up to `n` keys sharing the longest prefix with `miss`, in table order among equals."""

    def shared(k: str) -> int:
        i = 0
        while i < min(len(k), len(miss)) and k[i] == miss[i]:
            i += 1
        return i

    ranked = sorted(enumerate(keys), key=lambda ik: (-shared(ik[1]), ik[0]))
    return [k for _, k in ranked[:n]]


def numeric_texts(path: Path) -> list[str]:
    """Every cell of a delimited table, header excluded, that reads plainly as a number, as the
    text written (the delimiter as `load_table` picks it). A drawing exec's `figure_drawn` is
    checked cell by cell against its inputs with these (L140)."""
    delim = "\t" if path.suffix.lower() in {".tsv", ".txt", ".tab"} else ","
    out: list[str] = []
    with open(path, newline="") as f:
        reader = csv.reader(f, delimiter=delim)
        next(reader, None)
        for row in reader:
            out += [v.strip() for v in row if _NUMBER.fullmatch(v.strip())]
    return out


def table_text(path: Path) -> str:
    return path.read_text()
