"""`stringency tools list [--context] [--json]` (open_mode_plan.md 2.3): the tools a method
ships for questions, with what they could bind here. A reading verb; loads no plugin."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.present import Site
from stringency.tools import render_tools, tools_payload

app = typer.Typer(help="the tools a method ships for questions (open mode)", no_args_is_help=True)


@app.command("list")
@handle_errors
def list_(
    context: bool = typer.Option(
        False,
        "--context",
        help="add the objective's question and deliverables and the design's factors and levels",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    site = Site.find()
    payload = tools_payload(site, context=context)
    emit(payload, as_json, render_tools(payload))
