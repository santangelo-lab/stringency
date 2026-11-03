"""`stringency flag [--run <id>] [--step <id>] [--object <delivered file>] --reason "..."
[--json]` (the beta-tester package, 2026-11-03): record that a person says a delivered result
is wrong. The run defaults to the latest delivered one; the object is a file the delivery
index lists, recorded with its hash; the reason is the person's words. Exit 0; 15 when the run,
step or object is not one of the run's or the reason is empty."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.flags import record_flag
from stringency.project import Project


@handle_errors
def flag(
    run_id: str | None = typer.Option(None, "--run", help="default: the latest delivered run"),
    step_id: str | None = typer.Option(None, "--step", help="the step the result came from"),
    object_name: str | None = typer.Option(
        None, "--object", help="a delivered file's name, as the delivery lists it"
    ),
    reason: str = typer.Option(..., "--reason", help="the person's words"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    result = record_flag(project, run_id, reason=reason, step_id=step_id, object_name=object_name)
    refresh_if_present(project.root)
    what = (
        f"{result['object_name']} ({result['object_kind']})" if result["object_name"] else "the run"
    )
    where = f" from step {result['step_id']}" if result["step_id"] else ""
    emit(
        {"schema": "stringency.flag/1", **result},
        as_json,
        f"flag {result['flag_id']} recorded on run {result['run_id']}: {what}{where}, "
        f"by {result['flagged_by']} via {result['via']}",
    )
