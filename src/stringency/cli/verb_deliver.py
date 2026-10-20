"""`stringency deliver [--run] [--include <step>.<output>]...` (design 12.1). In an open
project it regenerates `deliver/<run>/` (the report and every answer; 2026-10-19)."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.deliver import deliver as do_deliver
from stringency.exit_codes import RefusedError
from stringency.notify import notify_after
from stringency.project import Project
from stringency.runs import latest_run, load_run


@handle_errors
def deliver(
    run_id: str | None = typer.Option(None, "--run"),
    include: list[str] = typer.Option([], "--include", help="<step>.<output>; repeatable"),
    answers: list[str] = typer.Option(
        [],
        "--answer",
        help="refused: open mode writes every answer as it is filed; see `finding`",
        hidden=True,
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if run_id is None:
        row = latest_run(project.store)
        if row is None:
            raise RefusedError("no run to deliver")
        run_id = row["run_id"]
    rc = load_run(project, run_id)
    d = do_deliver(rc, list(include), list(answers))
    payload = {
        "schema": "stringency.deliver/1",
        "delivery_id": d.delivery_id,
        "run_id": run_id,
        "path": str(d.path),
        "files": d.files,
        "answers": d.answers,
    }
    refresh_if_present(project.root)
    if rc.open_ended:
        payload["changed"] = d.changed
        if d.changed:
            notify_after(project, run_id=run_id, delivery=payload)
        n_f = sum(1 for e in d.answers if e["finding"])
        emit(
            payload,
            as_json,
            f"report {'rewritten' if d.changed else 'unchanged'}: {d.path / 'report.md'}\n"
            f"{n_f} finding(s) of {len(d.answers)} answer(s); {len(d.files)} cited file(s)",
        )
        return
    notify_after(project, run_id=run_id, delivery=payload)
    emit(
        payload,
        as_json,
        f"delivered run {run_id} to {d.path}\n{len(d.files)} file(s)\n\n{d.coverage}\n{d.methods}",
    )
