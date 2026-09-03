"""`stringency fork --from <run> --at <step> [--set step.param=value]... --reason` (design 2.6)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.fork import fork as do_fork
from stringency.project import Project


@handle_errors
def fork(
    from_run: str = typer.Option(..., "--from"),
    at: str = typer.Option(..., "--at"),
    sets: list[str] = typer.Option([], "--set", help="<step>.<param>=<value>; repeatable"),
    reason: str = typer.Option(..., "--reason"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    rc = do_fork(project, from_run=from_run, at=at, sets=list(sets), reason=reason)
    emit(
        {"schema": "stringency.fork/1", "run_id": rc.run_id, "parent_run_id": from_run, "at": at},
        as_json,
        f"run {rc.run_id} forked from {from_run} at {at}; `stringency run` continues it",
    )
