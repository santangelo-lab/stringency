"""`stringency present [--run <id>] [--hold <id>] [--skills-dir <dir>] [--json]` (design 14.3)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.present import Site, present_hold, present_run, render_markdown


@handle_errors
def present(
    run_id: str | None = typer.Option(None, "--run", help="a completed run (default: the latest)"),
    hold_id: str | None = typer.Option(
        None, "--hold", help="an open hold (default: the newest open one)"
    ),
    skills_dir: Path | None = typer.Option(
        None,
        "--skills-dir",
        help="read skills/<pipeline>.yml from here instead of the project's method clone",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Site.find()
    if hold_id is not None or (run_id is None and _has_open_hold(project)):
        payload = present_hold(project, hold_id, skills_dir)
    else:
        payload = present_run(project, run_id, skills_dir)
    emit(payload, as_json, render_markdown(payload))


def _has_open_hold(project: Site) -> bool:
    n = project.store.scalar("SELECT COUNT(*) FROM holds WHERE resolved_by_review IS NULL")
    return bool(n)
