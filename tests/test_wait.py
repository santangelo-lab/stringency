"""`stringency wait` (design 14.1, 2026-10-07): blocks until a hold is answered or a run changes."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from stringency.db.store import Store
from stringency.project import Project
from stringency.review import queue
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli

POLL = ("--poll", "0.05")


@pytest.fixture
def held(make_project: InitFn) -> Project:
    """A toy-engine project with open item holds on 03_label (split.yml)."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", env={**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")})
    assert r.exit_code == 10, r.output
    return p


def later(p: Project, act: Callable[[Store], object], delay: float = 0.3) -> threading.Thread:
    """Write to the trace from another connection while `wait` polls."""

    def go() -> None:
        time.sleep(delay)
        store = Store.open(p.root / "prov" / "run.db", create=False)
        try:
            act(store)
        finally:
            store.close()

    t = threading.Thread(target=go)
    t.start()
    return t


def test_wait_hold_returns_the_review(held: Project) -> None:
    hid = queue(held)[0]["hold_id"]
    t = later(held, lambda s: accept_hold(s, hid, reviewer="alice", reason="label A is right"))
    r = cli(held, "wait", "--hold", hid, *POLL, "--timeout", "20", "--json")
    t.join()
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["schema"] == "stringency.wait/1" and out["event"] == "resolved"
    assert out["hold_id"] == hid and out["step_id"] == "03_label"
    assert out["review"]["verdict"] == "accept" and out["review"]["reviewer"] == "alice"
    assert out["review"]["reason"] == "label A is right" and out["review"]["via"] == "tty"
    # an already-resolved hold returns at once, in words without --json
    r = cli(held, "wait", "--hold", hid)
    assert r.exit_code == 0
    assert r.output.strip() == f'hold {hid} resolved: accept by alice via tty: "label A is right"'


def test_wait_hold_timeout_exits_10_and_writes_nothing(held: Project) -> None:
    hid = queue(held)[0]["hold_id"]
    before = held.store.scalar("SELECT COUNT(*) FROM step_events")
    r = cli(held, "wait", "--hold", hid, *POLL, "--timeout", "0.2", "--json")
    assert r.exit_code == 10, r.output
    out = json.loads(r.output)
    assert out["event"] == "timeout" and out["hold_id"] == hid
    assert held.store.scalar("SELECT COUNT(*) FROM step_events") == before
    assert held.store.scalar("SELECT resolved_via FROM holds WHERE hold_id=?", (hid,)) is None


def test_wait_hold_withdrawn(held: Project) -> None:
    hid = queue(held)[0]["hold_id"]
    t = later(held, lambda s: s.withdraw_holds([hid], "run abandoned"))
    r = cli(held, "wait", "--hold", hid, *POLL, "--timeout", "20", "--json")
    t.join()
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["event"] == "withdrawn" and out["review"] is None
    assert out["resolved_via"] == "withdrawn"


def test_wait_run_returns_when_a_hold_closes(held: Project) -> None:
    run_id = held.store.scalar("SELECT run_id FROM runs")
    hids = [h["hold_id"] for h in queue(held)]
    t = later(held, lambda s: accept_hold(s, hids[0]))
    r = cli(held, "wait", *POLL, "--timeout", "20", "--json")  # the latest run
    t.join()
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["event"] == "changed" and out["run_id"] == run_id
    assert hids[0] in out["before"]["open_holds"]
    assert hids[0] not in out["after"]["open_holds"]
    assert f"holds closed: {hids[0]}" in out["message"]
    r = cli(held, "wait", "--run", run_id, *POLL, "--timeout", "0.2")
    assert r.exit_code == 10 and "unchanged" in r.output


def test_wait_run_on_a_closed_run_returns_at_once(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    run_id = json.loads(r.output)["run_id"]
    r = cli(p, "wait", "--run", run_id, "--json")
    assert r.exit_code == 0
    assert json.loads(r.output)["event"] == "closed"


def test_wait_refusals(held: Project) -> None:
    r = cli(held, "wait", "--hold", "NOPE")
    assert r.exit_code == 15 and "no hold NOPE" in str(r.stderr)
    r = cli(held, "wait", "--run", "NOPE")
    assert r.exit_code == 15 and "no run NOPE" in str(r.stderr)
    r = cli(held, "wait", "--hold", "a", "--run", "b")
    assert r.exit_code == 15


def test_run_json_at_a_hold_names_the_wait_the_page_and_the_skill(
    held: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backlog L14: an operator holding an older skill did not wait for a console verdict. The
    held payload names the `wait` command, the console page when `page_url` is set, and the
    operator skill installed with the engine; the terse human message is unchanged (14.2)."""
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(held, "run", "--json", env=env)
    assert r.exit_code == 10, r.output
    out = json.loads(r.output)
    hid = out["holds"][0]["hold_id"]
    assert out["wait_command"] == f"stringency wait --hold {hid} --timeout 86400 --json"
    assert out["review_page"] is None and out["operator_skill"] is None

    cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "stringency" / "notify.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("page_url: http://127.0.0.1:8765/?t=tok\nchannels: []\n")
    skill = tmp_path / "venv" / "skills" / "stringency-operator" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: stringency-operator\n---\n")
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    out = json.loads(cli(held, "run", "--json", env=env).output)
    assert out["review_page"] == f"http://127.0.0.1:8765/hold/{hid}?t=tok"
    assert out["operator_skill"] == str(skill)

    r = cli(held, "run", env=env)
    assert "stringency wait" not in r.output and "8765" not in r.output
