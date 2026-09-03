"""`stringency deliver [--run] [--include <step>.<output>]...` (design 12.1)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.deliver import deliver as do_deliver
from stringency.exit_codes import RefusedError
from stringency.project import Project
from stringency.runs import latest_run, load_run


@handle_errors
def deliver(
    run_id: str | None = typer.Option(None, "--run"),
    include: list[str] = typer.Option([], "--include", help="<step>.<output>; repeatable"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if run_id is None:
        row = latest_run(project.store)
        if row is None:
            raise RefusedError("no run to deliver")
        run_id = row["run_id"]
    rc = load_run(project, run_id)
    d = do_deliver(rc, list(include))
    emit(
        {
            "schema": "stringency.deliver/1",
            "delivery_id": d.delivery_id,
            "run_id": run_id,
            "path": str(d.path),
            "files": d.files,
        },
        as_json,
        f"delivered run {run_id} to {d.path}\n{len(d.files)} file(s)\n\n{d.coverage}\n{d.methods}",
    )
