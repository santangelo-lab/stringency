"""Plain-language echo-back of design, objective, and inputs (design 2.7).

The engine renders the structure; the plugin supplies domain phrasing through `echo`.
The text is bound to the hashes of the three files, and the init `confirm` hold carries it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from stringency.config import Design, InputsManifest, Objective
from stringency.plugins import Plugin


def contrast_sentence(objective: Objective) -> str:
    parts = [f"{c[1]} versus {c[2]} on {c[0]}" for c in objective.contrasts]
    if not parts:
        return f"the question is {objective.question} with no contrast declared"
    s = f"the question is {objective.question}: " + "; ".join(parts)
    if objective.min_n_per_group:
        n = objective.min_n_per_group
        unit = objective.replication_unit or "replicate"
        s += f", with at least {n} {unit}{'' if n == 1 else 's'} per group"
    return s


def generic_echo(
    design: Design, objective: Objective, inputs: InputsManifest, counts: Mapping[str, Any]
) -> str:
    lines: list[str] = []
    names = ", ".join(f"{i.name} ({i.type})" for i in inputs.items)
    lines.append(f"Inputs: {names}.")
    if design.units:
        units = "; ".join(f"the {k} is {v}" for k, v in design.units.items())
        lines.append(f"Units: {units}.")
    for fname, f in design.factors.items():
        lines.append(f"Factor {fname} (column {f.column}) has levels {', '.join(f.levels)}.")
    if design.batch:
        lines.append(f"Batch variables: {', '.join(design.batch)}.")
    if design.replication_unit:
        lines.append(f"The biological replicate is {design.replication_unit}.")
    lines.append(contrast_sentence(objective).capitalize() + ".")
    if objective.deliverables:
        lines.append(f"Deliverables: {', '.join(objective.deliverables)}.")
    if design.holdout:
        lines.append(f"{len(design.holdout)} held-out fixture(s) no run may touch.")
    return "\n".join(lines)


def render_echo(
    plugin: Plugin,
    design: Design,
    objective: Objective,
    inputs: InputsManifest,
    counts: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> str:
    domain = plugin.echo(design, objective, inputs, counts).strip()
    body = generic_echo(design, objective, inputs, counts)
    text = domain + "\n\n" + body if domain else body
    bound = "\n".join(f"  {k}: {v}" for k, v in sorted(hashes.items()))
    return (
        "# Echo-back\n\n"
        "This is the engine's reading of the declarations. Accept it with `stringency review`"
        " only if it matches the experiment.\n\n"
        f"{text}\n\nBound to:\n{bound}\n"
    )
