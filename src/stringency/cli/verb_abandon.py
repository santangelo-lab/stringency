"""`stringency abandon --run <id> --reason` (design 2.6), and `stringency abandon --step <id>
--reason` in an open project (L114): close one on-demand step that will not be carried out."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError
from stringency.notify import notify_after
from stringency.project import Project
from stringency.runs import abandon as do_abandon
from stringency.runs import abandon_step


@handle_errors
def abandon(
    run_id: str | None = typer.Option(None, "--run"),
    step: str | None = typer.Option(
        None,
        "--step",
        help="in an open project: close one tool call or exec that is held or accepted and "
        "will not be carried out; the run stays open",
    ),
    reason: str = typer.Option(..., "--reason"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if step is not None:
        done = abandon_step(project, step, reason, run_id=run_id)
        refresh_if_present(project.root)
        notify_after(project)
        emit(
            {"schema": "stringency.abandon/1", "status": "abandoned", **done},
            as_json,
            f"step {step} of run {done['run_id']} abandoned ({done['was']}); "
            f"{len(done['holds'])} hold(s) closed as withdrawn: {reason}",
        )
        return
    if run_id is None:
        raise ConfigError("abandon needs --run <id>, or --step <id> in an open project")
    do_abandon(project, run_id, reason)
    refresh_if_present(project.root)
    notify_after(project)
    emit(
        {"schema": "stringency.abandon/1", "run_id": run_id, "status": "abandoned"},
        as_json,
        f"run {run_id} abandoned: {reason}",
    )
