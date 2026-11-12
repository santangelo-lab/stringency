"""`stringency inputs add <name> <path> --type <type> --source "<the person's words>"` (design
2.3 as amended 2026-11-11, PLAN L160): a person's file brought into an open project, copied,
hashed and recorded with their words; `$inputs.<name>` binds it by name."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.added_inputs import add as add_input
from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.project import Project

app = typer.Typer(help="a person's file as an input of an open project", no_args_is_help=True)


@app.command("add")
@handle_errors
def add(
    name: str = typer.Argument(..., help="the input's name; `$inputs.<name>` binds it"),
    path: Path = typer.Argument(..., help="the person's file or directory; it is copied"),
    type_: str = typer.Option(..., "--type", help="an input type a tool of the method takes"),
    source: str = typer.Option(
        ..., "--source", help="the person's words: what the file is and where it came from"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    done = add_input(project, name, path, type_, source)
    refresh_if_present(project.root)
    emit(
        {"schema": "stringency.inputs_add/1", **done},
        as_json,
        f"input {name} added ({type_}, blake3 {done['blake3'][:12]}), copied to {done['path']}; "
        f"bind it with --in <input>={done['ref']}",
    )
