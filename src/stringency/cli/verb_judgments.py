"""`stringency judgments --dispatch [--print] [--run <id>] [--json]` (L134 d): the requests of
the step that is dispatching. With `--print` every request's JSON is printed inline in one
payload, so an operator behind a slow connection fetches no file; without it, their paths. Reads
the trace and the dispatch directory; loads no plugin; writes nothing."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from stringency.cli.common import OUT_HELP, emit, handle_errors
from stringency.exit_codes import ConfigError, RefusedError
from stringency.harness.subagent import read_requests
from stringency.present import Site, step_dir


@handle_errors
def judgments(
    dispatch: bool = typer.Option(
        False, "--dispatch", help="the requests of the step that is dispatching"
    ),
    print_: bool = typer.Option(
        False, "--print", help="with --dispatch: every request's JSON inline in one payload"
    ),
    run_id: str | None = typer.Option(None, "--run", help="a run (default: the latest)"),
    out: Path | None = typer.Option(None, "--out", help=OUT_HELP),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not dispatch:
        raise ConfigError("judgments takes --dispatch (the requests of a dispatching step)")
    site = Site.find()
    if run_id is None:
        row = site.store.one(
            "SELECT run_id FROM runs WHERE kind = 'run' ORDER BY started DESC, rowid DESC LIMIT 1"
        )
        if row is None:
            raise RefusedError("no run has been opened; nothing is dispatching")
        run_id = str(row["run_id"])
    step = site.store.one(
        "SELECT step_id FROM steps WHERE run_id = ? AND status = 'dispatching' ORDER BY rowid "
        "LIMIT 1",
        (run_id,),
    )
    if step is None:
        raise RefusedError(f"no step of run {run_id} is dispatching")
    sid = str(step["step_id"])
    base = step_dir(site, run_id, sid)
    ddir = (base if base is not None else site.root / "runs" / run_id / sid) / "dispatch"
    requests = read_requests(ddir)
    manifest = ddir / "manifest.json"
    payload = {
        "schema": "stringency.dispatch/1",
        "run_id": run_id,
        "step_id": sid,
        "dispatch_dir": str(ddir),
        "manifest": json.loads(manifest.read_text()) if manifest.is_file() else None,
        "requests_inline": print_,
        "requests": requests if print_ else [r["request_file"] for r in requests],
        "responses_document": {"step_id": sid, "responses": f"<{len(requests)} replies, in order>"},
        "file_with": "stringency run --responses <file | -> --json",
    }
    human = (
        json.dumps(payload, indent=2, sort_keys=True)
        if print_
        else "\n".join(
            [f"step {sid} of run {run_id} is dispatching {len(requests)} request(s) in {ddir}"]
            + [f"  {r['request_file']}" for r in requests]
        )
    )
    emit(
        payload,
        as_json,
        human,
        out=out,
        summary=f"{len(requests)} request(s) of step {sid}" + (", inline" if print_ else ""),
    )
