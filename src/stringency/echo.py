"""Plain-language echo-back of design, objective, and inputs (design 2.7).

The engine renders the structure; the plugin supplies domain phrasing through `echo`.
The text is bound to the hashes of the three files, and the init `confirm` hold carries it.
"""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

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
    method_root: Path | None = None,
) -> str:
    """The echo-back of an open project (open_mode_plan.md 1 and 2.1, 2026-10-16; L137,
    2026-10-29): the switch paragraph, then the bound delivery grouped by step (each file's name,
    type and the delivering pipeline's own words for it), the upstream input on one line, the
    upstream question, the tools as a count and their names, then the hashes the accept is bound
    to."""
    lines = open_echo_lines(objective, inputs, tools, method_root)
    bound = "\n".join(f"  {k}: {v}" for k, v in sorted(hashes.items()))
    return (
        "# Echo-back (open mode)\n\n"
        + wrap_text(OPEN_SWITCH)
        + "\n\n"
        + "\n".join(lines)
        + f"\n\nBound to:\n{bound}\n"
    )


def _upstream_pipeline(project: str | None) -> str | None:
    """The pipeline an upstream project ran, from its `stringency.yml`; None when unreadable."""
    if not project:
        return None
    try:
        data = yaml.safe_load((Path(project) / "stringency.yml").read_text())
    except (OSError, yaml.YAMLError):
        return None
    pipe = data.get("pipeline") if isinstance(data, dict) else None
    return str(pipe) if pipe else None


def pipeline_deliverables(pipeline: str | None, roots: list[Path]) -> dict[str, str]:
    """The delivering pipeline's own words for its outputs: `deliverables:` in
    `skills/<pipeline>.analyze.yml` (spec/method-skills.md), from the first method root that
    has the file. Empty when no file says it."""
    if not pipeline:
        return {}
    for root in roots:
        f = root / "skills" / f"{pipeline}.analyze.yml"
        if not f.is_file():
            continue
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError:
            return {}
        d = data.get("deliverables") if isinstance(data, dict) else None
        if isinstance(d, dict):
            return {str(k): " ".join(str(v).split()) for k, v in d.items() if v}
        return {}
    return {}


def bound_structure(
    objective: Objective,
    inputs: InputsManifest,
    tools: list[str],
    method_root: Path | None = None,
) -> dict[str, Any]:
    """What an open project is bound to, as rows (L137): `deliveries`, one per upstream run,
    each with `rows` of `{name, type, step, output, what, twice}` in the declarations' order
    (`what` is the delivering pipeline's own words for the output, `twice` the other steps the
    same output name ships from); `upstream_inputs` `{name, type, input, project}`; `raw`
    `{name, type}`; the upstream `question`; the `tools` by name. The confirm hold carries it in
    `context_json.bound`, so the console reads rows instead of the echo file's paragraphs.
    Reads the upstream projects' `stringency.yml` and the analyze files; writes nothing."""
    runs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    pipelines: dict[tuple[str, str], str | None] = {}
    upstream: list[dict[str, str]] = []
    raw: list[dict[str, str]] = []
    for i in inputs.items:
        if i.upstream_input is not None:
            upstream.append(
                {
                    "name": i.name,
                    "type": i.type,
                    "input": i.upstream_input.input,
                    "project": i.upstream_input.project,
                }
            )
            continue
        d = i.derived_from
        if d is None:
            raw.append({"name": i.name, "type": i.type})
            continue
        key = (d.run_id, d.project or "an unrecorded project")
        pipelines.setdefault(key, _upstream_pipeline(d.project))
        runs.setdefault(key, []).append(
            {
                "name": i.name,
                "type": i.type,
                "step": d.step_id or "",
                "output": d.output or i.name,
            }
        )
    deliveries: list[dict[str, Any]] = []
    for (run_id, project), rows in runs.items():
        roots = [r for r in (method_root, Path(project) / "method") if r is not None]
        words = pipeline_deliverables(pipelines[(run_id, project)], roots)
        steps_of: dict[str, list[str]] = {}
        for r in rows:
            steps_of.setdefault(r["output"], []).append(r["step"])
        for r in rows:
            r["what"] = words.get(r["output"], "")
            r["twice"] = [s for s in steps_of[r["output"]] if s != r["step"]]
        deliveries.append(
            {
                "run_id": run_id,
                "project": project,
                "pipeline": pipelines[(run_id, project)],
                "rows": rows,
            }
        )
    return {
        "deliveries": deliveries,
        "upstream_inputs": upstream,
        "raw": raw,
        "question": objective.question,
        "tools": list(tools),
    }


def _hanging(text: str, width: int = WIDTH) -> list[str]:
    """One list entry wrapped at `width` with its continuation lines indented two spaces."""
    return textwrap.wrap(
        text,
        width=width,
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]


def file_words(row: Mapping[str, Any], last: bool = True) -> str:
    """What one bound file is, for a reader: the pipeline's words, and where the same output
    also ships from. Of several copies the last carries the words (the pipeline's words describe
    what it delivers last); an earlier copy says which step wrote it and where the final one is."""
    what = str(row.get("what") or "")
    twice = [str(s) for s in row.get("twice") or []]
    if not twice:
        return what
    if last:
        also = f"also as {row.get('output')} from {', '.join(twice)}"
        return f"{what} ({also})" if what else also
    return (
        f"{row.get('output')} as {row.get('step')} wrote it; the same name ships from "
        f"{', '.join(twice)}"
    )


def _last_flags(rows: list[Mapping[str, Any]]) -> list[bool]:
    """For each row, whether it is the last of the rows that ship its output name."""
    remaining: dict[str, int] = {}
    for r in rows:
        remaining[str(r["output"])] = remaining.get(str(r["output"]), 0) + 1
    out = []
    for r in rows:
        remaining[str(r["output"])] -= 1
        out.append(remaining[str(r["output"])] == 0)
    return out


def bound_table(bound: Mapping[str, Any]) -> list[dict[str, str]]:
    """The bound files as table rows grouped by step, for the confirm card and `present --hold`:
    `step`, `name`, `type`, `what` (`file_words`), the step named once per group."""
    out: list[dict[str, str]] = []
    for dv in bound.get("deliveries") or []:
        for step, members in _by_step(dv["rows"]).items():
            for n, (r, last) in enumerate(members):
                out.append(
                    {
                        "step": step if n == 0 else "",
                        "name": str(r["name"]),
                        "type": str(r["type"]),
                        "what": file_words(r, last),
                    }
                )
    return out


def _by_step(rows: list[Mapping[str, Any]]) -> dict[str, list[tuple[Mapping[str, Any], bool]]]:
    """The rows grouped by step in first-seen order, each with its `last` flag."""
    steps: dict[str, list[tuple[Mapping[str, Any], bool]]] = {}
    for r, last in zip(rows, _last_flags(rows), strict=True):
        steps.setdefault(str(r["step"]), []).append((r, last))
    return steps


def bound_lines(bound: Mapping[str, Any]) -> list[str]:
    """The bound structure as the echo-back says it: a paragraph per delivery, then the files
    grouped by step as lists, then the upstream input, the other inputs, the question and the
    tools, one line each. Lines fit in 100 columns."""
    lines: list[str] = []
    for dv in bound.get("deliveries") or []:
        rows = list(dv["rows"])
        if lines:
            lines.append("")
        lines += _hanging_para(
            f"Delivery bound: run {dv['run_id']} of {dv['project']} ({len(rows)} files), by step."
        )
        for step, members in _by_step(rows).items():
            lines += ["", f"Step {step}:"]
            for r, last in members:
                words = file_words(r, last)
                entry = f"- {r['name']} ({r['type']})" + (f": {words}" if words else "")
                lines += _hanging(entry)
    rest = bound_rest(bound)
    if rest:
        lines.append("")
        for sentence in rest:
            lines += _hanging(f"- {sentence}")
    return lines


def bound_rest(bound: Mapping[str, Any]) -> list[str]:
    """The bound inputs that are not the delivery, one sentence each: the upstream input the
    pipeline ran on, the inputs that are not a delivery, the upstream question, the tools as a
    count and their names."""
    rest: list[str] = []
    for u in bound.get("upstream_inputs") or []:
        rest.append(
            f"The input the pipeline ran on, read-only, bound by name: {u['name']} ({u['type']}), "
            f"the input {u['input']} of {u['project']}."
        )
    raw = bound.get("raw") or []
    if raw:
        rest.append(
            "Inputs that are not a delivery: "
            + ", ".join(f"{r['name']} ({r['type']})" for r in raw)
            + "."
        )
    rest.append(f"The upstream project asked {bound.get('question')}.")
    tools = list(bound.get("tools") or [])
    if tools:
        rest.append(f"The method's {len(tools)} tools: {', '.join(tools)}.")
    return rest


def _hanging_para(text: str, width: int = WIDTH) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [
        text
    ]


def open_echo_lines(
    objective: Objective,
    inputs: InputsManifest,
    tools: list[Module],
    method_root: Path | None = None,
) -> list[str]:
    """What an open project is bound to, without the switch paragraph (`bound_lines` of
    `bound_structure`). The echo-back says it after the switch; the open summary's "What was
    analyzed" is it."""
    names = [m.manifest.name for m in tools]
    return bound_lines(bound_structure(objective, inputs, names, method_root))
