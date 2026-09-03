"""`stringency policy` subcommands (design 14.1)."""

from __future__ import annotations

import typer

from stringency.cli.common import handle_errors, not_implemented

app = typer.Typer(no_args_is_help=True)


@app.command("show")
@handle_errors
def show() -> None:
    not_implemented("policy show")
