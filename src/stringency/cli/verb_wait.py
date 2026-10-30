"""`stringency wait [--hold <id> | --run <id> | --job <id>] [--timeout <s>] [--json]` (design
14.1).

Blocks until the hold is resolved or withdrawn, or the run changes (exit 0), or the timeout
passes (exit 10). With no option it waits on the latest run. `--job` (L134) waits for a verb
started with `--detach` to exit and then prints what it printed, with its exit code. Reads the
trace and the job's files only; needs no plugin, so it works from any install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, RefusedError
from stringency.jobs import find_root, wait_job
from stringency.runs import latest_run
from stringency.wait import POLL_SECONDS, open_read_only, wait_hold, wait_run


def _project_root(start: Path | None = None) -> Path:
    return find_root(start)


@handle_errors
def wait(
    hold: str | None = typer.Option(None, "--hold", help="wait until this hold is answered"),
    run: str | None = typer.Option(None, "--run", help="wait until this run changes"),
    job: str | None = typer.Option(
        None,
        "--job",
        help="wait until a verb started with --detach exits, then print what it printed",
    ),
    timeout: float | None = typer.Option(
        None, "--timeout", "--for", help="give up after this many seconds (exit 10)"
    ),
    poll: float = typer.Option(POLL_SECONDS, "--poll", hidden=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if sum(x is not None for x in (hold, run, job)) > 1:
        raise ConfigError("wait takes one of --hold, --run or --job")
    if job is not None:
        _wait_job(job, timeout, as_json)
        return
    store = open_read_only(_project_root())
    try:
        if hold:
            res = wait_hold(store, hold, timeout=timeout, poll=poll)
        else:
            if run is None:
                row = latest_run(store)
                if row is None:
                    raise RefusedError("no run has been opened; nothing to wait on")
                run = str(row["run_id"])
            res = wait_run(store, run, timeout=timeout, poll=poll)
    finally:
        store.close()
    emit(res.to_json(), as_json, res.message)
    if res.exit_code:
        raise typer.Exit(code=res.exit_code)


def _wait_job(job: str, timeout: float | None, as_json: bool) -> None:
    """Print the job's saved output (its stdout to stdout, its stderr to stderr) and exit with
    its exit code; at the timeout print the job's state (`running`, exit 10)."""
    res = wait_job(_project_root(), job, timeout=timeout, poll=min(POLL_SECONDS, 1.0))
    if res.state == "exited":
        if res.stdout:
            sys.stdout.write(res.stdout)
        if res.stderr:
            sys.stderr.write(res.stderr)
    else:
        detail = res.detail or {}
        emit(
            {"schema": "stringency.job/1", "state": res.state, **detail},
            as_json,
            detail.get("message"),
        )
        if res.state == "lost" and res.stderr:
            sys.stderr.write(res.stderr)
    if res.exit_code:
        raise typer.Exit(code=res.exit_code)
