"""Delimited tables as evidence (design 8.3): rows keyed by an item column."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from stringency.predicates.context import EvidenceTable


def _coerce(v: str) -> Any:
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def load_table(path: Path, name: str, key_column: str | None = None) -> EvidenceTable:
    delim = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        columns = tuple(reader.fieldnames or ())
        key = key_column or (columns[0] if columns else "")
        rows: dict[str, dict[str, Any]] = {}
        for r in reader:
            rows[str(r[key])] = {c: _coerce(r[c]) for c in columns}
    return EvidenceTable(name=name, key_column=key, columns=columns, rows=rows)


def table_text(path: Path) -> str:
    return path.read_text()
