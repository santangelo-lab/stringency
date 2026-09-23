"""`stringency init` (design 14.1, 2.7)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import Exit
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
    drafted_by: str = typer.Option(
        "person", "--drafted-by", help="person | agent: who wrote the three declaration files"
    ),
    brief: Path | None = typer.Option(
        None,
        "--brief",
        help="the person's own description, kept as brief.md beside the declarations",
    ),
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
            drafted_by=drafted_by,
            brief=brief,
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
        "declarations": project.config.declarations.model_dump()
        if project.config.declarations
        else None,
    }
    human = (
        f"project {project.config.project_id} bound at {project.root}\n"
        f"method {project.config.method.repo} @ {project.config.method.tag} ({project.config.method.sha[:12]})\n"
        f"echo-back written to {project.echo_path()}"
    )
    if hold is not None:
        human += (
            f"\nheld: hold {hold['hold_id']} (confirm); waits on owner {project.config.roles.owner}; "
            f"run `stringency review --hold {hold['hold_id']}` in {project.root}"
        )
    refresh_if_present(project.root)
    emit(payload, as_json, human)
    if hold is not None and hold["resolved_by_review"] is None:
        # init leaves a hold open: exit 10 like every other verb that stops on a hold (design 14.2)
        raise typer.Exit(code=int(Exit.HELD))
