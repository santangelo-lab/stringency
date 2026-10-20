"""`stringency audit [--json]`: the trace read back against its own history (backlog L51)."""

from __future__ import annotations

import typer

from stringency.audit import audit
from stringency.cli.common import emit, handle_errors
from stringency.project import Project


@handle_errors
def audit_verb(as_json: bool = typer.Option(False, "--json")) -> None:
    project = Project.find()
    findings = audit(project.store)
    text = (
        "trace audited: no disagreement between the rows and their events"
        if not findings
        else "\n".join(
            ["trace audited: " + f"{len(findings)} disagreement(s)"]
            + ["  " + f.line() for f in findings]
        )
    )
    emit(
        {"schema": "stringency.audit/1", "findings": [f.to_json() for f in findings]}, as_json, text
    )
    if findings:
        raise typer.Exit(code=1)
