"""`stringency run` (design 14.1, 14.2)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.project import Project
from stringency.runloop import run_loop
from stringency.runs import open_or_resume


@handle_errors
def run(
    until: str | None = typer.Option(None, "--until", help="stop after this step"),
    allow_dirty: str | None = typer.Option(
        None, "--allow-dirty", help="reason to run with uncommitted method changes"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    rc = open_or_resume(project, allow_dirty=allow_dirty)
    nx = run_loop(rc, until=until)
    payload = {**nx.to_json(), "run_id": rc.run_id, "run_status": rc.run["status"]}
    emit(payload, as_json, f"run {rc.run_id}\n{nx.message}")
    if nx.exit_code:
        raise typer.Exit(code=nx.exit_code)
