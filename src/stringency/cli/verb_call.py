"""`stringency call <tool> [--question <id>] [--in k=ref]... [--set k=v]... [--asked-by
person] [--reason] [--json]` (open_mode_plan.md 2.3): run a tool the method ships as an
on-demand step of the open run: propose, pre-gate, execute on the engine, post-gate. Exit
codes are the run's: 0 completed, 10 held, 11 blocked, 12 rejected, 13 failed, 15 config."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import DETACH_HELP, detach_now, emit, handle_errors
from stringency.cli.verb_propose import parse_sets
from stringency.controls import ControlResult, ensure_current
from stringency.exit_codes import ConfigError, Exit, StringencyError
from stringency.machine import StepStatus
from stringency.notify import notify_after
from stringency.project import Project
from stringency.questions import open_for_questions, question
from stringency.resources import Override
from stringency.runloop import next_step
from stringency.steps import execute_engine, propose_tool

ASKED_BY = ("agent", "person")


def parse_ins(ins: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for s in ins:
        if "=" not in s:
            raise ConfigError(f"--in expects <input>=<ref>, got {s!r}")
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip()
    return out


@handle_errors
def call(
    tool: str = typer.Argument(..., help="a module of the method that lists open"),
    question_id: str | None = typer.Option(None, "--question", help="the question this answers"),
    ins: list[str] = typer.Option(
        [], "--in", help="<input>=<$inputs.name | $steps.id.out | artifact id>; repeatable"
    ),
    sets: list[str] = typer.Option([], "--set", help="parameter=value; repeatable"),
    asked_by: str = typer.Option(
        "agent",
        "--asked-by",
        help="agent | person: who chose every --set value; person opens no approval hold and "
        "needs --reason in the person's words",
    ),
    reason: str | None = typer.Option(None, "--reason", help="why these values"),
    cpus: int | None = typer.Option(
        None, "--cpus", help="CPUs for each step this invocation runs, within the policy's cap"
    ),
    memory: str | None = typer.Option(
        None,
        "--memory",
        help="memory in GB for each step this invocation runs (64 or 64GB), within the policy's cap",
    ),
    detach: bool = typer.Option(False, "--detach", help=DETACH_HELP),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if detach:
        detach_now(as_json)
        return
    override = Override.from_options(cpus, memory)
    if asked_by not in ASKED_BY:
        raise ConfigError("--asked-by must be agent or person")
    if asked_by == "person" and not reason:
        raise ConfigError("--asked-by person needs --reason: the person's words for the values")
    project = Project.find()
    rc = open_for_questions(project)
    rc.resource_override = override
    if question_id is not None:
        question(rc, question_id)  # must be a question of this run
    # a tool the method tested is checked before its first step here, so its answer can be
    # trusted (2026-10-19); a failing control is recorded and the step still runs, untested
    module = next((m for m in project.tools() if m.manifest.name == tool), None)
    controls: list[ControlResult] = []
    control_error = None
    if module is not None:
        try:
            controls = ensure_current(project, module, rc.env_digests.get(module.manifest.env))
        except StringencyError as e:  # a control that cannot run leaves the tool untested
            control_error = str(e)
    prop = propose_tool(
        rc,
        tool,
        parse_ins(ins),
        parse_sets(
            sets,
            (module.manifest.params_schema.get("properties") if module is not None else None),
        )
        or None,
        reason,
        source=asked_by,
        question_id=question_id,
    )
    status = prop.status
    message = ""
    if status == StepStatus.ADMISSIBLE:
        out = execute_engine(rc, prop)
        status, message = out.status, out.message
    nx = next_step(rc)
    artifacts = [
        dict(r)
        for r in rc.store.all(
            "SELECT artifact_id, name, kind, path FROM artifacts WHERE run_id=? AND step_id=? "
            "AND status='produced' ORDER BY rowid",
            (rc.run_id, prop.action.step_id),
        )
    ]
    payload = {
        "schema": "stringency.call/1",
        "run_id": rc.run_id,
        "step_id": prop.action.step_id,
        "tool": prop.plan.module.ref,
        "status": str(status),
        "question_id": question_id,
        "parameters": prop.action.parameters,
        "param_source": prop.action.param_source,
        "inputs": {k: str(v.job_value()) for k, v in prop.plan.inputs.items()},
        "artifacts": artifacts,
        "controls_run": [r.to_json() for r in controls],
        "controls_error": control_error,
        "next": nx.to_json(),
    }
    if nx.kind == "held":
        # the console's page for the hold when `page_url` is set (L134 b)
        payload["console_url"] = nx.detail.get("console_url")
    lines = [f"run {rc.run_id}"]
    if control_error:
        lines.append(
            f"the controls of {tool} could not run ({control_error}); its outputs will be "
            "labelled untested"
        )
    for r in controls:
        lines.append(
            f"control {r.control} of {r.module} ran before its first use: "
            + ("pass" if r.passed else "FAIL; its outputs will be labelled untested")
        )
    lines.append(f"step {prop.action.step_id}: {prop.plan.module.ref} {status}")
    if message:
        lines.append(message)
    for a in artifacts:
        lines.append(f"  {a['name']} ({a['kind']}): {a['artifact_id']}")
    lines.append(nx.message)
    refresh_if_present(project.root)
    notify_after(project, run_id=rc.run_id, nx=nx)
    emit(payload, as_json, "\n".join(lines))
    code = {
        StepStatus.COMPLETED: 0,
        StepStatus.HELD: int(Exit.HELD),
        StepStatus.BLOCKED: int(Exit.BLOCKED),
        StepStatus.REJECTED: int(Exit.REJECTED),
        StepStatus.FAILED: int(Exit.FAILED),
    }.get(status, int(Exit.INTERNAL))
    if code:
        raise typer.Exit(code=code)
