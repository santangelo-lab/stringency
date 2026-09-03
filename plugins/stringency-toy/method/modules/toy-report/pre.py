#!/usr/bin/env python3
"""report: one paragraph citing two numbers copied from the comparison table, plus group_labels.json.

The prose is produced by code, so every number is copied from a table cell and the engine's
numeric-claims predicate can check it against the `comparison` evidence table.
"""

import csv
import json
import sys

job = json.load(sys.stdin)
with open(job["inputs"]["comparison"], newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))
with open(job["inputs"]["labels"]) as f:
    consensus = json.load(f)

labels = {c["item_id"]: c.get("label") for c in consensus.get("items", [])}
first = next((r for r in rows if r["contrast"] == "A_vs_B"), rows[0])
para = (
    f"Group A ({labels.get('A', 'unlabelled')}) and group B ({labels.get('B', 'unlabelled')}) "
    f"differed by {first['diff']} in mean value (adjusted p = {first['p_adj']}, contrast {first['contrast']})."
)
with open(job["outputs"]["report"], "w") as f:
    f.write("# Toy report\n\n" + para + "\n")
with open(job["outputs"]["group_labels"], "w") as f:
    json.dump({"labels": labels, "source": "consensus"}, f, indent=2, sort_keys=True)
print("params: none")
