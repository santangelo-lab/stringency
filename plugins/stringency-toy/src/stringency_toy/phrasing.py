"""Domain wording: `describe(action)` for the methods paragraph, `echo` for init."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.actions import Action
from stringency.config import Design, InputsManifest, Objective


def describe(action: Action) -> str:
    p = action.parameters
    op = action.operation
    if op == "filter_rows":
        return f"rows with value below {p.get('min_value')} were removed (step {action.step_id})"
    if op == "summarize_groups":
        return f"per-group summary statistics were computed (step {action.step_id})"
    if op == "label_groups":
        return "groups were labelled by a language model shown the summary table and constrained to a declared vocabulary"
    if op == "compare_groups":
        return (
            f"groups were compared with a Welch t-test using {p.get('replicate_unit')} as the "
            f"replication unit and {p.get('correction')} correction (step {action.step_id})"
        )
    if op == "report":
        return f"a report was generated from the comparison table and the group labels (step {action.step_id})"
    return f"{op} was run (step {action.step_id})"


def echo(
    design: Design, objective: Objective, inputs: InputsManifest, counts: Mapping[str, Any]
) -> str:
    """`counts` is the extractor output for each object input, by input name."""
    parts: list[str] = []
    for name, summary in counts.items():
        if not isinstance(summary, dict):
            continue
        n = summary.get("n_obs")
        cpg = summary.get("counts_per_group", {})
        factor = next(iter(design.factors), None)
        if factor and factor in cpg:
            levels = cpg[factor]
            n_units = sum(int(v.get(design.units.get("sample", ""), 0)) for v in levels.values())
            parts.append(f"{n} rows in {n_units} units across {len(levels)} groups (input {name})")
        elif n is not None:
            parts.append(f"{n} rows (input {name})")
    rep = design.replication_unit or "unset"
    parts.append(f"the replicate is the {rep}")
    for c in objective.contrasts:
        parts.append(f"the question is {c[1]} versus {c[2]}")
    return "; ".join(parts) + "."
