"""`<project>/README.md` (2026-10-19): written by the engine after every verb that changes the
trace, it says what the project is and what every path holds; one a person wrote is never
overwritten. The open project's README is checked in `test_open_mode.py`."""

from __future__ import annotations

from pathlib import Path

from stringency.readme import MARKER, write_readme
from tests.conftest import InitFn
from tests.test_open_init import delivered_process


def test_pipeline_readme_names_the_steps_runs_and_layout(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    out = write_readme(up.root)
    assert out == up.root / "README.md"
    text = out.read_text()
    assert text.startswith(MARKER)
    assert "A stringency pipeline project: pipeline `toy-process`" in text
    assert "| `01_filter` |" in text
    run_id = up.store.scalar("SELECT run_id FROM runs WHERE kind='run'")
    assert f"| `{run_id}` |" in text and f"`deliver/{run_id}/`" in text
    assert "`prov/run.db`" in text and "`runs/<run>/<step>/`" in text
    # a file the project does not have is left out of the table
    assert "`brief.md`" not in text


def test_a_readme_a_person_wrote_is_kept(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    mine = up.root / "README.md"
    mine.write_text("# notes of my own\n")
    assert write_readme(up.root) is None
    assert mine.read_text() == "# notes of my own\n"
