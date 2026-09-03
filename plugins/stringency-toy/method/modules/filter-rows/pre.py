#!/usr/bin/env python3
"""filter_rows: keep rows with value >= min_value. Prints the parameter it used to its log."""

import csv
import json
import sys

job = json.load(sys.stdin)
min_value = float(job["params"]["min_value"])
src = job["inputs"]["object"]
dst = job["outputs"]["object"]
with open(src, newline="") as f:
    rows = list(csv.DictReader(f))
kept = [r for r in rows if float(r["value"]) >= min_value]
with open(dst, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(kept)
print(f"params: min_value={min_value:g}")
print(f"kept {len(kept)} of {len(rows)} rows")
