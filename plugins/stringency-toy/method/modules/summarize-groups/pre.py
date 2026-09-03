#!/usr/bin/env python3
"""summarize_groups: one TSV row per group: group, n_rows, n_units, mean_value, sd_value, top_unit."""

import csv
import json
import statistics
import sys
from collections import defaultdict

job = json.load(sys.stdin)
with open(job["inputs"]["object"], newline="") as f:
    rows = list(csv.DictReader(f))
by_group = defaultdict(list)
for r in rows:
    by_group[r["group"]].append(r)
with open(job["outputs"]["table"], "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["group", "n_rows", "n_units", "mean_value", "sd_value", "top_unit"])
    for g in sorted(by_group):
        rs = by_group[g]
        vals = [float(r["value"]) for r in rs]
        per_unit = defaultdict(float)
        for r in rs:
            per_unit[r["unit"]] += float(r["value"])
        top = max(per_unit, key=lambda u: (per_unit[u], u))
        sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        w.writerow(
            [
                g,
                len(rs),
                len({r["unit"] for r in rs}),
                f"{statistics.fmean(vals):.2f}",
                f"{sd:.2f}",
                top,
            ]
        )
print("params: none")
