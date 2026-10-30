"""`stringency ask "<text>" [--wants "<quantity>"] [--suggested] [--json]` (open_mode_plan.md
2.3; L139): file a person's question on the open run, with the quantity that would answer it.
Prints the question id, what it wants, and the tools that could answer it."""

from __future__ import annotations

import typer

from stringency.board import refresh_if_present
from stringency.cli.common import emit, handle_errors
from stringency.project import Project
from stringency.questions import file_question, open_for_questions


@handle_errors
def ask(
    text: str = typer.Argument(..., help="the person's words, verbatim"),
    suggested: bool = typer.Option(
        False,
        "--suggested",
        help="a path the operator proposed before the switch and the person picked",
    ),
    wants: str | None = typer.Option(
        None,
        "--wants",
        help="the quantity that would answer it, in one phrase (a tool's output is compared "
        "with it by its --gives)",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    rc = open_for_questions(project)
    q = file_question(rc, text, origin="suggested" if suggested else "person", wants=wants)
    tools = [
        {"name": m.manifest.name, "ref": m.ref, "operation": m.manifest.operation}
        for m in project.tools()
    ]
    payload = {
        "schema": "stringency.ask/1",
        "run_id": rc.run_id,
        "question_id": q["question_id"],
        "seq": q["seq"],
        "origin": q["origin"],
        "text": q["text"],
        "wants": q["wants"],
        "tools": tools,
    }
    human = (
        f"run {rc.run_id}\nquestion {q['question_id']} ({q['origin']}, #{q['seq']}): {q['text']}\n"
        f"wants: {q['wants'] or 'not said'}\n"
        "tools: " + (", ".join(t["name"] for t in tools) or "none")
    )
    refresh_if_present(project.root)
    emit(payload, as_json, human)
