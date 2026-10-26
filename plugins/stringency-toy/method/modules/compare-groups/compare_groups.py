#!/usr/bin/env python3
"""compare_groups: Welch t-test between every pair of groups at the chosen replication unit.

Output TSV: contrast, n_a, n_b, mean_a, mean_b, diff, p_value, p_adj.
The p-value uses a normal approximation to the t distribution; this is a toy.
"""

import csv
import itertools
import json
import math
import statistics
import sys
from collections import defaultdict

job = json.load(sys.stdin)
unit = job["params"]["replicate_unit"]
correction = job["params"]["correction"]
with open(job["inputs"]["object"], newline="") as f:
    rows = list(csv.DictReader(f))

samples = defaultdict(list)
if unit == "row":
    for r in rows:
        samples[r["group"]].append(float(r["value"]))
else:
    per = defaultdict(list)
    for r in rows:
        per[(r["group"], r["unit"])].append(float(r["value"]))
    for (g, _u), vals in per.items():
        samples[g].append(statistics.fmean(vals))


def welch(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va = statistics.variance(a) if len(a) > 1 else 0.0
    vb = statistics.variance(b) if len(b) > 1 else 0.0
    se = math.sqrt(va / len(a) + vb / len(b)) if (va or vb) else 1e-9
    t = (ma - mb) / se
    p = math.erfc(abs(t) / math.sqrt(2))  # two-sided normal approximation
    return ma, mb, t, min(max(p, 1e-300), 1.0)


results = []
for a, b in itertools.combinations(sorted(samples), 2):
    ma, mb, t, p = welch(samples[a], samples[b])
    results.append([f"{a}_vs_{b}", len(samples[a]), len(samples[b]), ma, mb, ma - mb, p])

ps = [r[6] for r in results]
m = len(ps)
if correction == "bonferroni":
    adj = [min(1.0, p * m) for p in ps]
elif correction == "bh":
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        prev = min(prev, ps[i] * m / rank)
        adj[i] = min(prev, 1.0)
else:
    adj = list(ps)

with open(job["outputs"]["comparison_table"], "w", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    w.writerow(["contrast", "n_a", "n_b", "mean_a", "mean_b", "diff", "p_value", "p_adj"])
    for r, pa in zip(results, adj, strict=True):
        w.writerow(
            [
                r[0],
                r[1],
                r[2],
                f"{r[3]:.2f}",
                f"{r[4]:.2f}",
                f"{r[5]:.2f}",
                f"{r[6]:.3g}",
                f"{pa:.3g}",
            ]
        )
print(f"params: replicate_unit={unit} correction={correction}")
