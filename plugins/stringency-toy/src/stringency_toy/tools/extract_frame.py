#!/usr/bin/env python3
"""State extractor for object type `frame` (design 4.2). Stdlib only.

usage: extract_frame.py <frame.csv> <design.json>
Prints the envelope: extractor, type, n_obs, fields, counts_per_group, domain.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict


def dtype(values: list[str]) -> str:
    try:
        for v in values:
            if v != "":
                float(v)
        return "number"
    except ValueError:
        return "string"


def main(argv: list[str]) -> int:
    path, design_path = argv[1], argv[2]
    with open(design_path) as f:
        design = json.load(f)
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    columns = list(rows[0].keys()) if rows else []
    fields = {
        c: {"dtype": dtype([r[c] for r in rows]), "n_unique": len({r[c] for r in rows})}
        for c in columns
    }
    units = design.get("units", {})
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for fname, fac in design.get("factors", {}).items():
        col = fac["column"]
        per_level: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for i, r in enumerate(rows):
            if col not in r:
                continue
            lvl = r[col]
            for ucol in units.values():
                key = r.get(ucol, str(i)) if ucol in r else str(i)
                per_level[lvl][ucol].add(key)
        counts[fname] = {
            lvl: {ucol: len(keys) for ucol, keys in d.items()} for lvl, d in per_level.items()
        }
        for lvl in fac.get("levels", []):
            counts[fname].setdefault(lvl, {ucol: 0 for ucol in units.values()})
    out = {
        "extractor": "toy.frame@1",
        "type": "frame",
        "n_obs": len(rows),
        "fields": {"columns": fields},
        "counts_per_group": counts,
        "domain": {},
    }
    json.dump(out, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
