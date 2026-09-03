"""`stringency abandon --run <id> --reason` (design 2.6)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.project import Project
from stringency.runs import abandon as do_abandon


@handle_errors
def abandon(
    run_id: str = typer.Option(..., "--run"),
    reason: str = typer.Option(..., "--reason"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    do_abandon(project, run_id, reason)
    emit(
        {"schema": "stringency.abandon/1", "run_id": run_id, "status": "abandoned"},
        as_json,
        f"run {run_id} abandoned: {reason}",
    )
