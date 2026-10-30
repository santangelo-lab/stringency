"""`stringency run` (design 14.1, 14.2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import DETACH_HELP, OUT_HELP, detach_now, emit, handle_errors
from stringency.deliver import deliver as do_deliver
from stringency.exit_codes import ConfigError, RefusedError
from stringency.harness.subagent import read_requests
from stringency.judgment import check_responses, check_text
from stringency.notify import notify_after
from stringency.project import Project
from stringency.resources import Override
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
    cpus: int | None = typer.Option(
        None, "--cpus", help="CPUs for each step this invocation runs, within the policy's cap"
    ),
    memory: str | None = typer.Option(
        None,
        "--memory",
        help="memory in GB for each step this invocation runs (64 or 64GB), within the policy's cap",
    ),
    print_requests: bool = typer.Option(
        False,
        "--print-requests",
        help="at a dispatch (exit 20): every request's JSON inline in the payload",
    ),
    detach: bool = typer.Option(False, "--detach", help=DETACH_HELP),
    out: Path | None = typer.Option(None, "--out", help=OUT_HELP),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if detach:
        detach_now(as_json)
        return
    override = Override.from_options(cpus, memory)
    project = Project.find()
    if project.open_ended:
        raise RefusedError(
            "run is not a verb of an open project: there is no declared topology to run; "
            "`stringency ask` files a question and `call` or `exec` answers it one step at a time"
        )
    if check:
        if responses is None:
            raise ConfigError("--check needs --responses <file>")
        res = check_responses(_latest(project), read_responses(responses))
        emit({"schema": "stringency.response_check/1", **res}, as_json, check_text(res), out=out)
        return
    rc = open_or_resume(project, allow_dirty=allow_dirty, new=new)
    rc.resource_override = override
    for c in rc.plugin_changes:
        sys.stderr.write(
            f"note: plugin {c['plugin']} is {c['now'] or 'not installed'} now; it was "
            f"{c['at_init']} when the project was initialised (recorded in the run's captures)\n"
        )
    human_prefix = ""
    if responses is not None:
        ddir = file_responses(rc, read_responses(responses))
        human_prefix = f"responses filed in {ddir}\n"
    nx = run_loop(rc, until=until)
    payload = {**nx.to_json(), "run_id": rc.run_id, "run_status": rc.run["status"]}
    if print_requests and nx.kind == "dispatching":
        # every request inline, so an operator behind a slow connection fetches nothing (L134 d)
        payload["requests"] = read_requests(Path(nx.detail["dispatch_dir"]))
        payload["requests_inline"] = True
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
    emit(
        payload, as_json, human, out=out, summary=nx.message.splitlines()[0] if nx.message else None
    )
    if nx.exit_code:
        raise typer.Exit(code=nx.exit_code)
