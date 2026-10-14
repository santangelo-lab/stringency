"""`stringency probe [--method <path|url@tag>] [--no-hash] [--json]` (design 14.1): is this
install ready? Exit 0 when every check passes, 1 otherwise."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.probe import probe as do_probe
from stringency.probe import render


@handle_errors
def probe(
    method: str | None = typer.Option(
        None, "--method", help="a method checkout or <url>@<tag>: check its requires and images too"
    ),
    no_hash: bool = typer.Option(
        False, "--no-hash", help="do not hash the images (a multi-GB SIF takes a while)"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = do_probe(method, hash_images=not no_hash)
    emit(payload, as_json, render(payload))
    if not payload["ok"]:
        raise typer.Exit(code=1)
