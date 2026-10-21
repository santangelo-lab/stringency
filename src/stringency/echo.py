"""Plain-language echo-back of design, objective, and inputs (design 2.7).

The engine renders the structure; the plugin supplies domain phrasing through `echo`.
The text is bound to the hashes of the three files, and the init `confirm` hold carries it.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from typing import Any

from stringency.config import Design, InputsManifest, Objective
from stringency.modules import Module
from stringency.plugins import Plugin

# The switch paragraph (open_mode_plan.md 1, "The pinned sentences"; owner's decision 4,
# 2026-10-16): the confirm echo of an open project is this paragraph and the bound delivery.
# The operator says it as written and relays the person's yes with `--attest`. Held identical to
# the operator skill's copy by a test.
OPEN_SWITCH = (
    "Your results are delivered. You can ask questions of them here. Nothing you ask is "
    "declared in advance and nothing here is a pre-registered result. Some questions I answer "
    "with tools shipped with this method, which are tested; some with code written in this "
    "session, which is not; the engine labels each answer trusted or untested from what ran, "
    "counts every run of the same tool on the same data, and nothing you ask changes the "
    "delivered files. Shall I open it for questions?"
)


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
    if objective.params:
        parts = [
            f"{sid}: " + ", ".join(f"{k} = {v}" for k, v in vals.items())
            for sid, vals in objective.params.items()
        ]
        lines.append(
            "Parameters declared, taken as given when the step runs and not proposed by the "
            "agent: " + "; ".join(parts) + "."
        )
    if design.holdout:
        lines.append(f"{len(design.holdout)} held-out fixture(s) no run may touch.")
    return "\n".join(lines)


WIDTH = 100


def wrap_text(text: str, width: int = WIDTH) -> str:
    """Wrap each paragraph line at `width` columns; lines that are already short, blank, or
    indented (the bound digests) are left as they are (Lane A item 5, 2026-09-23)."""
    out: list[str] = []
    for line in text.splitlines():
        if len(line) <= width or not line.strip() or line.startswith((" ", "\t", "#")):
            out.append(line)
        else:
            out.extend(
                textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False)
            )
    return "\n".join(out)


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
    head = (
        "This is the engine's reading of the declarations. Accept it with `stringency review`"
        " only if it matches the experiment."
    )
    return f"# Echo-back\n\n{wrap_text(head)}\n\n{wrap_text(text)}\n\nBound to:\n{bound}\n"


def render_inherited_echo(
    objective: Objective,
    inputs: InputsManifest,
    hashes: Mapping[str, str],
    inherited: Mapping[str, Any],
    pipeline: str,
    plugin: Any = None,
    design: Any = None,
) -> str:
    """The echo-back of a project whose confirmation is inherited (design 2.7, added
    2026-09-23; the rules of confirm once, 2026-10-21): the rule and the acceptance it rests
    on, then what is new. Under the `derived` and `inputs matched` rules every input's
    provenance was accepted upstream and only the new facts are shown; under `re-declared` and
    `study` the inputs are listed in full, raw ones named as such, since the acceptance covers
    the design and not these files (an input the owner has never seen is a fact the echo
    states, not a reason to re-ask about the design)."""
    ups = list(inherited.get("upstreams", []))
    rule = str(inherited.get("rule", "derived"))
    matched = dict(inherited.get("matched") or {})
    lines: list[str] = []
    for u in ups:
        lines.append(
            f"Design accepted by rule `{rule}` from {u['project']}: echo-back accepted by "
            f"{u['reviewer']} on {str(u['ts'])[:10]} (hold {u['hold_id']}, review {u['review_id']})."
        )
    lines.append(f"Pipeline: {pipeline}.")
    lines.append(contrast_sentence(objective).capitalize() + ".")
    if objective.deliverables:
        lines.append(f"Deliverables: {', '.join(objective.deliverables)}.")
    for i in inputs.items:
        d = i.derived_from
        if d is not None:
            where = f" (step {d.step_id}, output {d.output})" if d.step_id else ""
            lines.append(f"Input {i.name} ({i.type}) is run {d.run_id}{where} of {d.project}.")
        elif rule in ("inputs matched",):
            lines.append(f"Input {i.name} ({i.type}) is raw, {matched.get(i.name, 'unmatched')}.")
        elif rule in ("re-declared", "study"):
            role = "a reference" if i.role == "reference" else "raw"
            lines.append(
                f"Input {i.name} ({i.type}) is {role}: {i.path}, blake3 {i.blake3[:12]}; the "
                "accepted design does not cover this file."
            )
    bound = "\n".join(f"  {k}: {v}" for k, v in sorted(hashes.items()))
    return (
        "# Echo-back (confirmation inherited)\n\n"
        + wrap_text(_INHERITED_HEAD[rule if rule in _INHERITED_HEAD else "derived"])
        + "\n\n"
        + wrap_text("\n".join(lines))
        + f"\n\nBound to:\n{bound}\n"
    )


_INHERITED_HEAD = {
    "derived": (
        "Every input is a delivered artifact of a project this owner already confirmed, with "
        "the same design and the same method major version, so no new acceptance is asked. "
        "This is what is new here."
    ),
    "inputs matched": (
        "Every input is a delivered artifact of a project this owner already confirmed, or a "
        "file one of those projects bound under the same name, type and hash, or a reference, "
        "with the same design and the same method major version, so no new acceptance is "
        "asked. This is what is new here."
    ),
    "re-declared": (
        "These declaration files are byte for byte the ones this owner already confirmed in a "
        "sibling project, on the same method, so no new acceptance is asked. This is what the "
        "project binds."
    ),
    "study": (
        "This design is the one this owner already confirmed for this study, on the same "
        "method, so no new acceptance is asked of the design. The inputs are listed in full: "
        "the acceptance covers the design, not these files."
    ),
}


def render_open_echo(
    objective: Objective,
    inputs: InputsManifest,
    hashes: Mapping[str, str],
    tools: list[Module],
) -> str:
    """The echo-back of an open project (open_mode_plan.md 1 and 2.1, 2026-10-16): the switch
    paragraph, then the bound delivery (the upstream run and project, the files by name and
    type) and the tools the method ships, then the hashes the accept is bound to."""
    lines = open_echo_lines(objective, inputs, tools)
    bound = "\n".join(f"  {k}: {v}" for k, v in sorted(hashes.items()))
    return (
        "# Echo-back (open mode)\n\n"
        + wrap_text(OPEN_SWITCH)
        + "\n\n"
        + wrap_text("\n".join(lines))
        + f"\n\nBound to:\n{bound}\n"
    )


def open_echo_lines(objective: Objective, inputs: InputsManifest, tools: list[Module]) -> list[str]:
    """What an open project is bound to, without the switch paragraph: the delivery, the
    upstream pipeline's own inputs, other inputs, the upstream question and the tools. The
    echo-back says it after the switch; the open summary's "What was analyzed" is it."""
    lines: list[str] = []
    runs: dict[tuple[str, str], list[str]] = {}
    raw: list[str] = []
    before: dict[str, list[str]] = {}
    for i in inputs.items:
        if i.upstream_input is not None:
            before.setdefault(i.upstream_input.project, []).append(
                f"{i.upstream_input.input} ({i.type}) as {i.name}"
            )
            continue
        d = i.derived_from
        if d is None:
            raw.append(f"{i.name} ({i.type})")
            continue
        runs.setdefault((d.run_id, d.project or "an unrecorded project"), []).append(
            f"{i.name} ({i.type}, step {d.step_id}, output {d.output})"
        )
    for (run_id, project), files in runs.items():
        lines.append(f"Delivery bound: run {run_id} of {project}: " + "; ".join(files) + ".")
    for project, names in before.items():
        lines.append(
            f"The pipeline's own inputs, read-only, from before it ran: {'; '.join(names)} of "
            f"{project}."
        )
    if raw:
        lines.append("Inputs that are not a delivery: " + ", ".join(raw) + ".")
    lines.append(f"The upstream project asked {objective.question}.")
    if tools:
        lines.append(
            "Tools shipped with the method: "
            + ", ".join(f"{m.manifest.name} ({m.manifest.operation})" for m in tools)
            + "."
        )
    return lines
