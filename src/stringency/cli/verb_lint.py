"""`stringency lint <module-dir | method-repo>` (design 13, 14.1)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import Exit
from stringency.lint import lint_path


@handle_errors
def lint(
    path: Path = typer.Argument(..., help="a module directory or a method repository"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    report = lint_path(path)
    emit(
        {"schema": "stringency.lint/1", "errors": report.errors, "warnings": report.warnings},
        as_json,
        report.render(),
    )
    if not report.ok:
        raise typer.Exit(code=int(Exit.CONFIG))
