#!/usr/bin/env python3
"""plot_groups: a bar per contrast of the comparison table's `diff`, drawn as SVG with the
standard library only (a tool for questions; open mode)."""

import csv
import json
import sys

job = json.load(sys.stdin)
with open(job["inputs"]["comparison"], newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

width, bar_h, left, gap = 480, 24, 120, 8
height = 40 + len(rows) * (bar_h + gap)
diffs = [float(r["diff"]) for r in rows] or [0.0]
scale = (width - left - 40) / max(abs(d) for d in diffs) / 2 if any(diffs) else 1.0
zero_x = left + (width - left - 40) / 2
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
    f'font-family="sans-serif" font-size="12">',
    f'<line x1="{zero_x:.1f}" y1="20" x2="{zero_x:.1f}" y2="{height - 10}" stroke="#888"/>',
]
for i, (r, d) in enumerate(zip(rows, diffs, strict=True)):
    y = 30 + i * (bar_h + gap)
    x = zero_x if d >= 0 else zero_x + d * scale
    parts.append(f'<text x="8" y="{y + 16}">{r["contrast"]}</text>')
    parts.append(
        f'<rect x="{x:.1f}" y="{y}" width="{abs(d) * scale:.1f}" height="{bar_h}" fill="#4a6fa5"/>'
    )
    parts.append(f'<text x="{width - 36}" y="{y + 16}">{d:.2f}</text>')
parts.append("</svg>")
with open(job["outputs"]["figure"], "w") as f:
    f.write("\n".join(parts) + "\n")
print(f"drew {len(rows)} contrast(s)")
