"""`deliver/<run>/summary.md` (design 12.1): the engine's plain rendering of a run for a reader
who will not open the trace: what was analyzed, what ran, what was checked and who decided
what, judgments, what was delivered, what was not checked. Every sentence is filled from the
trace; the file contains no interpretation and no adjectives.

Reads: steps, actions (parameters and their source), the echo-back on disk, the pipeline's
step titles, the coverage data (which read predicate_results, holds, reviews, judgments,
consensus, invocations). Writes nothing; `deliver` writes the file.
"""

from __future__ import annotations

from typing import Any

from stringency.methods import number_word
from stringency.runs import RunContext
from stringency.steps import action_from_row

NOT_CHECKED = "not checked: anything not listed above"


def _n(n: int) -> str:
    return number_word(n)


def _count(n: int) -> str:
    """A count that stands alone in a list: 'none' rather than 'no'."""
    return "none" if n == 0 else number_word(n)


def echo_body(text: str) -> str:
    """The echo-back without its heading, its acceptance instruction, and the hash block; the
    hashes are in the trace and `index.json`."""
    out: list[str] = []
    for line in text.splitlines():
        if line.startswith("Bound to:"):
            break
        if line.startswith("# ") or line.startswith("This is the engine's reading"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{_n(n)} {one if n == 1 else (many or one + 's')}"


def what_ran(rc: RunContext) -> list[str]:
    """One line per step, by title: parameters that differed from the defaults, or
    'at defaults'. Reads: steps, actions."""
    store, project = rc.store, rc.project
    lines: list[str] = []
    for step in project.pipeline.steps:
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        title = project.pipeline.title(step.id)
        if st != "completed":
            lines.append(f"- {title} (step {step.id}): did not complete; status {st}.")
            continue
        row = store.one(
            "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
            (rc.run_id, step.id),
        )
        if row is None:
            lines.append(f"- {title} (step {step.id}): completed.")
            continue
        action = action_from_row(row)
        changed = [
            f"{k} set to {action.parameters[k]}"
            for k, src in action.param_source.items()
            if src != "default" and k in action.parameters
        ]
        if not action.parameters:
            detail = "no parameters"
        elif changed:
            detail = "; ".join(changed) + (
                "; other parameters at defaults" if len(changed) < len(action.parameters) else ""
            )
        else:
            detail = "at defaults"
        lines.append(f"- {title} (step {step.id}): {detail}.")
    return lines


def what_was_checked(rc: RunContext, cov: dict[str, Any]) -> list[str]:
    g = cov["gate"]
    steps = cov["steps"]["declared"]
    lines = [
        f"{_plural(g['evaluated'], 'check').capitalize()} were evaluated over "
        f"{_plural(steps, 'step')}; {_plural(g['fired']['block'], 'block')} and "
        f"{_plural(len(g['flags']), 'flag')} were raised."
    ]
    for f in g["flags"]:
        title = rc.project.pipeline.title(f["step"])
        if f["verdict"] == "open":
            lines.append(f"- {f['predicate']} on {title}: open, not yet decided.")
            continue
        reason = f' "{f["reason"]}"' if f["reason"] else ""
        lines.append(
            f"- {f['predicate']} on {title}: {f['verdict']} by {f['reviewer']} via {f['via']} on {f['date']}{reason}."
        )
    return lines


def judgments(rc: RunContext, cov: dict[str, Any]) -> list[str]:
    if not cov["judgment"]:
        return ["No step asked for a judgment."]
    lines = []
    for j in cov["judgment"]:
        title = rc.project.pipeline.title(j["step"])
        lines.append(
            f"- {title} (step {j['step']}): {_plural(j['items'], 'item')} judged by "
            f"{_plural(j['replicates'], 'independent replicate')}; {_count(j['agreed'])} agreed, "
            f"{_count(j['self_uncertain'])} self-uncertain, {_count(j['run_disagreement'])} in disagreement; "
            f"reviews: {_count(j['accepted'])} accepted, {_count(j['override'])} corrected, "
            f"{_count(j['unresolved'])} unresolved."
        )
    return lines


def what_you_received(rc: RunContext, files: list[dict[str, Any]]) -> list[str]:
    project = rc.project
    lines = []
    for f in files:
        step = project.pipeline.step(f["step_id"])
        spec = project.modules.require(step.module).manifest.outputs.get(f["output"])
        shape = f"; type {spec.type}, format {spec.format}" if spec else ""
        lines.append(
            f"- `{f['file']}`: the {f['output']} output of {project.pipeline.title(f['step_id'])}{shape}."
        )
    lines.append(
        "- `coverage.md`: the coverage report; `methods.md`: the methods paragraph; "
        "`index.json`: each file linked to its run, step, action, and hash."
    )
    return lines


def render_summary(rc: RunContext, cov: dict[str, Any], files: list[dict[str, Any]]) -> str:
    project = rc.project
    echo_path = project.echo_path()
    echo = echo_body(echo_path.read_text()) if echo_path.exists() else "No echo-back was recorded."
    sections = [
        f"# Summary of run {rc.run_id}",
        "",
        f"Project {project.config.project_id}; pipeline {project.pipeline.name} {project.pipeline.version}; "
        f"profile {project.config.profile}.",
        "",
        "## What was analyzed",
        "",
        echo,
        "",
        "## What ran",
        "",
        *what_ran(rc),
        "",
        "## What was checked and decided",
        "",
        *what_was_checked(rc, cov),
        "",
        "## Judgments",
        "",
        *judgments(rc, cov),
        "",
        "## What you received",
        "",
        *what_you_received(rc, files),
        "",
        "## Not checked",
        "",
        NOT_CHECKED,
    ]
    return "\n".join(sections) + "\n"
