"""`stringency fork --from <run> --at <step> [--set step.param=value]... --reason [--check]`
(design 2.6). The output lists what every re-run step will run with and where each value comes
from (`inherited` from the parent, `fork` from `--set`, `default`); `--check` lists it and opens
no run."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.fork import check as do_check
from stringency.fork import fork as do_fork
from stringency.fork import render_params, resolved_params
from stringency.project import Project


@handle_errors
def fork(
    from_run: str = typer.Option(..., "--from"),
    at: str = typer.Option(..., "--at"),
    sets: list[str] = typer.Option([], "--set", help="<step>.<param>=<value>; repeatable"),
    reason: str | None = typer.Option(None, "--reason"),
    check: bool = typer.Option(
        False, "--check", help="list what each re-run step would run with; open no run"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if check:
        table = do_check(project, from_run=from_run, at=at, sets=list(sets))
        emit(
            {
                "schema": "stringency.fork/1",
                "check": True,
                "parent_run_id": from_run,
                "at": at,
                "params": table,
            },
            as_json,
            f"a fork of {from_run} at {at} would run with:\n{render_params(table)}",
        )
        return
    if not reason:
        raise typer.BadParameter("--reason is required to fork")
    rc = do_fork(project, from_run=from_run, at=at, sets=list(sets), reason=reason)
    table = resolved_params(project, from_run, at, rc.delta_for_all())
    emit(
        {
            "schema": "stringency.fork/1",
            "run_id": rc.run_id,
            "parent_run_id": from_run,
            "at": at,
            "params": table,
        },
        as_json,
        f"run {rc.run_id} forked from {from_run} at {at}; `stringency run` continues it, with:\n"
        + render_params(table),
    )
