"""`stringency init` (design 14.1, 2.7)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.project import InitRequest, init_project


@handle_errors
def init(
    path: Path = typer.Argument(..., help="project directory to create"),
    method: str = typer.Option(..., "--method", help="<git-url>@<tag> of the method repo"),
    pipeline: str = typer.Option(..., "--pipeline", help="pipeline name under method/pipelines/"),
    objective: Path = typer.Option(..., "--objective"),
    design: Path = typer.Option(..., "--design"),
    inputs: Path = typer.Option(..., "--inputs"),
    mode: str = typer.Option("pipeline", "--mode"),
    profile: str = typer.Option("standard", "--profile"),
    owner: str | None = typer.Option(None, "--owner"),
    reviewer: str | None = typer.Option(None, "--reviewer"),
    judgment_harness: str = typer.Option("subagent", "--judgment-harness"),
    execution: str = typer.Option("operator", "--execution"),
    executor: str = typer.Option("apptainer", "--executor"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = init_project(
        InitRequest(
            path=path,
            method=method,
            pipeline=pipeline,
            objective=objective,
            design=design,
            inputs=inputs,
            mode=mode,
            profile=profile,
            owner=owner,
            reviewer=reviewer,
            judgment_harness=judgment_harness,
            execution=execution,
            executor=executor,
        )
    )
    hold = project.confirm_hold()
    payload = {
        "schema": "stringency.init/1",
        "project_id": project.config.project_id,
        "path": str(project.root),
        "method_sha": project.config.method.sha,
        "confirm_hold": hold["hold_id"] if hold else None,
        "echo": str(project.echo_path()),
    }
    human = (
        f"project {project.config.project_id} bound at {project.root}\n"
        f"method {project.config.method.repo} @ {project.config.method.tag} ({project.config.method.sha[:12]})\n"
        f"echo-back written to {project.echo_path()}\n"
        f"held: confirm {payload['confirm_hold']} waits on owner {project.config.roles.owner}; "
        f"run `stringency review` in {project.root}"
    )
    emit(payload, as_json, human)
