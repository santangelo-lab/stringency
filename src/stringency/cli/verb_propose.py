"""`stringency propose <step> [--set k=v]... [--reason]` (design 3.4, 14.1)."""

from __future__ import annotations

import typer

from stringency.actions import coerce_value
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, Exit
from stringency.machine import StepStatus
from stringency.operator_exec.tickets import job_spec, render_job_spec
from stringency.project import Project
from stringency.runloop import next_step
from stringency.runs import open_or_resume
from stringency.steps import execute_engine
from stringency.steps import propose as do_propose


def parse_sets(sets: list[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for s in sets:
        if "=" not in s:
            raise ConfigError(f"--set expects key=value, got {s!r}")
        k, _, v = s.partition("=")
        k = k.split(".", 1)[1] if "." in k else k  # accept <step>.<param>=<value>
        out[k] = coerce_value(v)
    return out


@handle_errors
def propose(
    step: str = typer.Argument(...),
    sets: list[str] = typer.Option([], "--set", help="parameter=value; repeatable"),
    reason: str | None = typer.Option(
        None, "--reason", help="the agent's stated reason for its choices"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    rc = open_or_resume(project)
    prop = do_propose(rc, step, parse_sets(sets), rationale=reason)
    if prop.status == StepStatus.AWAITING_EXECUTION:
        spec = job_spec(prop, rc.env_digests.get(prop.plan.module.manifest.env), rc.executor)
        emit(
            {
                "schema": "stringency.propose/1",
                "run_id": rc.run_id,
                "status": str(prop.status),
                "job_spec": spec,
            },
            as_json,
            f"run {rc.run_id}\n" + render_job_spec(spec),
        )
        raise typer.Exit(code=int(Exit.AWAITING_EXECUTION))
    if prop.status == StepStatus.ADMISSIBLE:
        out = execute_engine(rc, prop)
        nx = next_step(rc)
        emit(
            {
                "schema": "stringency.propose/1",
                "run_id": rc.run_id,
                "status": str(out.status),
                "next": nx.to_json(),
            },
            as_json,
            f"run {rc.run_id}\n{out.message}\n{nx.message}",
        )
        if nx.exit_code:
            raise typer.Exit(code=nx.exit_code)
        return
    nx = next_step(rc)
    emit(
        {
            "schema": "stringency.propose/1",
            "run_id": rc.run_id,
            "status": str(prop.status),
            "next": nx.to_json(),
        },
        as_json,
        f"run {rc.run_id}\n{nx.message}",
    )
    raise typer.Exit(code=nx.exit_code)
