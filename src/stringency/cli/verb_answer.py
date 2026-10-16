"""`stringency answer --question <id> --cite <artifact id[:row[:column]]>... (--text <file> |
-) [--json]` (open_mode_plan.md 2.5): file the operator's reply against the cells it cites.
Exit 0 admissible, 12 blocked (the answer is kept, as a rejected proposal is), 15 config."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from stringency.answers import file_answer, parse_cite
from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError, Exit
from stringency.project import Project
from stringency.questions import open_for_questions


@handle_errors
def answer(
    question_id: str = typer.Option(..., "--question", help="the question this answers"),
    cites: list[str] = typer.Option(
        [],
        "--cite",
        help="<artifact id>[:<row>[:<column>]]; repeatable; the cells the numbers come from",
    ),
    text: str = typer.Option(..., "--text", help="a file holding the reply text, or - for stdin"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if text == "-":
        body = sys.stdin.read()
    else:
        p = Path(text)
        if not p.is_file():
            raise ConfigError(f"no text file at {p}")
        body = p.read_text()
    project = Project.find()
    rc = open_for_questions(project)
    res = file_answer(rc, question_id, body, [parse_cite(c) for c in cites])
    payload = {**res.to_json(), "run_id": rc.run_id}
    if res.status == "admissible":
        human = f"answer {res.answer_id} recorded ({res.status})\n{res.sentence}\n{res.qualifier}"
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
