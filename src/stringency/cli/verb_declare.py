"""`stringency declare --check <dir>` (design 2.7): every check `init` runs, no project."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError
from stringency.project import InitRequest, check_declarations


@handle_errors
def declare(
    directory: Path = typer.Argument(
        ..., help="directory holding objective.yml, design.yml, inputs.yml"
    ),
    check: bool = typer.Option(
        False, "--check", help="validate the declarations and print the echo-back"
    ),
    method: str = typer.Option(..., "--method", help="<git-url>@<tag> of the method repo"),
    pipeline: str = typer.Option(..., "--pipeline"),
    objective: Path | None = typer.Option(None, "--objective"),
    design: Path | None = typer.Option(None, "--design"),
    inputs: Path | None = typer.Option(None, "--inputs"),
    mode: str = typer.Option("pipeline", "--mode"),
    profile: str = typer.Option("standard", "--profile"),
    judgment_harness: str = typer.Option("subagent", "--judgment-harness"),
    execution: str = typer.Option("operator", "--execution"),
    executor: str = typer.Option("apptainer", "--executor"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not check:
        raise ConfigError("declare does one thing for now: --check")
    files = {
        "objective": objective or directory / "objective.yml",
        "design": design or directory / "design.yml",
        "inputs": inputs or directory / "inputs.yml",
    }
    for name, p in files.items():
        if not p.exists():
            raise ConfigError(f"no {name} file at {p}")
    result = check_declarations(
        InitRequest(
            path=directory,  # replaced by a temporary directory inside check_declarations
            method=method,
            pipeline=pipeline,
            objective=files["objective"],
            design=files["design"],
            inputs=files["inputs"],
            mode=mode,
            profile=profile,
            judgment_harness=judgment_harness,
            execution=execution,
            executor=executor,
        )
    )
    n = len(result.predicates)
    human = (
        result.echo.rstrip()
        + f"\n\ndeclarations check out: {n} init predicate(s) evaluated, none fired; "
        f"method {result.method_sha[:12]}. Nothing was created; `stringency init` binds the project."
    )
    emit(result.to_json(), as_json, human)
