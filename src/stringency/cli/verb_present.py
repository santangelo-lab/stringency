"""`stringency present [--run <id>] [--hold <id>] [--step <id>] [--answer <id> [--chat] [--details]]
[--answers] [--skills-dir <dir>] [--out <file>] [--json]` (design 14.3; `--chat`, L141).

`--step` (L134 a) renders a completed step of a run in any state and records it: a `presented`
run event and a `rendered` step event on that step (`present.record_rendered`)."""

from __future__ import annotations

from pathlib import Path

import typer

from stringency.cli.common import OUT_HELP, emit, handle_errors
from stringency.present import (
    Site,
    present_answer,
    present_answers,
    present_completed_step,
    present_hold,
    present_run,
    record_presented,
    record_rendered,
    render_markdown,
)


@handle_errors
def present(
    run_id: str | None = typer.Option(None, "--run", help="a completed run (default: the latest)"),
    hold_id: str | None = typer.Option(
        None, "--hold", help="an open hold (default: the newest open one)"
    ),
    step_id: str | None = typer.Option(
        None,
        "--step",
        help="a completed step of the run (default: the latest run), even while the run is held",
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
    out: Path | None = typer.Option(None, "--out", help=OUT_HELP),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Site.find()
    if step_id is not None:
        payload = present_completed_step(project, run_id, step_id, skills_dir)
        record_presented(project, payload)  # the hold's evidence line reads it (L62)
        record_rendered(project, payload)  # the step's own mark, `rendered` (L134)
        emit(payload, as_json, render_markdown(payload), out=out, summary=_summary(payload))
        return
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
    emit(payload, as_json, render_markdown(payload), out=out, summary=_summary(payload))


def _summary(payload: dict[str, object]) -> str:
    """The one line printed with `--out`."""
    sections = payload.get("sections")
    n = len(sections) if isinstance(sections, list) else 0
    what = payload.get("kind")
    ident = payload.get("hold_id") or payload.get("step_id") or payload.get("answer_id") or ""
    return f"present {what} {ident}: {n} section(s)".replace("  ", " ")


def _has_open_hold(project: Site) -> bool:
    n = project.store.scalar(
        "SELECT COUNT(*) FROM holds WHERE resolved_by_review IS NULL AND resolved_via IS NULL"
    )
    return bool(n)
