"""`stringency submit <ticket> --outputs name=path... [--evidence path]...` (design 3.4, 14.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError
from stringency.notify import notify_after
from stringency.operator_exec.submit import submit as do_submit
from stringency.project import Project
from stringency.runloop import next_step
from stringency.runs import open_or_resume


@handle_errors
def submit(
    ticket: str = typer.Argument(...),
    outputs: list[str] = typer.Option([], "--outputs", help="name=path; repeatable"),
    evidence: list[Path] = typer.Option([], "--evidence", help="evidence file; repeatable"),
    command: str | None = typer.Option(
        None, "--command", help="the exact command you ran; recorded as reported"
    ),
    as_json: bool = typer.Option(False, "--json"),
    deliver: bool = typer.Option(
        False,
        "--deliver",
        help="deliver in this invocation when this submit completes the run (backlog J2)",
    ),
    failed: bool = typer.Option(
        False, "--failed", help="the external run failed; close the attempt with --reason"
    ),
    reason: str | None = typer.Option(None, "--reason", help="--failed: what happened"),
    exit_code: int = typer.Option(1, "--exit-code", help="--failed: the reported exit code"),
) -> None:
    project = Project.find()
    rc = open_or_resume(project)
    if failed:
        from stringency.operator_exec.submit import submit_failed

        if not reason:
            raise ConfigError("--failed needs --reason")
        out = submit_failed(
            rc, ticket, reason=reason, exit_code=exit_code, evidence=list(evidence), command=command
        )
        nx = next_step(rc)
        refresh_if_present(project.root)
        notify_after(project, run_id=rc.run_id, nx=nx)
        emit(
            {
                "schema": "stringency.submit/1",
                "run_id": rc.run_id,
                "step_id": out.step_id,
                "status": str(out.status),
                "next": nx.to_json(),
            },
            as_json,
            f"run {rc.run_id}\n{out.message}\n{nx.message}",
        )
        if nx.exit_code:
            raise typer.Exit(code=nx.exit_code)
        return
    outs: dict[str, Path] = {}
    for o in outputs:
        if "=" not in o:
            raise ConfigError(f"--outputs expects name=path, got {o!r}")
        k, _, v = o.partition("=")
        outs[k] = Path(v)
    out = do_submit(rc, ticket, outs, list(evidence), command=command)
    nx = next_step(rc)
    refresh_if_present(project.root)
    payload: dict[str, Any] = {
        "schema": "stringency.submit/1",
        "run_id": rc.run_id,
        "step_id": out.step_id,
        "status": str(out.status),
        "next": nx.to_json(),
    }
    human = f"run {rc.run_id}\n{out.message}\n{nx.message}"
    # the same guard as `run --deliver`: a last operator ticket completes the run inside submit
    if deliver and nx.kind == "completed" and rc.run["status"] == "completed":
        from stringency.deliver import deliver as do_deliver

        d = do_deliver(rc)
        payload["delivery"] = {
            "delivery_id": d.delivery_id,
            "path": str(d.path),
            "files": [str(f) for f in d.files],
        }
        human += f"\ndelivered run {rc.run_id} to {d.path}\n{len(d.files)} file(s)"
    notify_after(project, run_id=rc.run_id, nx=nx, delivery=payload.get("delivery"))
    emit(payload, as_json, human)
    if nx.exit_code:
        raise typer.Exit(code=nx.exit_code)
