"""`stringency controls` subcommands (design 14.1)."""

from __future__ import annotations

import typer

from stringency.cli.common import handle_errors, not_implemented

app = typer.Typer(no_args_is_help=True)


@app.command("run")
@handle_errors
def run() -> None:
    not_implemented("controls run")
