"""`stringency finding <answer id>... [--reason "<the person's words>"] [--remove] [--json]`
(open mode, the report; 2026-10-19): mark answers as findings, the ones `report.md` leads
with, or unmark them. Recorded append-only with who, how and when; the report is rewritten.
Exit 0; 15 when an id is not an admissible answer of the open run."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.findings import mark
from stringency.project import Project
from stringency.questions import open_for_questions
from stringency.report import write_open_delivery


@handle_errors
def finding(
    answer_ids: list[str] = typer.Argument(..., help="admissible answers of the open run"),
    reason: str | None = typer.Option(
        None, "--reason", help="the person's words for the choice, when they gave any"
    ),
    remove: bool = typer.Option(False, "--remove", help="unmark instead"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    rc = open_for_questions(project)
    results = mark(rc, list(answer_ids), reason=reason, remove=remove)
    d = write_open_delivery(rc)
    payload = {
        "schema": "stringency.finding/1",
        "run_id": rc.run_id,
        "results": results,
        "report": str(d.path / "report.md"),
        "findings": [e["answer_id"] for e in d.answers if e["finding"]],
    }
    lines = []
    for r in results:
        what = "unmarked" if r["action"] == "unmark" else "marked as a finding"
        if not r["changed"]:
            what = "already " + ("not a finding" if r["action"] == "unmark" else "a finding")
        lines.append(f"question {r['question_seq']} ({r['answer_id']}): {what}")
    lines.append(
        f"report rewritten: {d.path / 'report.md'} ({len(payload['findings'])} finding(s) of "
        f"{len(d.answers)} answer(s))"
    )
    refresh_if_present(project.root)
    emit(payload, as_json, "\n".join(lines))
