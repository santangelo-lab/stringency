"""Delimited tables as evidence (design 8.3): rows keyed by an item column."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from stringency.predicates.context import EvidenceTable

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


def load_table(path: Path, name: str, key_column: str | None = None) -> EvidenceTable:
    """Rows keyed by the key column's text exactly as read; the key cell is never coerced, so
    a reviewer who cites the key as rendered cites the row's key (L12)."""
    delim = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        columns = tuple(reader.fieldnames or ())
        key = key_column or (columns[0] if columns else "")
        rows: dict[str, dict[str, Any]] = {}
        for r in reader:
            rows[str(r[key])] = {c: r[c] if c == key else _coerce(r[c]) for c in columns}
    return EvidenceTable(name=name, key_column=key, columns=columns, rows=rows)


def table_text(path: Path) -> str:
    return path.read_text()
