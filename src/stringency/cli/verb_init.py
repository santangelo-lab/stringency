"""`stringency init` (design 14.1, 2.7)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import Exit
from stringency.notify import notify_after
from stringency.project import InitRequest, init_project


@handle_errors
def init(
    path: Path = typer.Argument(..., help="project directory to create"),
    method: str = typer.Option(..., "--method", help="<git-url>@<tag> of the method repo"),
    pipeline: str | None = typer.Option(
        None, "--pipeline", help="pipeline name under method/pipelines/ (not in open mode)"
    ),
    objective: Path | None = typer.Option(None, "--objective"),
    design: Path | None = typer.Option(None, "--design"),
    inputs: Path | None = typer.Option(None, "--inputs"),
    mode: str = typer.Option("pipeline", "--mode", help="pipeline | open"),
    from_delivery: Path | None = typer.Option(
        None,
        "--from-delivery",
        help="open mode: a delivery directory (deliver/<run>/) whose files become the inputs; "
        "the design and objective are derived from the upstream project",
    ),
    upstream: Path | None = typer.Option(
        None, "--upstream", help="with --from-delivery: the upstream project root"
    ),
    profile: str = typer.Option("standard", "--profile"),
    owner: str | None = typer.Option(None, "--owner"),
    reviewer: str | None = typer.Option(None, "--reviewer"),
    judgment_harness: str = typer.Option("subagent", "--judgment-harness"),
    judgment_model: str | None = typer.Option(
        None, "--judgment-model", help="the judge's model (api, openai-compatible, command)"
    ),
    judgment_base_url: str | None = typer.Option(
        None,
        "--judgment-base-url",
        help="openai-compatible: the server, e.g. http://localhost:11434/v1",
    ),
    judgment_command: str | None = typer.Option(
        None,
        "--judgment-command",
        help="command: the command run per replicate with {schema}, {response}, {prompt_file}, {dir}",
    ),
    execution: str = typer.Option("operator", "--execution"),
    executor: str = typer.Option("apptainer", "--executor"),
    egress_max: int | None = typer.Option(
        None,
        "--egress-max",
        help="the highest data egress class this project allows: 0 none, 1 reference, "
        "2 terms, 3 derived, 4 data",
    ),
    operator_model: str = typer.Option(
        "hosted",
        "--operator-model",
        help="hosted | local | none: the model of the agent that operates the project",
    ),
    drafted_by: str = typer.Option(
        "person", "--drafted-by", help="person | agent: who wrote the three declaration files"
    ),
    brief: Path | None = typer.Option(
        None,
        "--brief",
        help="the person's own description, kept as brief.md beside the declarations",
    ),
    study: str | None = typer.Option(
        None,
        "--study",
        help="the study this project opts into: siblings naming the same study under the same "
        "parent directory share one design acceptance and one parameter acceptance",
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
            judgment_model=judgment_model,
            judgment_base_url=judgment_base_url,
            judgment_command=judgment_command,
            execution=execution,
            executor=executor,
            egress_max=egress_max,
            operator_model=operator_model,
            drafted_by=drafted_by,
            brief=brief,
            from_delivery=from_delivery,
            upstream=upstream,
            study=study,
        )
    )
    hold = project.confirm_hold()
    egress = project.egress_assessment()
    ehold = project.egress_hold(egress)
    payload = {
        "schema": "stringency.init/1",
        "project_id": project.config.project_id,
        "path": str(project.root),
        "method_sha": project.config.method.sha,
        "confirm_hold": hold["hold_id"] if hold else None,
        "inheritance": project.inheritance_report() if not project.open_ended else None,
        "echo": str(project.echo_path()),
        "egress_hold": ehold["hold_id"] if ehold else None,
        "egress": {
            "max_class": egress.max_class,
            "assessed_class": egress.assessed_class,
            "within": egress.within,
            "report": str(project.egress_report_path(egress)),
        },
        "declarations": project.config.declarations.model_dump()
        if project.config.declarations
        else None,
    }
    human = (
        f"project {project.config.project_id} bound at {project.root}"
        + (" (open mode)" if project.open_ended else "")
        + "\n"
        f"method {project.config.method.repo} @ {project.config.method.tag} ({project.config.method.sha[:12]})\n"
        f"echo-back written to {project.echo_path()}\n"
        f"{egress.summary_line()}; report {project.egress_report_path(egress)}"
    )
    if payload["inheritance"]:
        human += f"\n{payload['inheritance']}"
    if hold is not None and hold["resolved_by_review"] is None:
        human += (
            f"\nheld: hold {hold['hold_id']} (confirm); waits on owner {project.config.roles.owner}; "
            f"run `stringency review --hold {hold['hold_id']}` in {project.root}"
        )
    if ehold is not None and ehold["resolved_by_review"] is None:
        human += (
            f"\nheld: hold {ehold['hold_id']} (egress); waits on owner "
            f"{project.config.roles.owner}; run `stringency review --hold {ehold['hold_id']}` "
            f"in {project.root}"
        )
    refresh_if_present(project.root)
    notify_after(project)
    emit(payload, as_json, human)
    open_hold = any(h is not None and h["resolved_by_review"] is None for h in (hold, ehold))
    if open_hold:
        # init leaves a hold open: exit 10 like every other verb that stops on a hold (design 14.2)
        raise typer.Exit(code=int(Exit.HELD))
