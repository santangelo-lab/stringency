"""`stringency next` (design 14.1): the coming step with its plan template, or the current hold."""

from __future__ import annotations

import json

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import RefusedError
from stringency.project import Project
from stringency.runloop import next_step
from stringency.runs import latest_run, load_run


def _current_rc(project: Project):  # type: ignore[no-untyped-def]
    row = latest_run(project.store)
    if row is None:
        raise RefusedError("no run has been opened; run `stringency run` first")
    return load_run(project, row["run_id"])


@handle_errors
def next_(as_json: bool = typer.Option(False, "--json")) -> None:
    project = Project.find()
    rc = _current_rc(project)
    nx = next_step(rc)
    payload = {**nx.to_json(), "run_id": rc.run_id}
    if nx.kind == "runnable":
        plan = nx.detail["plan"]
        lines = [
            f"next: {plan['step_id']}  {plan['module']}  {plan['operation']} ({plan['kind']}, runner {plan['runner']})"
        ]
        for k, v in plan["parameters"].items():
            rng = (
                f" range {v['range']}"
                if v["range"]
                else (f" options {v['options']}" if v["options"] else " fixed")
            )
            lines.append(
                f"  {k}: default {v['default']!r}{rng}"
                + ("  [decision point]" if v["decision_point"] else "")
            )
        lines.append(
            "  outputs: " + ", ".join(f"{k} ({v['type']})" for k, v in plan["outputs"].items())
        )
        if plan["evidence"]:
            lines.append("  evidence: " + ", ".join(e["kind"] for e in plan["evidence"]))
        if plan["vocabulary"]:
            lines.append("  vocabulary: " + ", ".join(plan["vocabulary"]))
        human = "\n".join(lines)
    else:
        human = nx.message
    emit(payload, as_json, human)
    if not as_json and nx.kind == "runnable":
        return
    _ = json  # keep import for typing consistency
