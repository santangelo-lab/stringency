"""`stringency archive --reason "<why>" [--json]` (L132): mark the project as archived. Writes
`prov/archived.json` (who, when, why) and nothing in the trace; the console lists the project
under "archived" and `board` skips it. Removing the file brings the project back. Loads no
plugin, so a project whose plugin is gone can still be put away."""

from __future__ import annotations

import contextlib
import sys

import typer

from stringency.archive import archive_project
from stringency.board import BOARD_FILE, write_board
from stringency.cli.common import emit, handle_errors
from stringency.jobs import find_root


@handle_errors
def archive(
    reason: str = typer.Option(..., "--reason", help="why the project is put away"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    root = find_root()
    record, notes = archive_project(root, reason)
    for n in notes:
        sys.stderr.write(f"note: {n}\n")
    parent = root.parent
    if (parent / BOARD_FILE).exists():
        # the board drops the project now, not at the next verb; a convenience never fails it
        with contextlib.suppress(Exception):
            write_board(parent)
    emit(
        {"schema": "stringency.archive/1", "project": root.name, **record},
        as_json,
        f"{root.name} archived: {reason}\n"
        f"the console lists it under archived and `board` skips it; remove "
        f"{record['marker']} to bring it back",
    )
