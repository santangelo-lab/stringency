"""`stringency exec <script | -> [--lang py|R|sh] [--question <id>] [--in k=ref]... [--out
name=type[/format]]... [--env <name>] [--seed N] [--reason] [--allow-local] [--json]`
(open_mode_plan.md 2.4; backlog G2 closed): run a script written in the session as an
on-demand step of the open run, under the executor, inputs read-only, the script in the trace,
every output recorded and labelled untested when cited. Exit codes are the run's."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import DETACH_HELP, detach_now, emit, handle_errors
from stringency.cli.verb_call import parse_ins
from stringency.exit_codes import ConfigError, Exit
from stringency.machine import StepStatus
from stringency.notify import notify_after
from stringency.project import Project
from stringency.questions import open_for_questions, question
from stringency.resources import Override
from stringency.runloop import next_step
from stringency.steps import EXEC_LANGS, execute_engine, parse_outs, propose_exec

UNTESTED_LINE = (
    "untested: a script written in this session ran on the engine and its outputs are "
    "recorded; no test or control has checked what they claim"
)


def read_script(source: str) -> tuple[str, str | None]:
    """(text, extension from the file name or None for stdin)."""
    if source == "-":
        return sys.stdin.read(), None
    p = Path(source)
    if not p.is_file():
        raise ConfigError(f"no script at {p}")
    return p.read_text(), p.suffix.lstrip(".") or None


@handle_errors
def exec_(
    script: str = typer.Argument(..., help="a script file, or - for stdin (never argv)"),
    lang: str | None = typer.Option(
        None, "--lang", help="py | R | sh (default: the file's suffix, else py)"
    ),
    question_id: str | None = typer.Option(None, "--question", help="the question this answers"),
    ins: list[str] = typer.Option(
        [],
        "--in",
        help="<name>=<$inputs.x | $steps.id.out>; repeatable; added to every delivered "
        "input, which is always bound (an upstream_* input only when named)",
    ),
    outs: list[str] = typer.Option([], "--out", help="<name>=<type>\\[/<format>]; repeatable"),
    env: str | None = typer.Option(None, "--env", help="the environment to run in"),
    seed: int | None = typer.Option(None, "--seed", help="recorded and passed as job seed"),
    reason: str | None = typer.Option(None, "--reason", help="why this code, in a sentence"),
    allow_local: bool = typer.Option(
        False, "--allow-local", help="development only: run under the local executor"
    ),
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
        detach_now(as_json)  # a script on stdin (`-`) is kept in the job's directory
        return
    override = Override.from_options(cpus, memory)
    text, suffix = read_script(script)
    chosen = lang or (suffix if suffix in EXEC_LANGS else None) or "py"
    project = Project.find()
    rc = open_for_questions(project)
    rc.resource_override = override
    if question_id is not None:
        question(rc, question_id)
    prop = propose_exec(
        rc,
        text,
        lang=chosen,
        bindings=parse_ins(ins),
        outputs=parse_outs(outs),
        env=env,
        seed=seed,
        rationale=reason,
        question_id=question_id,
        allow_local=allow_local,
    )
    status = prop.status
    message = ""
    if status == StepStatus.ADMISSIBLE:
        out = execute_engine(rc, prop)
        status, message = out.status, out.message
    nx = next_step(rc)
    ex = rc.store.one(
        "SELECT script_blob, network, env_status FROM executions WHERE action_id=?",
        (prop.action.action_id,),
    )
    artifacts = [
        dict(r)
        for r in rc.store.all(
            "SELECT artifact_id, name, kind, path FROM artifacts WHERE run_id=? AND step_id=? "
            "AND status='produced' ORDER BY rowid",
            (rc.run_id, prop.action.step_id),
        )
    ]
    payload = {
        "schema": "stringency.exec/1",
        "run_id": rc.run_id,
        "step_id": prop.action.step_id,
        "module": prop.plan.module.ref,
        "status": str(status),
        "question_id": question_id,
        "script_blob": ex["script_blob"] if ex else prop.plan.module.manifest.version,
        "seed": prop.action.parameters.get("seed"),
        "env": prop.plan.module.manifest.env,
        "env_status": ex["env_status"] if ex else None,
        "network": ex["network"] if ex else None,
        "timeout_s": prop.plan.timeout,
        "inputs": {k: str(v.job_value()) for k, v in prop.plan.inputs.items()},
        "artifacts": artifacts,
        "label": "untested",
        "next": nx.to_json(),
    }
    lines = [f"run {rc.run_id}", f"step {prop.action.step_id}: {prop.plan.module.ref} {status}"]
    if message:
        lines.append(message)
    for a in artifacts:
        lines.append(f"  {a['name']} ({a['kind']}): {a['artifact_id']}")
    if status == StepStatus.COMPLETED:
        lines.append(UNTESTED_LINE)
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
