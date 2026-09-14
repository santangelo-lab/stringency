"""`stringency lint <module-dir | method-repo>` (design 13, 14.1)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import Exit
from stringency.lint import lint_path


@handle_errors
def lint(
    path: str = typer.Argument(
        ..., help="a module directory, a method repository, or <repo-or-url>@<tag>"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    target = Path(path)
    if not target.exists() and "@" in path:
        # a method spec as `init` takes it: clone at the tag into a temporary directory
        from stringency.git import clone_at
        from stringency.project import _parse_method

        url, tag = _parse_method(path)
        with tempfile.TemporaryDirectory(prefix="stringency-lint-") as tmp:
            clone_at(url, tag, Path(tmp) / "method")
            report = lint_path(Path(tmp) / "method")
    else:
        report = lint_path(target)
    emit(
        {"schema": "stringency.lint/1", "errors": report.errors, "warnings": report.warnings},
        as_json,
        report.render(),
    )
    if not report.ok:
        raise typer.Exit(code=int(Exit.CONFIG))
