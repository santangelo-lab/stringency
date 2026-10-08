"""`stringency run` (design 14.1, 14.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.deliver import deliver as do_deliver
from stringency.exit_codes import ConfigError
from stringency.judgment import check_responses, check_text
from stringency.notify import notify_after
from stringency.project import Project
from stringency.runloop import Next, file_responses, run_loop
from stringency.runs import RunContext, latest_run, load_run, open_or_resume


def completed_line(nx: Next) -> str:
    """One line naming the steps this invocation completed on the engine, or nothing (I8).
    Reads `Next.detail["completed_steps"]`, which `run_loop` fills from the steps table."""
    done = nx.detail.get("completed_steps") or []
    return f"completed by the engine: {', '.join(done)}\n" if done else ""


def read_responses(source: str) -> Any:
    """The `--responses` document: a file path, or `-` for stdin."""
    text = sys.stdin.read() if source == "-" else Path(source).read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(f"--responses: not JSON ({e})") from None


def _latest(project: Project) -> RunContext:
    """The latest run, loaded without opening or resuming it (the check writes nothing)."""
    row = latest_run(project.store)
    if row is None:
        raise ConfigError("no run to check responses against")
    return load_run(project, row["run_id"])


@handle_errors
def run(
    until: str | None = typer.Option(None, "--until", help="stop after this step"),
    allow_dirty: str | None = typer.Option(
        None, "--allow-dirty", help="reason to run with uncommitted method changes"
    ),
    new: bool = typer.Option(False, "--new", help="open a new run when the latest is closed"),
    responses: str | None = typer.Option(
        None,
        "--responses",
        help="file (or -) with one JSON document {step_id, responses: [...]} for the dispatching step",
    ),
    deliver: bool = typer.Option(
        False, "--deliver", help="deliver in this invocation when the run completes"
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="with --responses: check the responses as filing would, and file nothing",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if check:
        if responses is None:
            raise ConfigError("--check needs --responses <file>")
        res = check_responses(_latest(project), read_responses(responses))
        emit({"schema": "stringency.response_check/1", **res}, as_json, check_text(res))
        return
    rc = open_or_resume(project, allow_dirty=allow_dirty, new=new)
    human_prefix = ""
    if responses is not None:
        ddir = file_responses(rc, read_responses(responses))
        human_prefix = f"responses filed in {ddir}\n"
    nx = run_loop(rc, until=until)
    payload = {**nx.to_json(), "run_id": rc.run_id, "run_status": rc.run["status"]}
    human = f"run {rc.run_id}\n{human_prefix}{completed_line(nx)}{nx.message}"
    if deliver and nx.kind == "completed" and rc.run["status"] == "completed":
        d = do_deliver(rc)
        payload["delivery"] = {
            "delivery_id": d.delivery_id,
            "path": str(d.path),
            "files": d.files,
        }
        human += f"\ndelivered run {rc.run_id} to {d.path}\n{len(d.files)} file(s)"
    refresh_if_present(project.root)
    notify_after(project, run_id=rc.run_id, nx=nx, delivery=payload.get("delivery"))
    emit(payload, as_json, human)
    if nx.exit_code:
        raise typer.Exit(code=nx.exit_code)
