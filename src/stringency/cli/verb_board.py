"""`stringency board <root> [--write] [--json] [--watch [--interval <s>]]` (design 14.1): the
progress board."""

from __future__ import annotations

import contextlib
from pathlib import Path

import typer

from stringency.board import BOARD_FILE, board, watch
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError


@handle_errors
def board_(
    root: Path = typer.Argument(..., help="directory holding project directories"),
    write: bool = typer.Option(False, "--write", help=f"rewrite <root>/{BOARD_FILE}"),
    as_json: bool = typer.Option(False, "--json"),
    watch_: bool = typer.Option(
        False,
        "--watch",
        help="read the board again every --interval seconds and print it when a project "
        "changed (with --write, rewrite STATUS.md then); stop with Ctrl-C",
    ),
    interval: float = typer.Option(10.0, "--interval", help="--watch: seconds between reads"),
) -> None:
    if not root.is_dir():
        raise ConfigError(f"{root} is not a directory")
    if watch_:
        if as_json:
            raise ConfigError("--watch prints the board as text; --json reads it once")
        if interval < 1:
            raise ConfigError("--interval is at least 1 second")
        with contextlib.suppress(KeyboardInterrupt):
            watch(root, interval=interval, write=write, show=lambda t: typer.echo("\n" + t))
        return
    entries, text = board(root)
    if write:
        (root / BOARD_FILE).write_text(text)
    emit(
        {"schema": "stringency.board/1", "root": str(root), "projects": entries, "written": write},
        as_json,
        text + (f"\n(written to {root / BOARD_FILE})" if write else ""),
    )
