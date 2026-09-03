"""`stringency controls run [--module <name>]` (design 11)."""

from __future__ import annotations

import typer

from stringency.cli.common import emit, handle_errors
from stringency.controls import run_controls
from stringency.exit_codes import Exit
from stringency.project import Project

app = typer.Typer(no_args_is_help=True)


@app.command("run")
@handle_errors
def run(
    module: str | None = typer.Option(None, "--module"),
    allow_mock: bool = typer.Option(
        False, "--allow-mock", help="tests only: let the mock harness answer"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    results = run_controls(project, module, allow_mock=allow_mock)
    lines = []
    for r in results:
        metrics = ", ".join(f"{k} {v}" for k, v in sorted(r.metrics.items()))
        flag = "pass" if r.passed else "FAIL"
        if r.regression:
            flag += " REGRESSION"
        lines.append(
            f"{r.module}  {r.control} ({r.kind}): {flag}  {metrics}"
            + (f"  [{'; '.join(r.notes)}]" if r.notes else "")
        )
    emit(
        {"schema": "stringency.controls/1", "results": [r.to_json() for r in results]},
        as_json,
        "\n".join(lines) or "no controls found",
    )
    if any(not r.passed or r.regression for r in results):
        raise typer.Exit(code=int(Exit.FAILED))
