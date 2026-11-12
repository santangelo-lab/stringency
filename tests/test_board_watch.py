"""K4: the board opens with the newest change over every project, and `board --watch` shows
it again when a project changed."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from stringency.board import BOARD_FILE, board, project_entry, watch
from stringency.cli.app import app
from tests.conftest import InitFn, accept_hold
from tests.test_board_present import _delivered

runner = CliRunner()


def test_the_board_names_the_newest_change(make_project: InitFn, tmp_path: Path) -> None:
    p, _, _ = _delivered(make_project)
    e = project_entry(p.root)
    assert e["latest_change"]["what"] == "the run: delivered"
    _, text = board(tmp_path)
    head = text.split("| project |")[0]
    assert f"Newest change: {p.root.name}, " in head and ": the run: delivered." in head


def test_a_project_with_nothing_yet_has_no_line(make_project: InitFn, tmp_path: Path) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    assert project_entry(p.root)["latest_change"] is None
    assert "Newest change" not in board(tmp_path)[1]
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    assert project_entry(p.root)["latest_change"]["what"] == "accept on a confirm hold"


def test_watch_shows_the_board_again_only_when_a_project_changed(
    make_project: InitFn, tmp_path: Path
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    shown: list[str] = []
    reads = {"n": 0}

    def between(_: float) -> None:
        reads["n"] += 1
        if reads["n"] == 2:  # after the second read, the owner confirms the plan
            accept_hold(p.store, p.confirm_hold()["hold_id"])

    n = watch(tmp_path, interval=5, write=True, show=shown.append, cycles=4, sleep=between)
    assert n == 2 and len(shown) == 2 and reads["n"] == 3
    assert "Its plan waits for" in shown[0] and "accept on a confirm hold" in shown[1]
    assert (tmp_path / BOARD_FILE).read_text() == shown[1]


def test_watch_refuses_json_and_a_short_interval(tmp_path: Path) -> None:
    r = runner.invoke(app, ["board", str(tmp_path), "--watch", "--json"])
    assert r.exit_code == 15 and "--json" in r.output
    r = runner.invoke(app, ["board", str(tmp_path), "--watch", "--interval", "0.5"])
    assert r.exit_code == 15 and "--interval" in r.output
