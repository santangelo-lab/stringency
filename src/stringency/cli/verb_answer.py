"""`stringency answer --question <id> --cite <artifact id[:row[:column]]>... [--figure <artifact
id>]... (--text <file> | -) [--json]` (open_mode_plan.md 2.5): file the operator's reply against
the cells it cites, with the figures that illustrate it attached (L143). Exit 0 admissible, 12
blocked (the answer is kept, as a rejected proposal is), 15 config."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from stringency.answers import file_answer, file_unanswerable, parse_cite
from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, Exit
from stringency.project import Project
from stringency.questions import open_for_questions
from stringency.report import write_open_delivery


@handle_errors
def answer(
    question_id: str = typer.Option(..., "--question", help="the question this answers"),
    cites: list[str] = typer.Option(
        [],
        "--cite",
        help=(
            "<artifact id>[:<row>[:<column>]], the row by its key (<k1>|<k2> as present "
            "prints it); repeatable; the cells the numbers come from"
        ),
    ),
    figures: list[str] = typer.Option(
        [],
        "--figure",
        help=(
            "<artifact id> of a figure that illustrates this answer; repeatable; attached to "
            "the answer with its own label, not filed as an answer of its own"
        ),
    ),
    text: str | None = typer.Option(
        None, "--text", help="a file holding the reply text, or - for stdin"
    ),
    cannot: bool = typer.Option(
        False, "--cannot", help="the question cannot be answered from the delivery (with --reason)"
    ),
    reason: str | None = typer.Option(None, "--reason", help="with --cannot: why, one sentence"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if cannot:
        if text is not None or cites or figures:
            raise ConfigError("--cannot takes --reason only, no --text, --cite or --figure")
        project = Project.find()
        rc = open_for_questions(project)
        out = file_unanswerable(rc, question_id, reason or "")
        write_open_delivery(rc)
        refresh_if_present(project.root)
        emit(
            {**out, "run_id": rc.run_id},
            as_json,
            f"answer {out['answer_id']} recorded (unanswerable): {out['reason']}",
        )
        return
    if text is None:
        raise ConfigError("answer needs --text <file|-> (or --cannot --reason)")
    if text == "-":
        body = sys.stdin.read()
    else:
        p = Path(text)
        if not p.is_file():
            raise ConfigError(f"no text file at {p}")
        body = p.read_text()
    project = Project.find()
    rc = open_for_questions(project)
    res = file_answer(rc, question_id, body, [parse_cite(c) for c in cites], list(figures))
    payload = {**res.to_json(), "run_id": rc.run_id}
    if res.status == "admissible":
        # every admissible answer is in deliver/<run>/ the moment it exists (2026-10-19)
        d = write_open_delivery(rc)
        mine = next((e for e in d.answers if e["answer_id"] == res.answer_id), None)
        payload["report"] = {
            "path": str(d.path / "report.md"),
            "file": mine["file"] if mine else None,
        }
        figs = "".join(
            f"figure {f['name']} ({f['step_id']}): {f['label_line']}\n" for f in res.figures
        )
        human = (
            f"answer {res.answer_id} recorded ({res.status})\n{res.sentence}\n{res.qualifier}\n"
            f"{figs}in the report as {mine['file'] if mine else '?'} ({d.path / 'report.md'})"
        )
    else:
        human = (
            f"answer {res.answer_id} blocked: "
            + "; ".join(r.line() for r in res.gate.blocked)
            + "\nfix the text, never a number, never a table; the cited cells are in the JSON"
        )
    refresh_if_present(project.root)
    emit(payload, as_json, human)
    if res.status != "admissible":
        raise typer.Exit(code=int(Exit.REJECTED))
