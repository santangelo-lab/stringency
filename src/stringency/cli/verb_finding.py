"""`stringency finding <answer id>... [--reason "<the person's words>"] [--order <n>] [--under
"<heading>"] [--remove] [--json]` (open mode, the report; 2026-10-19; L144): mark answers as
findings, the ones `report.md` leads with, or unmark them; `--order` sets their place in the
report (n for the first id, n+1 for the next; 0 unsets) and `--under` groups them under a
heading in the person's words ("" removes it). An answer named with `--order` or `--under` is
marked first when it is not a finding yet. Recorded append-only with who, how and when; the
report is rewritten. Exit 0; 15 when an id is not an admissible answer of the open run."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.exit_codes import ConfigError
from stringency.findings import mark, place
from stringency.project import Project
from stringency.questions import open_for_questions
from stringency.report import write_open_delivery


@handle_errors
def finding(
    answer_ids: list[str] = typer.Argument(..., help="admissible answers of the open run"),
    reason: str | None = typer.Option(
        None, "--reason", help="the person's words for the choice, when they gave any"
    ),
    order: int | None = typer.Option(
        None,
        "--order",
        help="the place in the report the person gave: n for the first id, n+1 for the next; 0 unsets",
    ),
    under: str | None = typer.Option(
        None, "--under", help='a heading in the person\'s words to group these under; "" removes it'
    ),
    remove: bool = typer.Option(False, "--remove", help="unmark instead"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if remove and (order is not None or under is not None):
        raise ConfigError("--remove takes no --order and no --under")
    project = Project.find()
    rc = open_for_questions(project)
    results = mark(rc, list(answer_ids), reason=reason, remove=remove)
    placed = place(rc, list(answer_ids), order=order, heading=under)
    d = write_open_delivery(rc)
    payload = {
        "schema": "stringency.finding/1",
        "run_id": rc.run_id,
        "results": results,
        "placed": placed,
        "report": str(d.path / "report.md"),
        "findings": [e["answer_id"] for e in d.answers if e["finding"]],
    }
    lines = []
    where = {p["answer_id"]: p for p in placed}
    for r in results:
        what = "unmarked" if r["action"] == "unmark" else "marked as a finding"
        if not r["changed"]:
            what = "already " + ("not a finding" if r["action"] == "unmark" else "a finding")
        if r["action"] == "mark" and r["figures"]:
            what += ", with figure " + ", ".join(f["name"] for f in r["figures"])
        p = where.get(r["answer_id"])
        if p is not None:
            if "order" in p:
                what += f"; place {p['order']}" if p["order"] else "; place unset"
            if "heading" in p:
                what += f'; under "{p["heading"]}"' if p["heading"] else "; no heading"
        lines.append(f"question {r['question_seq']} ({r['answer_id']}): {what}")
    lines.append(
        f"report rewritten: {d.path / 'report.md'} ({len(payload['findings'])} finding(s) of "
        f"{len(d.answers)} answer(s))"
    )
    refresh_if_present(project.root)
    emit(payload, as_json, "\n".join(lines))
