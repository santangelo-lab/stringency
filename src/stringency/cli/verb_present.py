"""`stringency present [--run <id>] [--hold <id>] [--answer <id> [--chat] [--details]]
[--answers] [--skills-dir <dir>] [--json]` (design 14.3; `--chat`, L141)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import emit, handle_errors
from stringency.present import (
    Site,
    present_answer,
    present_answers,
    present_hold,
    present_run,
    record_presented,
    render_markdown,
)


@handle_errors
def present(
    run_id: str | None = typer.Option(None, "--run", help="a completed run (default: the latest)"),
    hold_id: str | None = typer.Option(
        None, "--hold", help="an open hold (default: the newest open one)"
    ),
    answer_id: str | None = typer.Option(None, "--answer", help="open mode: one answer"),
    answers: bool = typer.Option(False, "--answers", help="open mode: list every answer"),
    details: bool = typer.Option(
        False,
        "--details",
        help="with --answer: add the qualifier line, the cells checked, every decision, the ids",
    ),
    chat: bool = typer.Option(
        False,
        "--chat",
        help=(
            "with --answer: the block to paste under the reply: the cited rows, the figures, "
            "the label sentence; the full answer view only with --details"
        ),
    ),
    skills_dir: Path | None = typer.Option(
        None,
        "--skills-dir",
        help="read skills/<pipeline>.yml from here instead of the project's method clone",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Site.find()
    if answers:
        payload = present_answers(project, run_id)
    elif answer_id is not None:
        payload = present_answer(project, answer_id, skills_dir, details=details, chat=chat)
    elif hold_id is not None or (run_id is None and _has_open_hold(project)):
        payload = present_hold(project, hold_id, skills_dir)
    else:
        payload = present_run(project, run_id, skills_dir)
    if payload.get("kind") in ("hold", "run"):
        record_presented(project, payload)  # one `presented` event per rendering (L62)
    emit(payload, as_json, render_markdown(payload))


def _has_open_hold(project: Site) -> bool:
    n = project.store.scalar(
        "SELECT COUNT(*) FROM holds WHERE resolved_by_review IS NULL AND resolved_via IS NULL"
    )
    return bool(n)
