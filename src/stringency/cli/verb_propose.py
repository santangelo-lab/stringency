"""`stringency propose <step> [--set k=v]... [--reason]` (design 3.4, 14.1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import typer

from stringency.actions import coerce_value
from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, Exit
from stringency.machine import StepStatus
from stringency.operator_exec.tickets import job_spec, render_job_spec
from stringency.project import Project
from stringency.runloop import next_step
from stringency.runs import open_or_resume
from stringency.steps import execute_engine, starting_params
from stringency.steps import propose as do_propose


def parse_sets(sets: list[str], properties: Mapping[str, Any] | None = None) -> dict[str, object]:
    """`--set k=v` entries, each coerced by the parameter's schema when `properties` (the
    module's `params.schema.json` properties) is given: lists as `[a,b]`, string enums as
    spelled (backlog L47, L39)."""
    out: dict[str, object] = {}
    for s in sets:
        if "=" not in s:
            raise ConfigError(f"--set expects key=value, got {s!r}")
        k, _, v = s.partition("=")
        k = k.split(".", 1)[1] if "." in k else k  # accept <step>.<param>=<value>
        schema = properties.get(k) if properties else None
        out[k] = coerce_value(v, schema if isinstance(schema, dict) else None)
    return out


def schema_properties(rc: Any, step: str) -> Mapping[str, Any] | None:
    """The properties of the step's module schema, or None when the step is not declared."""
    try:
        decl = rc.pipeline.step(step)
        manifest = rc.project.modules.require(decl.module).manifest
    except Exception:  # noqa: BLE001  (an unknown step is reported by propose itself)
        return None
    props = manifest.params_schema.get("properties")
    return props if isinstance(props, dict) else None


@handle_errors
def propose(
    step: str = typer.Argument(...),
    sets: list[str] = typer.Option([], "--set", help="parameter=value; repeatable"),
    reason: str | None = typer.Option(
        None, "--reason", help="the agent's stated reason for its choices"
    ),
    as_json: bool = typer.Option(False, "--json"),
    new: bool = typer.Option(
        False,
        "--new",
        help="open a new run when the latest is closed (so the first step can be proposed)",
    ),
) -> None:
    project = Project.find()
    rc = open_or_resume(project, new=new)
    # an operator's proposal starts from the objective's declared values, what a fork's parent
    # admitted, and the fork's own --set delta (design 2.5, 2.6); --set here overrides them all
    inherited = starting_params(rc, step) or {}
    inherited.update({k: (v, "fork") for k, v in rc.delta_for(step).items()})
    prop = do_propose(
        rc,
        step,
        parse_sets(sets, schema_properties(rc, step)),
        rationale=reason,
        inherited=inherited or None,
    )
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
    refresh_if_present(project.root)
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
