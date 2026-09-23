"""`stringency board <root> [--write] [--json]` (design 14.1): the progress board."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.board import BOARD_FILE, board
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError


@handle_errors
def board_(
    root: Path = typer.Argument(..., help="directory holding project directories"),
    write: bool = typer.Option(False, "--write", help=f"rewrite <root>/{BOARD_FILE}"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not root.is_dir():
        raise ConfigError(f"{root} is not a directory")
    entries, text = board(root)
    if write:
        (root / BOARD_FILE).write_text(text)
    emit(
        {"schema": "stringency.board/1", "root": str(root), "projects": entries, "written": write},
        as_json,
        text + (f"\n(written to {root / BOARD_FILE})" if write else ""),
    )
