"""The review page (design 7.5 `via: web`, 14.1; ux-two-audiences 5.2): the reviewer's own
server records verdicts by the same rules as the terminal, behind a per-start token."""

from __future__ import annotations

import html
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


# -- the project page (Track 1h, plan section 3.4) ------------------------------------------------


def _no_follow(url: str) -> tuple[int, str]:
    """Status and Location without following the redirect."""
    import http.client

    u = urllib.parse.urlsplit(url)
    conn = http.client.HTTPConnection(u.hostname or "", u.port, timeout=10)
    conn.request("GET", f"{u.path}?{u.query}" if u.query else u.path)
    r = conn.getresponse()
    loc = r.getheader("Location") or ""
    conn.close()
    return r.status, loc


def _tables(html: str) -> list[list[list[str]]]:
    """Every <table> as rows of cell texts (th and td alike)."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.tables: list[list[list[str]]] = []
            self.row: list[str] | None = None
            self.cell: list[str] | None = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "table":
                self.tables.append([])
            elif tag == "tr":
                self.row = []
            elif tag in ("td", "th"):
                self.cell = []

        def handle_endtag(self, tag: str) -> None:
            if tag in ("td", "th") and self.cell is not None and self.row is not None:
                self.row.append("".join(self.cell))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.tables[-1].append(self.row)
                self.row = None

        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell.append(data)

    p = P()
    p.feed(html)
    return p.tables


def _serve(p: Project, **kw: object) -> Iterator[str]:
    srv = make_server([p.root], port=0, token=TOKEN, **kw)  # type: ignore[arg-type]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def test_landing_has_needs_you_then_the_board_with_sentences(server: tuple[str, Project]) -> None:
    from stringency.board import project_entry, sentence

    base, p = server
    status, body = get(f"{base}/?t={TOKEN}")
    assert status == 200 and "<script" not in body
    assert body.index("Needs you") < body.index("Board") < body.index("In words")
    assert sentence(project_entry(p.root)) in html.unescape(body)  # the board's sentence, verbatim
    assert f'href="/p/0?t={TOKEN}"' in body and 'content="60"' in body
    tables = _tables(body)
    assert tables[0][0] == ["project", "step", "kind", "item", "waits on", "open for"]
    assert tables[0][1][:4] == [p.root.name, "Label the groups", "run_disagreement", "A"]
    assert tables[1][0][:4] == ["project", "pipeline", "method", "plan"]


def test_project_page_names_every_step_by_title_with_status(server: tuple[str, Project]) -> None:
    base, p = server
    status, body = get(f"{base}/p/0?t={TOKEN}")
    assert status == 200 and "<script" not in body and 'content="60"' in body
    steps = _tables(body)[0][1:]
    assert [s[0] for s in steps] == [p.pipeline.title(s) for s in p.pipeline.order()]
    by = dict(steps)
    assert by["Label the groups"] == "held" and by["Filter low-value rows"] == "completed"
    assert "Nothing delivered yet." in body and "Label the groups" in body
    assert get(f"{base}/p/7?t={TOKEN}")[0] == 404


def test_run_page_tables_equal_present_rows_and_files_download(make_project: InitFn) -> None:
    from stringency.present import Site, present_rows
    from tests.test_board_present import _delivered, _skill

    p, run_id, d = _delivered(make_project)
    table = next(f["file"] for f in d.files if f["file"].endswith(".tsv"))
    _skill(p, [{"title": "The table", "source": table, "kind": "table"}])
    for base in _serve(p):
        status, body = get(f"{base}/p/0/run/{run_id}?t={TOKEN}")
        assert status == 200 and "<script" not in body
        site = Site.load(p.root)
        rows = present_rows(site, run_id)
        site.store.close()
        assert rows and rows[0]["title"] == "The table"
        html_tables = _tables(body)
        assert html_tables[0] == [rows[0]["columns"], *rows[0]["rows"]]
        assert "Not shown, by the method's rule: run ids, hashes." in body
        assert "## " in body or "Summary" in body  # summary.md body is on the page
        # the project page lists the delivery and links to this run
        status, proj = get(f"{base}/p/0?t={TOKEN}")
        assert f'href="/p/0/run/{run_id}?t={TOKEN}"' in proj and table in proj
        # files: a listed file with its recorded type, a report, and nothing else
        status, text = get(f"{base}/p/0/file/{run_id}/{table}?t={TOKEN}")
        assert status == 200 and text == (Path(d.path) / table).read_text()
        with urllib.request.urlopen(f"{base}/p/0/file/{run_id}/{table}?t={TOKEN}") as r:
            assert r.headers["Content-Type"].startswith("text/tab-separated-values")
            assert r.headers["Content-Disposition"] == f'attachment; filename="{table}"'
        with urllib.request.urlopen(f"{base}/p/0/file/{run_id}/summary.md?t={TOKEN}") as r:
            assert r.headers["Content-Type"].startswith("text/markdown")
        assert get(f"{base}/p/0/file/{run_id}/stringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/file/{run_id}/index.json?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/file/{run_id}/..%2Fstringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/file/{run_id}/..%5Cstringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/file/{run_id}/.hidden?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/file/NOTARUN/{table}?t={TOKEN}")[0] == 404
        assert get(f"{base}/p/0/run/NOTARUN?t={TOKEN}")[0] == 404
        # the redirect routes a notification links to
        status, loc = _no_follow(f"{base}/run/{run_id}?t={TOKEN}")
        assert (status, loc) == (302, f"/p/0/run/{run_id}?t={TOKEN}")
        assert _no_follow(f"{base}/run/NOTARUN?t={TOKEN}")[0] == 404


def test_hold_page_shows_hold_view_tables_and_redirect(make_project: InitFn) -> None:
    import json

    from tests.test_board_present import _delivered, _skill

    p, run_id, _ = _delivered(make_project)
    (p.root / "runs" / run_id / "proposal.csv").write_text("item,verdict\ng1,exclude\n")
    _skill(
        p, [], hold_view=[{"predicate": "toy.flagged", "source": "proposal.csv", "kind": "table"}]
    )
    hid = p.store.create_hold(
        {
            "run_id": run_id,
            "step_id": "04_compare",
            "kind": "flag",
            "reason": "toy.flagged: something looked off",
            "waits_on_role": "reviewer",
            "context_json": json.dumps({"predicate": "toy.flagged@1", "evidence": {"n": 1}}),
        }
    )
    for base in _serve(p):
        status, body = get(f"{base}/p/0/hold/{hid}?t={TOKEN}")
        assert status == 200 and "<script" not in body
        assert _tables(body)[0] == [["item", "verdict"], ["g1", "exclude"]]
        assert body.index("<table") < body.index("<pre>")  # the method's table above the packet
        assert "<form" in body
        status, loc = _no_follow(f"{base}/hold/{hid}?t={TOKEN}")
        assert (status, loc) == (302, f"/p/0/hold/{hid}?t={TOKEN}")
        assert _no_follow(f"{base}/hold/NOPE?t={TOKEN}")[0] == 404


def test_read_only_refuses_post_and_hides_the_form(held: tuple[Project, dict[str, str]]) -> None:
    from stringency.review_serve import READ_ONLY_MESSAGE

    p, _ = held
    h = queue(p)[0]
    for base in _serve(p, read_only=True):
        status, body = get(f"{base}/?t={TOKEN}")
        assert status == 200 and "read-only" in body
        status, body = get(f"{base}/p/0/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200 and "<form" not in body and "scripts/review-page.sh" in body
        assert "stringency review --hold" in body
        status, body = post(
            f"{base}/p/0/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1"
        )
        assert status == 405 and READ_ONLY_MESSAGE in html.unescape(body)
        assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0
        assert queue(p) != []
        # without the token a POST is still 403, not 405
        status, _ = post(f"{base}/p/0/hold/{h['hold_id']}", verdict="accept", replicate="1")
        assert status == 403


def test_token_file_is_created_once_and_honoured(
    tmp_path: Path, held: tuple[Project, dict[str, str]]
) -> None:
    import stat

    from stringency.review_serve import read_token_file

    p, _ = held
    f = tmp_path / "cfg" / "page-token"
    token = read_token_file(f)
    assert len(token) >= 24 and f.read_text().strip() == token
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert read_token_file(f) == token
    srv = make_server([p.root], port=0, token=read_token_file(f), read_only=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        assert get(f"{base}/?t={token}")[0] == 200
        assert get(f"{base}/?t={TOKEN}")[0] == 403
    finally:
        srv.shutdown()
        srv.server_close()
    f.write_text("\n")
    with pytest.raises(Exception, match="empty"):
        read_token_file(f)
