"""`stringency review` (design 7.3, 14.1)."""

from __future__ import annotations

import json

import typer

from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.review import get_hold, queue, record_review, show


@handle_errors
def review(
    run_id: str | None = typer.Option(None, "--run"),
    show_only: bool = typer.Option(
        False, "--show", help="print the queue and every hold's evidence"
    ),
    verdict: str | None = typer.Option(
        None, "--verdict", help="accept | override | reject | defer"
    ),
    hold: str | None = typer.Option(
        None, "--hold", help="the hold a verdict applies to; alone, show that hold"
    ),
    item: str | None = typer.Option(None, "--item", help="informational; the hold names its item"),
    replicate: int | None = typer.Option(
        None, "--replicate", help="accept: which replicate's call"
    ),
    correction: str | None = typer.Option(
        None, "--correction", help="override: JSON with label (and ontology_id)"
    ),
    reason: str | None = typer.Option(None, "--reason"),
    attest: bool = typer.Option(
        False, "--attest", help="relayed: the person confirmed in the conversation"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if verdict is None and hold is not None:
        view = show(project, get_hold(project, hold))
        emit({"schema": "stringency.review_queue/1", "holds": [view.to_json()]}, as_json, view.text)
        return
    if verdict is None:
        holds = queue(project, run_id)
        views = [show(project, h) for h in holds] if (show_only or holds) else []
        payload = {"schema": "stringency.review_queue/1", "holds": [v.to_json() for v in views]}
        if not holds:
            emit(payload, as_json, "no unresolved holds")
            return
        human = f"{len(holds)} unresolved hold(s), oldest first\n\n" + "\n\n".join(
            v.text for v in views
        )
        emit(payload, as_json, human)
        return
    if hold is None:
        raise ConfigError("--verdict needs --hold <id>")
    corr = json.loads(correction) if correction else None
    result = record_review(
        project, hold, verdict, reason=reason, correction=corr, replicate=replicate, attest=attest
    )
    emit(
        result.to_json(),
        as_json,
        f"review {result.review_id}: {verdict} on hold {hold} via {result.via}"
        + (f"; step {result.step_status}, run {result.run_status}" if result.step_status else ""),
    )
