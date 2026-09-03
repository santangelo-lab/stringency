#!/usr/bin/env python3
"""Negative-control generator: permute the `group` column of a frame.

Job JSON on stdin: {"inputs": {"input": path}, "params": {"seed": int, "within": null},
                    "outputs": {"object": path}}
"""

from __future__ import annotations

import csv
import json
import random
import sys


def main() -> int:
    job = json.load(sys.stdin)
    src = job["inputs"]["input"]
    dst = job["outputs"]["object"]
    seed = int(job.get("params", {}).get("seed", 0))
    with open(src, newline="") as f:
        rows = list(csv.DictReader(f))
    groups = [r["group"] for r in rows]
    random.Random(seed).shuffle(groups)
    for r, g in zip(rows, groups, strict=True):
        r["group"] = g
    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"shuffled group column with seed {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
