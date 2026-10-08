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
from stringency.review_render import render
from stringency.review_serve import discover, make_server
from stringency.runs import open_or_resume
from stringency.steps import propose
from tests.conftest import InitFn, accept_hold
from tests.test_run import HARNESS, MOCK, cli

TOKEN = "test-token-not-secret"


def _only_console_script(body: str) -> bool:
    """The page carries one script, the vendored console script, and nothing inline."""
    return body.count("<script") == 1 and '<script src="/static/console.js" defer></script>' in body


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
    assert "Label the groups" in body and "run_disagreement" in body and _only_console_script(body)
    h = queue(p)[0]
    status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
    assert status == 200
    assert "replicate 1: abundant (high)" in body  # the terminal packet, verbatim
    assert 'name="verdict" value="accept"' in body and 'name="replicate"' in body
    assert _only_console_script(body)


def test_token_required(server: tuple[str, Project]) -> None:
    base, p = server
    assert get(f"{base}/")[0] == 403
    assert get(f"{base}/?t=wrong")[0] == 403
    h = queue(p)[0]
    status, _ = post(f"{base}/hold/{h['hold_id']}", verdict="accept", replicate="1")
    assert status == 403
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0


def test_replicate_accept_records_via_web(server: tuple[str, Project]) -> None:
    base, p = server
    h = queue(p)[0]
    status, body = post(
        f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1", reason=""
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
        f"{base}/hold/{h['hold_id']}",
        t=TOKEN,
        verdict="override",
        label="",
        reason="sd is small",
    )
    assert status == 400 and "override needs" in body and 'name="verdict"' in body
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0
    # the form offers only the vocabulary; a label outside it is refused by the engine
    status, body = post(
        f"{base}/hold/{h['hold_id']}",
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
    status, body = post(f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1")
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
        status, body = post(f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="")
        assert status == 400 and "needs --reason" in body  # the engine's rule, re-shown in the form
        status, body = post(
            f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="matches the plan"
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
    prop = propose(
        rc,
        "01_filter",
        {"min_value": 12},
        rationale="12 is the floor here.\nRows below it are noise.",
    )
    assert str(prop.status) == "held"
    # L8: the operator's reason is in the packet the terminal shows
    view = render(p, queue(p)[0])
    assert view.operator_reason == "12 is the floor here.\nRows below it are noise."
    assert (
        "the operator's reason:\n  12 is the floor here.\n  Rows below it are noise." in view.text
    )
    srv = make_server([p.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        h = queue(p)[0]
        assert h["kind"] == "flag"
        status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200 and "param.agent_proposed" in body and "min_value" in body
        assert "the operator&#39;s reason:" in body and "Rows below it are noise." in body
        status, body = post(
            f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", reason="agreed, 12"
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
    # what the board skips, the page skips: superseded and declarations at either level, dot-dirs
    for skip in ("superseded/old", "declarations/decl", ".hidden/h", "deep/superseded", "deep/.x"):
        (area / skip).mkdir(parents=True)
        (area / skip / "stringency.yml").write_text("x: 1\n")
    roots = discover([p.root], area)
    assert roots[0] == p.root.resolve()
    assert {r.name for r in roots[1:]} == {"inner", "shallow"}
    # a superseded project named explicitly is still served
    assert discover([area / "superseded" / "old"], None) == [
        (area / "superseded" / "old").resolve()
    ]
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
    assert status == 200 and _only_console_script(body)
    assert body.index("Needs you") < body.index("Board") < body.index("In words")
    assert sentence(project_entry(p.root)) in html.unescape(body)  # the board's sentence, verbatim
    assert f'href="/project/{p.config.project_id}"' in body and 'content="60"' in body
    # the inbox: one card under its ask heading, the title linking to the hold
    assert "Settle a disagreement" in body
    h = queue(p)[0]
    assert f'<div class="card" data-card="{h["hold_id"]}">' in body
    assert (
        f'<a href="/hold/{h["hold_id"]}" data-open><strong>Label the groups, item A</strong>'
        in body
    )
    assert "run_disagreement" in body and "item A" in body
    # the board: the held project is active, with the four driver columns
    tables = _tables(body)
    assert tables[0][0] == [
        *["project", "pipeline", "method", "plan", "latest run", "current step"],
        *["waiting on", "delivered", "for", "elsewhere", "driver", "last call"],
    ]
    assert tables[0][1][0] == p.root.name and "you" in tables[0][1][6]
    assert "1 active, 0 delivered and idle" in body


def test_project_page_names_every_step_by_title_with_status(server: tuple[str, Project]) -> None:
    base, p = server
    status, body = get(f"{base}/project/{p.config.project_id}?t={TOKEN}")
    assert status == 200 and _only_console_script(body) and 'content="60"' in body
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
        status, body = get(f"{base}/run/{run_id}?t={TOKEN}")
        assert status == 200 and _only_console_script(body)
        site = Site.load(p.root)
        rows = present_rows(site, run_id)
        site.store.close()
        assert rows and rows[0]["title"] == "The table"
        html_tables = _tables(body)
        assert html_tables[0] == [rows[0]["columns"], *rows[0]["rows"]]
        assert "Not shown, by the method's rule: run ids, hashes." in body
        assert "## " in body or "Summary" in body  # summary.md body is on the page
        # the project page lists the delivery and links to this run
        status, proj = get(f"{base}/project/{p.config.project_id}?t={TOKEN}")
        assert f'href="/run/{run_id}"' in proj and table in proj
        # files: a listed file with its recorded type, a report, and nothing else
        status, text = get(f"{base}/file/{run_id}/{table}?t={TOKEN}")
        assert status == 200 and text == (Path(d.path) / table).read_text()
        with urllib.request.urlopen(f"{base}/file/{run_id}/{table}?t={TOKEN}") as r:
            assert r.headers["Content-Type"].startswith("text/tab-separated-values")
            assert r.headers["Content-Disposition"] == f'attachment; filename="{table}"'
        with urllib.request.urlopen(f"{base}/file/{run_id}/summary.md?t={TOKEN}") as r:
            assert r.headers["Content-Type"].startswith("text/markdown")
        assert get(f"{base}/file/{run_id}/stringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/file/{run_id}/index.json?t={TOKEN}")[0] == 404
        assert get(f"{base}/file/{run_id}/..%2Fstringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/file/{run_id}/..%5Cstringency.yml?t={TOKEN}")[0] == 404
        assert get(f"{base}/file/{run_id}/.hidden?t={TOKEN}")[0] == 404
        assert get(f"{base}/file/NOTARUN/{table}?t={TOKEN}")[0] == 404
        assert get(f"{base}/run/NOTARUN?t={TOKEN}")[0] == 404
        # the positional routes of 0.2.6 redirect to the id routes; a notification's link is a page
        status, loc = _no_follow(f"{base}/p/0/run/{run_id}?t={TOKEN}")
        assert (status, loc) == (302, f"/run/{run_id}?t={TOKEN}")
        assert _no_follow(f"{base}/p/0?t={TOKEN}") == (
            302,
            f"/project/{p.config.project_id}?t={TOKEN}",
        )
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
        status, body = get(f"{base}/hold/{hid}?t={TOKEN}")
        assert status == 200 and _only_console_script(body)
        assert _tables(body)[0] == [["item", "verdict"], ["g1", "exclude"]]
        assert body.index("<table") < body.index("<pre>")  # the method's table above the packet
        assert "<form" in body
        status, loc = _no_follow(f"{base}/p/0/hold/{hid}?t={TOKEN}")
        assert (status, loc) == (302, f"/hold/{hid}?t={TOKEN}")
        assert _no_follow(f"{base}/hold/NOPE?t={TOKEN}")[0] == 404


def test_read_only_refuses_post_and_hides_the_form(held: tuple[Project, dict[str, str]]) -> None:
    from stringency.review_serve import READ_ONLY_MESSAGE

    p, _ = held
    h = queue(p)[0]
    for base in _serve(p, read_only=True):
        status, body = get(f"{base}/?t={TOKEN}")
        assert status == 200 and "read-only" in body
        status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200 and "<form" not in body and "scripts/review-page.sh" in body
        assert "stringency review --hold" in body
        status, body = post(f"{base}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1")
        assert status == 405 and READ_ONLY_MESSAGE in html.unescape(body)
        assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (h["hold_id"],)) == 0
        assert queue(p) != []
        # without the token a POST is still 403, not 405
        status, _ = post(f"{base}/hold/{h['hold_id']}", verdict="accept", replicate="1")
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


# -- the console, C1 (console-and-fleet-plan.md 3.5): several roots, routes by id, the cookie ---


def test_cookie_set_on_tokened_visit_then_plain_links_work(server: tuple[str, Project]) -> None:
    import http.client

    base, p = server
    u = urllib.parse.urlsplit(base)
    conn = http.client.HTTPConnection(u.hostname or "", u.port, timeout=10)
    conn.request("GET", f"/?t={TOKEN}")
    r = conn.getresponse()
    cookie = r.getheader("Set-Cookie") or ""
    r.read()
    assert r.status == 200
    assert cookie.startswith(f"stringency_console_{u.port}={TOKEN}")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    # the links on the page carry no token
    conn.request("GET", f"/project/{p.config.project_id}?t={TOKEN}")
    r = conn.getresponse()
    body = r.read().decode()
    assert "?t=" not in body
    # a cookied request without the token is served; one with neither is 403
    conn.request("GET", f"/project/{p.config.project_id}", headers={"Cookie": cookie.split(";")[0]})
    r = conn.getresponse()
    assert r.status == 200 and r.getheader("Set-Cookie") is None
    r.read()
    conn.request("GET", f"/project/{p.config.project_id}")
    r = conn.getresponse()
    assert r.status == 403
    r.read()
    # a wrong cookie is 403; a POST with the cookie alone is accepted by the token check (405 on
    # a read-only server would come after it; here it reaches the form rules: 400, choose a verdict)
    conn.request(
        "GET",
        f"/project/{p.config.project_id}",
        headers={"Cookie": f"stringency_console_{u.port}=wrong"},
    )
    r = conn.getresponse()
    assert r.status == 403
    r.read()
    h = queue(p)[0]
    conn.request(
        "POST",
        f"/hold/{h['hold_id']}",
        body=urllib.parse.urlencode({"verdict": ""}),
        headers={
            "Cookie": cookie.split(";")[0],
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    r = conn.getresponse()
    assert r.status == 400 and "choose a verdict" in r.read().decode()
    conn.close()


def test_two_project_dirs_and_a_project_that_appears_later(
    tmp_path: Path, make_project: InitFn
) -> None:
    import shutil

    from stringency.console import Registry

    a = make_project(pipeline="toy-engine", execution="engine")
    area1 = tmp_path / "study-one"
    area2 = tmp_path / "study-two"
    (area1 / "one").mkdir(parents=True)
    area2.mkdir()
    for item in a.root.iterdir():
        dest = area1 / "one" / item.name
        shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
    reg = Registry(explicit=[], dirs=[area1, area2], rescan_seconds=0.0)
    reg.refresh(force=True)
    assert [r.name for r in reg.roots] == ["one"]
    assert reg.root_of(a.config.project_id) == (area1 / "one").resolve()
    # a project initialised later under the second directory is found on the next scan
    (area2 / "two").mkdir()
    for item in a.root.iterdir():
        dest = area2 / "two" / item.name
        shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
    (area2 / "two" / "stringency.yml").write_text(
        (area2 / "two" / "stringency.yml").read_text().replace(a.config.project_id, "01TWO")
    )
    reg.refresh()
    assert [r.name for r in reg.roots] == ["one", "two"]
    assert reg.root_of("01TWO") == (area2 / "two").resolve()
    # ownership lookups find the hold's project and refuse an unknown id
    pid, root = reg.owner_of("hold", a.confirm_hold()["hold_id"])
    assert pid == a.config.project_id and root.name == "one"
    with pytest.raises(Exception, match="no hold NOPE"):
        reg.owner_of("hold", "NOPE")
    with pytest.raises(Exception, match="no project 01NONE"):
        reg.root_of("01NONE")
    # the server serves both directories and lists both projects
    srv = make_server([], port=0, token=TOKEN, projects_dirs=[area1, area2])
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        status, body = get(f"{base}/?t={TOKEN}")
        assert status == 200 and 'href="/project/01TWO"' in body
        assert f'href="/project/{a.config.project_id}"' in body
        assert get(f"{base}/project/01TWO?t={TOKEN}")[0] == 200
    finally:
        srv.shutdown()
        srv.server_close()


# -- the console, C2 first cut (plan 3.7, 3.9): the inbox by ask, the driver, the timeline ------


def test_inbox_groups_holds_by_ask_and_the_method_names_the_card(make_project: InitFn) -> None:
    from stringency.console import ask_of, card_title, group_cards, hold_context, method_ask
    from tests.test_board_present import _skill

    p = make_project(pipeline="toy-engine", execution="engine")
    confirm = p.confirm_hold()
    assert ask_of(confirm, hold_context(confirm)) == "confirm"
    accept_hold(p.store, confirm["hold_id"])
    rc = open_or_resume(p)
    propose(rc, "01_filter", {"min_value": 12}, rationale="12 is the floor here")
    h = queue(p)[0]
    ctx = hold_context(h)
    assert ask_of(h, ctx) == "parameters"
    assert card_title(h, ctx, "parameters", "Filter low-value rows", None) == (
        "Filter low-value rows: min_value"
    )
    # the method's `ask` phrase names the card; an entry for another step does not apply
    skill = {
        "hold_view": [
            {"predicate": "param.agent_proposed", "step": "02_other", "ask": "wrong step"},
            {"predicate": "param.agent_proposed", "ask": "Approve the floor"},
        ]
    }
    assert method_ask(skill, "param.agent_proposed@1", "01_filter") == "Approve the floor"
    assert card_title(h, ctx, "parameters", "Filter low-value rows", skill) == "Approve the floor"

    # the shapes the engine groups by, without a trace behind them
    class Row(dict):  # noqa: D401 - a sqlite3.Row stand-in
        def __getitem__(self, k: str):  # type: ignore[override]
            return dict.get(self, k)

    item = Row(kind="run_disagreement", item_id="7", context_json="{}")
    assert ask_of(item, {}) == "disagreement"
    unsure = Row(kind="self_uncertain", item_id="7", context_json="{}")
    assert ask_of(unsure, {}) == "uncertain"
    invalid = Row(kind="run_disagreement", item_id=None, context_json="{}")
    assert ask_of(invalid, {}) == "invalid"
    route = Row(kind="flag", item_id=None, context_json="{}")
    assert ask_of(route, {"evidence": {"consensus_label": "correct_batch"}}) == "consensus"
    other = Row(kind="flag", item_id=None, context_json="{}")
    assert ask_of(other, {"evidence": {"n": 1}, "predicate": "toy.flagged@1"}) == "flag"
    groups = group_cards(
        [
            {"group": "flag", "created": "2026-01-01T00:00:02Z", "hold_id": "B"},
            {"group": "confirm", "created": "2026-01-01T00:00:03Z", "hold_id": "C"},
            {"group": "flag", "created": "2026-01-01T00:00:01Z", "hold_id": "A"},
        ]
    )
    assert [g["key"] for g in groups][:2] == ["confirm", "parameters"]
    assert [c["hold_id"] for g in groups for c in g["cards"]] == ["C", "A", "B"]
    # on the page: the parameter hold under its heading, with the method's phrase
    _skill(p, [], hold_view=[{"predicate": "param.agent_proposed", "ask": "Approve the floor"}])
    for base in _serve(p):
        status, body = get(f"{base}/?t={TOKEN}")
        assert status == 200
        assert "Approve the operator&#39;s parameters" in body and "Approve the floor" in body
        assert "Confirm the plan" not in body  # an empty group is not shown


def test_driver_block_and_timeline(server: tuple[str, Project]) -> None:
    from datetime import UTC, datetime, timedelta

    from stringency.console import driver, references, timeline

    base, p = server
    run = p.store.one("SELECT * FROM runs ORDER BY started DESC LIMIT 1")
    assert run is not None
    refs = references([p.root])
    assert refs[("toy-engine", "01_filter")] >= 0  # a completed step gives the reference
    current = {"step_id": "03_label", "title": "Label the groups", "status": "held"}
    d = driver(p.store.conn, run, current, "toy-engine", refs)
    assert d["user"] == run["user"] and d["host"] == run["host"]
    assert d["last_call"] is not None and d["step"] == "Label the groups" and d["status"] == "held"
    assert d["elapsed"] and not d["stale"]  # a held step is the person's, never stale
    # a running step with no engine call for an hour is stale; one of twenty minutes is not,
    # when the same step took fifteen minutes elsewhere (twice that is the limit)
    later = datetime.now(UTC) + timedelta(hours=1)
    running = {"step_id": "03_label", "title": "Label the groups", "status": "dispatching"}
    assert driver(p.store.conn, run, running, "toy-engine", refs, now=later)["stale"]
    soon = datetime.now(UTC) + timedelta(minutes=20)
    slow = {("toy-engine", "03_label"): 15 * 60.0}
    assert not driver(p.store.conn, run, running, "toy-engine", slow, now=soon)["stale"]
    assert driver(p.store.conn, run, running, "toy-engine", {}, now=soon)["stale"]
    # the timeline: one run, opened, held at the labelling step; the page shows it
    titles = {s: p.pipeline.title(s) for s in p.pipeline.order()}
    tl = timeline(p.store.conn, titles)
    assert len(tl) == 1 and tl[0]["status"] == "held" and not tl[0]["fork"]
    texts = [e["text"] for e in tl[0]["events"]]
    assert texts[0].startswith("opened by ")
    assert any(t.startswith("held at 'Label the groups', item A (run_disagreement)") for t in texts)
    status, body = get(f"{base}/project/{p.config.project_id}?t={TOKEN}")
    assert status == 200 and "Timeline" in body and "held at &#39;Label the groups&#39;" in body
    assert "Driver:" in body and "Last engine call" in body
    status, body = get(f"{base}/?t={TOKEN}")
    assert "<th>driver</th>" in body and "<th>elsewhere</th>" in body


def test_hold_view_entry_for_another_step_is_not_shown(make_project: InitFn) -> None:
    import json

    from tests.test_board_present import _delivered, _skill

    p, run_id, _ = _delivered(make_project)
    (p.root / "runs" / run_id / "proposal.csv").write_text("item,verdict\ng1,exclude\n")
    _skill(
        p,
        [],
        hold_view=[
            {
                "predicate": "toy.flagged",
                "step": "01_filter",
                "source": "proposal.csv",
                "kind": "table",
            },
            {
                "predicate": "toy.flagged",
                "step": "04_compare",
                "source": "proposal.csv",
                "kind": "table",
            },
        ],
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
        status, body = get(f"{base}/hold/{hid}?t={TOKEN}")
        assert status == 200
        assert len([t for t in _tables(body) if t and t[0] == ["item", "verdict"]]) == 1


# -- the console, C5 first cut (plan 3.5, 3.6): the event stream, the JSON routes, the script ----


def test_snapshot_diff_names_the_change() -> None:
    from stringency.console import diff_snapshots

    a = {
        "run": ("R1", "running"),
        "steps": {"01": "completed", "02": "running"},
        "holds": set(),
        "deliveries": 0,
    }
    assert diff_snapshots(None, a) == [("project", {})]
    b = {
        "run": ("R1", "held"),
        "steps": {"01": "completed", "02": "held"},
        "holds": {"H1"},
        "deliveries": 0,
    }
    assert diff_snapshots(a, b) == [
        ("hold_opened", {"hold_id": "H1"}),
        ("run", {"run_id": "R1", "status": "held"}),
        ("step", {"step_id": "02", "status": "held"}),
    ]
    c = {"run": ("R2", "running"), "steps": {"01": "completed"}, "holds": set(), "deliveries": 1}
    assert diff_snapshots(b, c) == [
        ("hold_resolved", {"hold_id": "H1"}),
        ("run", {"run_id": "R2", "status": "running"}),
        ("delivery", {}),
    ]
    assert diff_snapshots(c, c) == []


def test_events_stream_follows_the_trace(held: tuple[Project, dict[str, str]]) -> None:
    import http.client
    import json
    import time

    p, _ = held
    srv = make_server([p.root], port=0, token=TOKEN, poll_seconds=0.2)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        port = srv.server_address[1]
        time.sleep(0.6)  # the watcher's first pass takes the baseline snapshot
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", f"/events?t={TOKEN}")
        r = conn.getresponse()
        assert r.status == 200 and r.getheader("Content-Type", "").startswith("text/event-stream")
        assert r.readline() == b": connected\n"

        def next_event() -> tuple[str, dict[str, str]]:
            name, data = "", "{}"
            deadline = time.time() + 10
            while time.time() < deadline:
                line = r.readline().decode().rstrip("\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    data = line[6:]
                elif line == "" and name:
                    return name, json.loads(data)
            raise AssertionError("no event within 10 s")

        # a hold opened in another process (here: the store) is announced
        hid = p.store.create_hold(
            {
                "run_id": None,
                "step_id": None,
                "kind": "confirm",
                "reason": "test",
                "waits_on_role": "owner",
                "context_json": "{}",
            }
        )
        name, data = next_event()
        assert (name, data["hold_id"], data["project_id"]) == (
            "hold_opened",
            hid,
            p.config.project_id,
        )
        # a verdict recorded on the page is announced as the hold's resolution
        h = next(x for x in queue(p) if x["kind"] == "run_disagreement")
        status, _ = post(
            f"http://127.0.0.1:{port}/hold/{h['hold_id']}", t=TOKEN, verdict="accept", replicate="1"
        )
        assert status == 200
        seen = {}
        for _ in range(3):
            name, data = next_event()
            seen[name] = data
            if "hold_resolved" in seen and "run" in seen:
                break
        assert seen["hold_resolved"]["hold_id"] == h["hold_id"]
        conn.close()
    finally:
        srv.shutdown()
        srv.server_close()


def test_json_routes_and_static_and_csp(server: tuple[str, Project]) -> None:
    import json
    import urllib.request

    base, p = server
    with urllib.request.urlopen(f"{base}/?t={TOKEN}") as r:
        assert r.headers["Content-Security-Policy"].startswith("default-src 'self'")
    with urllib.request.urlopen(f"{base}/static/console.js?t={TOKEN}") as r:
        assert r.headers["Content-Type"].startswith("text/javascript")
        assert b"EventSource" in r.read()
    status, body = get(f"{base}/api/fleet?t={TOKEN}")
    fleet = json.loads(body)
    assert status == 200 and fleet["schema"] == "stringency.console_fleet/1"
    assert fleet["projects"][0]["project_id"] == p.config.project_id
    assert fleet["projects"][0]["driver"]["step"] == "Label the groups"
    groups = {g["key"]: g["cards"] for g in fleet["inbox"]}
    assert groups["disagreement"][0]["title"] == "Label the groups, item A"
    status, body = get(f"{base}/api/project/{p.config.project_id}?t={TOKEN}")
    proj = json.loads(body)
    assert status == 200 and proj["timeline"][0]["events"][0]["text"].startswith("opened by")
    assert [s["status"] for s in proj["steps"]][:2] == ["completed", "completed"]
    h = queue(p)[0]
    status, body = get(f"{base}/api/hold/{h['hold_id']}?t={TOKEN}")
    hold = json.loads(body)
    assert (
        status == 200
        and hold["ask"] == "disagreement"
        and hold["project_id"] == p.config.project_id
    )
    assert "operator_reason" in hold and hold["replicates"] and "verdicts" in hold
    assert get(f"{base}/api/nothing?t={TOKEN}")[0] == 404
    assert get(f"{base}/api/fleet")[0] == 403
