from typer.testing import CliRunner

from stringency import __version__
from stringency.cli.app import app

VERBS = [
    "init",
    "run",
    "next",
    "propose",
    "submit",
    "status",
    "review",
    "deliver",
    "fork",
    "abandon",
    "lint",
    "controls",
    "policy",
    "plugins",
]


def test_import() -> None:
    assert __version__


def test_help_lists_every_verb() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for verb in VERBS:
        assert verb in result.output, verb
