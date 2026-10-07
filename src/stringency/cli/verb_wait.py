"""`stringency wait [--hold <id> | --run <id>] [--timeout <s>] [--json]` (design 14.1).

Blocks until the hold is resolved or withdrawn, or the run changes (exit 0), or the timeout
passes (exit 10). With neither option it waits on the latest run. Reads the trace only; needs
no plugin, so it works from any install.
"""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, RefusedError
from stringency.runs import latest_run
from stringency.wait import POLL_SECONDS, open_read_only, wait_hold, wait_run


def _project_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for cand in (cur, *cur.parents):
        if (cand / "stringency.yml").exists():
            return cand
    raise ConfigError("no stringency project found here or in a parent directory")


@handle_errors
def wait(
    hold: str | None = typer.Option(None, "--hold", help="wait until this hold is answered"),
    run: str | None = typer.Option(None, "--run", help="wait until this run changes"),
    timeout: float | None = typer.Option(
        None, "--timeout", help="give up after this many seconds (exit 10)"
    ),
    poll: float = typer.Option(POLL_SECONDS, "--poll", hidden=True),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if hold and run:
        raise ConfigError("wait takes --hold or --run, not both")
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
