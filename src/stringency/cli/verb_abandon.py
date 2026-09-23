"""`stringency abandon --run <id> --reason` (design 2.6)."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.notify import notify_after
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
    refresh_if_present(project.root)
    notify_after(project)
    emit(
        {"schema": "stringency.abandon/1", "run_id": run_id, "status": "abandoned"},
        as_json,
        f"run {run_id} abandoned: {reason}",
    )
