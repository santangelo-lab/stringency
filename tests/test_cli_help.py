"""Every verb's help renders (backlog L43: `exec --help` crashed on rich markup in an option's
help text, 2026-10-20)."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from stringency.cli.app import app


def test_every_verb_help_renders() -> None:
    group = typer.main.get_command(app)
    verbs = sorted(getattr(group, "commands", {}).keys())
    assert "exec" in verbs and len(verbs) > 10, verbs
    runner = CliRunner()
    for v in verbs:
        r = runner.invoke(app, [v, "--help"])
        assert r.exit_code == 0 and r.exception is None, (v, r.output[-300:], repr(r.exception))
