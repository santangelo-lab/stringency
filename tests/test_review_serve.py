"""The review page (design 7.5 `via: web`, 14.1; ux-two-audiences 5.2): the reviewer's own
server records verdicts by the same rules as the terminal, behind a per-start token."""

from __future__ import annotations

import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from stringency.project import Project
from stringency.review import queue
from stringency.review_serve import discover, make_server
from stringency.runs import open_or_resume
from stringency.steps import propose
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli

TOKEN = "test-token-not-secret"


@pytest.fixture(autouse=True)
def _identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


@pytest.fixture
def held(make_project: InitFn) -> tuple[Project, dict[str, str]]:
    """A toy-engine project with an open item hold on 03_label (split.yml)."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "run", env=env)
    assert r.exit_code == 10, r.output
    return p, env


@pytest.fixture
def server(held: tuple[Project, dict[str, str]]) -> Iterator[tuple[str, Project]]:
    p, _ = held
    srv = make_server([p.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", p
    finally:
        srv.shutdown()
        srv.server_close()


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def post(url: str, **fields: str) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_list_and_hold_page(server: tuple[str, Project]) -> None:
    base, p = server
    status, body = get(f"{base}/?t={TOKEN}")
    assert status == 200
    assert "Label the groups" in body and "run_disagreement" in body and "<script" not in body
    h = queue(p)[0]
    status, body = get(f"{base}/p/0/hold/{h['hold_id']}?t={TOKEN}")
    assert status == 200
    assert "replicate 1: abundant (high)" in body  # the terminal packet, verbatim
    assert 'name="verdict" value="accept"' in body and 'name="replicate"' in body
    assert "<script" not in body


def test_token_required(server: tuple[str, Project]) -> None:
    base, p = server
    assert get(f"{base}/")[0] == 403
    assert get(f"{base}/?t=wrong")[0] == 403
    h = queue(p)[0]
    status, _ = post(f"{base}/p/0/hold/{h['hold_id']}", verdict="accept", replicate="1")
    assert status == 403
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0


def test_replicate_accept_records_via_web(server: tuple[str, Project]) -> None:
    base, p = server
    h = queue(p)[0]
    status, body = post(
        f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1", reason=""
    )
    assert status == 200 and "Recorded" in body
    rev = p.store.one("SELECT * FROM reviews WHERE hold_id=?", (h["hold_id"],))
    assert rev["via"] == "web" and rev["reviewer"] == "tester" and rev["chosen_replicate"] == 1
    cons = p.store.one("SELECT * FROM consensus WHERE item_id='A'")
    assert cons["source"] == "accepted" and cons["label"] == "abundant"
    assert queue(p) == []


def test_override_outside_vocabulary_reshows_form(server: tuple[str, Project]) -> None:
    base, p = server
    h = queue(p)[0]
    status, body = post(
        f"{base}/p/0/hold/{h['hold_id']}",
        t=TOKEN,
        verdict="override",
        label="",
        reason="sd is small",
    )
    assert status == 400 and "override needs" in body and 'name="verdict"' in body
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0
    # the form offers only the vocabulary; a label outside it is refused by the engine
    status, body = post(
        f"{base}/p/0/hold/{h['hold_id']}",
        t=TOKEN,
        verdict="override",
        label="not-a-label",
        reason="sd is small",
    )
    assert status == 400 and "not in vocabulary" in body
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0


def test_stranger_is_refused_and_writes_nothing(
    server: tuple[str, Project], monkeypatch: pytest.MonkeyPatch
) -> None:
    base, p = server
    monkeypatch.setattr("stringency.review.current_user", lambda: "stranger")
    h = queue(p)[0]
    status, body = post(f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1")
    assert status == 403 and "you are stranger" in body
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0
    assert queue(p) != []


def test_strict_profile_accepts_web_and_prefills_confirm(make_project: InitFn) -> None:
    p = make_project(profile="strict")
    h = p.confirm_hold()
    srv = make_server([p.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        status, body = get(f"{base}/?t={TOKEN}")
        assert status == 200 and "confirm" in body
        status, body = post(f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="")
        assert status == 400 and "needs --reason" in body  # the engine's rule, re-shown in the form
        status, body = post(
            f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="matches the plan"
        )
        assert status == 200 and "Recorded" in body
        rev = p.store.one("SELECT via FROM reviews WHERE hold_id=?", (h["hold_id"],))
        assert rev["via"] == "web" and p.confirm_status() == "accepted"
    finally:
        srv.shutdown()
        srv.server_close()


def test_param_flag_hold_is_accepted_on_the_page(make_project: InitFn) -> None:
    """A pre-phase flag (param.agent_proposed) accepted on the page makes the step admissible."""
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    prop = propose(rc, "01_filter", {"min_value": 12}, rationale="12 is the floor here")
    assert str(prop.status) == "held"
    srv = make_server([p.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        h = queue(p)[0]
        assert h["kind"] == "flag"
        status, body = get(f"{base}/p/0/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200 and "param.agent_proposed" in body and "min_value" in body
        status, body = post(
            f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="agreed, 12"
        )
        assert status == 200 and "step admissible" in body
        assert (
            p.store.one("SELECT via FROM reviews WHERE hold_id=?", (h["hold_id"],))["via"] == "web"
        )
    finally:
        srv.shutdown()
        srv.server_close()


def test_discover_walks_two_levels(tmp_path: Path, held: tuple[Project, dict[str, str]]) -> None:
    p, _ = held
    area = tmp_path / "area"
    (area / "deep" / "inner").mkdir(parents=True)
    (area / "deep" / "inner" / "stringency.yml").write_text("x: 1\n")
    (area / "shallow").mkdir()
    (area / "shallow" / "stringency.yml").write_text("x: 1\n")
    (area / "noise").mkdir()
    roots = discover([p.root], area)
    assert roots[0] == p.root.resolve()
    assert {r.name for r in roots[1:]} == {"inner", "shallow"}
    with pytest.raises(Exception, match="not a stringency project"):
        discover([tmp_path / "nowhere"], None)
