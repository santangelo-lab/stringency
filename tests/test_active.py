"""The engine's mark while it executes a step, and the console's stale rule that reads it
(backlog L15: a long clustering step was marked stale while it computed)."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from stringency import active
from stringency.console import driver
from stringency.project import Project
from tests.conftest import InitFn
from tests.test_run import MOCK, cli, confirmed

STEP = {"step_id": "02_summarize", "title": "Summarize", "status": "running"}


def test_mark_lives_for_the_block_and_names_this_process(tmp_path: Path) -> None:
    p = active.mark_path(tmp_path, "R1")
    with active.executing(tmp_path, "R1", "02_summarize"):
        mark = json.loads(p.read_text())
        assert mark["step_id"] == "02_summarize" and mark["host"] == socket.gethostname()
        assert active.engine_alive(tmp_path, "R1", "02_summarize") is True
    assert not p.exists()
    with pytest.raises(RuntimeError), active.executing(tmp_path, "R1", "02_summarize"):
        raise RuntimeError("the step failed")
    assert not p.exists()  # removed however the block ends


def test_engine_run_leaves_no_mark(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "run", env=MOCK)
    assert r.exit_code == 0, r.output
    assert not list((p.root / "runs").rglob(active.MARK))


def _write_mark(root: Path, run_id: str, pid: int, host: str | None = None) -> None:
    m = active.mark_path(root, run_id)
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(
        json.dumps({"pid": pid, "host": host or socket.gethostname(), "step_id": "02_summarize"})
    )


def test_driver_reads_the_mark_not_the_clock(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    assert cli(p, "run", env=MOCK).exit_code == 0
    run = p.store.one("SELECT * FROM runs ORDER BY started DESC LIMIT 1")
    assert run is not None
    rid = run["run_id"]
    hours_later = datetime.now(UTC) + timedelta(hours=3)

    # alive: a long quiet step is computing, not stale
    _write_mark(p.root, rid, active.os.getpid())
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=hours_later, root=p.root)
    assert d["engine"] == "computing" and not d["stale"]

    # gone: stale at once, whatever the clock says
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _write_mark(p.root, rid, dead.pid)
    soon = datetime.now(UTC) + timedelta(minutes=1)
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=soon, root=p.root)
    assert d["engine"] == "gone" and d["stale"]

    # another host: the console cannot tell, so the time rule applies
    _write_mark(p.root, rid, active.os.getpid(), host="elsewhere.invalid")
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=hours_later, root=p.root)
    assert d["engine"] == "" and d["stale"]
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=soon, root=p.root)
    assert not d["stale"]


def test_without_a_mark_a_run_process_in_the_project_counts(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runs opened by an engine that writes no mark (0.2.10): a `stringency run` working in the
    project directory is the evidence; none found leaves the time rule in charge."""
    p: Project = confirmed(make_project, pipeline="toy-engine", execution="engine")
    assert cli(p, "run", env=MOCK).exit_code == 0
    run = p.store.one("SELECT * FROM runs ORDER BY started DESC LIMIT 1")
    assert run is not None
    later = datetime.now(UTC) + timedelta(hours=3)
    assert active.run_process_in(p.root) is None
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=later, root=p.root)
    assert d["stale"] and d["engine"] == ""
    monkeypatch.setattr(active, "run_process_in", lambda root: True)
    monkeypatch.setattr("stringency.console.engine_alive", active.engine_alive)
    d = driver(p.store.conn, run, STEP, "toy-engine", {}, now=later, root=p.root)
    assert d["engine"] == "computing" and not d["stale"]
