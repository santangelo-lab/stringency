"""The `stringency` console script. Verbs per design 14.1."""

from __future__ import annotations

import typer

from stringency import __version__
from stringency.cli import (
    verb_abandon,
    verb_board,
    verb_controls,
    verb_declare,
    verb_deliver,
    verb_fork,
    verb_init,
    verb_lint,
    verb_next,
    verb_plugins,
    verb_policy,
    verb_present,
    verb_propose,
    verb_review,
    verb_run,
    verb_status,
    verb_submit,
)

app = typer.Typer(
    name="stringency",
    help="Admissibility gates and provenance for agent-assisted analysis pipelines.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.command("init")(verb_init.init)
app.command("declare")(verb_declare.declare)
app.command("run")(verb_run.run)
app.command("next")(verb_next.next_)
app.command("propose")(verb_propose.propose)
app.command("submit")(verb_submit.submit)
app.command("status")(verb_status.status)
app.command("board")(verb_board.board_)
app.command("present")(verb_present.present)
app.command("review")(verb_review.review)
app.command("deliver")(verb_deliver.deliver)
app.command("fork")(verb_fork.fork)
app.command("abandon")(verb_abandon.abandon)
app.command("lint")(verb_lint.lint)
app.add_typer(verb_controls.app, name="controls")
app.add_typer(verb_policy.app, name="policy")
app.add_typer(verb_plugins.app, name="plugins")


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True),
) -> None:
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
