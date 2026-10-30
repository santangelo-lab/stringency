"""L134 and L132: the operator loop and open projects on the console.

L134: `present --step` on a held run and its `rendered` mark; the hold payload's `console_url`;
`--detach` and `wait --job` (a slow toy step, in real processes); `judgments --dispatch --print`
and `run --print-requests`; a view's `where:` clause and its lint; `--out` on `run`, `deliver`
and `present`. L132: an open project idle after its last call reads "open, idle since"; the
archive marker; the console names a plugin it cannot load instead of a 404.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from stringency import git
from stringency.board import board, project_entry, sentence
from stringency.lint import lint_path
from stringency.present import Site, apply_where, parse_where
from stringency.project import Project
from stringency.review_serve import make_server
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_steps import questions  # noqa: F401 - the fixture
from tests.test_review_serve import TOKEN, get
from tests.test_run import HARNESS, MOCK, MOCK_DISPATCH, cli

SPLIT = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}


def _confirmed(make_project: InitFn, **kw: object) -> Project:
    p = make_project(**kw)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    return p


def _acknowledged(p: Project) -> Project:
    """A child process does not see the test's egress patch (conftest): open the egress hold
    the engine would open and accept it, so the child runs as the foreground verb would."""
    from stringency.project import Project as P

    P.load(p.root).ensure_egress_hold()
    for h in p.store.all(
        "SELECT hold_id FROM holds WHERE kind = 'egress' AND resolved_by_review IS NULL"
    ):
        accept_hold(p.store, h["hold_id"])
    return p


@pytest.fixture
def held(make_project: InitFn) -> Project:
    """toy-engine held at item holds on 03_label; 01_filter and 02_summarize completed."""
    p = _confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "run", env=SPLIT)
    assert r.exit_code == 10, r.output
    return p


def _page_url(url: str = "http://127.0.0.1:9765", extra: str = "") -> Path:
    cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "stringency" / "notify.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(f"page_url: {url}\n{extra}")
    return cfg


# -- (a) present --step -------------------------------------------------------------------------


def test_present_step_renders_a_completed_step_of_a_held_run_and_marks_it(held: Project) -> None:
    r = cli(held, "present", "--step", "01_filter", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["kind"] == "step" and out["step_id"] == "01_filter"
    assert out["status"] == "completed" and out["run_status"] == "held"
    assert [o["name"] for o in out["outputs"]] == ["object"]
    table = out["sections"][0]
    assert table["kind"] == "table" and table["columns"][:2] == ["row_id", "group"]
    assert table["source"] == "01_filter/object.csv"
    ev = held.store.all(
        "SELECT payload_json FROM step_events WHERE step_id = '01_filter' AND event = 'rendered'"
    )
    assert len(ev) == 1
    mark = json.loads(ev[0]["payload_json"])
    assert mark["verb"] == "present --step" and mark["ts"].endswith("Z")
    presented = held.store.one("SELECT payload_json FROM run_events WHERE event = 'presented'")
    assert json.loads(presented["payload_json"])["step_id"] == "01_filter"
    human = cli(held, "present", "--step", "01_filter").output
    assert human.startswith("## Filter low-value rows: completed (the run is held)")
    # a step that is not completed is refused with the reason
    r = cli(held, "present", "--step", "03_label")
    assert r.exit_code == 15 and "03_label is held" in str(r.stderr)
    r = cli(held, "present", "--step", "nope")
    assert r.exit_code == 15 and "no step nope" in str(r.stderr)


def test_present_step_shows_the_methods_views_of_the_step(held: Project) -> None:
    run_id = held.store.scalar("SELECT run_id FROM runs")
    d = held.method_root / "skills"
    d.mkdir(exist_ok=True)
    (d / "toy-engine.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "pipeline": "toy-engine",
                "after_delivery": [],
                "hold_view": [
                    {
                        "step": "03_label",
                        "title": "Group A's rows",
                        "source": "01_filter/object.csv",
                        "kind": "table",
                        "columns": ["row_id", "group", "value"],
                        "where": "group = A",
                    }
                ],
            }
        )
    )
    out = json.loads(cli(held, "present", "--step", "01_filter", "--run", run_id, "--json").output)
    assert [s["title"] for s in out["sections"]] == ["Group A's rows"]
    sec = out["sections"][0]
    assert sec["rows"] and all(r[1] == "A" for r in sec["rows"])


def test_propose_carries_the_rendered_marks(held: Project) -> None:
    cli(held, "present", "--step", "01_filter")
    r = cli(held, "propose", "04_compare", "--json", env=SPLIT)
    assert r.exit_code in (0, 10), r.output + str(r.stderr)
    ev = held.store.one(
        "SELECT payload_json FROM step_events WHERE step_id = '04_compare' "
        "AND event = 'status:proposed' ORDER BY seq DESC LIMIT 1"
    )
    marks = json.loads(ev["payload_json"])["rendered"]
    assert [(m["step_id"], m["verb"]) for m in marks] == [("01_filter", "present --step")]


# -- (b) the console link -----------------------------------------------------------------------


def test_hold_payloads_carry_the_console_link_from_page_url(held: Project) -> None:
    out = json.loads(cli(held, "run", "--json", env=SPLIT).output)
    assert out["console_url"] is None  # no notify file: no link and no error
    hid = out["holds"][0]["hold_id"]
    _page_url(extra="notify: off\n")  # the owner's file: page_url, no channels
    out = json.loads(cli(held, "run", "--json", env=SPLIT).output)
    assert out["console_url"] == f"http://127.0.0.1:9765/hold/{hid}"
    pres = json.loads(cli(held, "present", "--hold", hid, "--json").output)
    assert pres["console_url"] == f"http://127.0.0.1:9765/hold/{hid}"
    _page_url("http://127.0.0.1:8765/?t=tok")
    pres = json.loads(cli(held, "present", "--hold", hid, "--json").output)
    assert pres["console_url"] == f"http://127.0.0.1:8765/hold/{hid}?t=tok"
    assert "9765" not in cli(held, "run", env=SPLIT).output  # the terse message is unchanged


def test_a_held_call_carries_the_console_link(questions: Project) -> None:  # noqa: F811
    _page_url()
    r = cli(questions, "call", "compare-groups", "--set", "correction=bonferroni", "--json")
    assert r.exit_code == 10, r.output + str(r.stderr)
    out = json.loads(r.output)
    hid = out["next"]["holds"][0]["hold_id"]
    assert out["console_url"] == f"http://127.0.0.1:9765/hold/{hid}"


# -- (c) --detach and wait --job ----------------------------------------------------------------


def _engine(cwd: Path, *args: str, env: dict[str, str] | None = None, stdin: str | None = None):  # type: ignore[no-untyped-def]
    return subprocess.run(
        [sys.executable, "-P", "-m", "stringency.cli.app", *args],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.egress
def test_detach_returns_at_once_and_wait_job_prints_what_the_verb_printed(
    make_project: InitFn, method_repo: MethodRepo
) -> None:
    script = method_repo.path / "modules" / "filter-rows" / "filter_rows.py"
    script.write_text(
        script.read_text().replace("import sys\n", "import sys\nimport time\n\ntime.sleep(3)\n", 1)
    )
    method_repo.commit("a slow filter")
    git.tag(method_repo.path, "v0.1.1")
    p = _confirmed(
        make_project,
        pipeline="toy-engine",
        execution="engine",
        method=f"{method_repo.path}@v0.1.1",
    )
    _acknowledged(p)
    t0 = time.monotonic()
    r = _engine(p.root, "run", "--detach", "--json", env=SPLIT)
    took = time.monotonic() - t0
    assert r.returncode == 0, r.stdout + r.stderr
    job = json.loads(r.stdout)
    assert set(job) >= {"job_id", "pid", "log"} and took < 2.5, (job, took)
    d = p.root / "prov" / "jobs" / job["job_id"]
    assert json.loads((d / "job.json").read_text())["argv"] == ["stringency", "run", "--json"]
    # the step sleeps three seconds: a short wait says the job is still running
    w = _engine(p.root, "wait", "--job", job["job_id"], "--for", "0.5", "--json")
    assert w.returncode == 10, (w.stdout, w.stderr)
    assert json.loads(w.stdout)["state"] == "running", (w.stdout, w.stderr)
    w = _engine(p.root, "wait", "--job", job["job_id"])
    assert w.returncode == 10, w.stdout + w.stderr  # the run's own exit: held
    out = json.loads(w.stdout)
    assert out["kind"] == "held" and out["completed_steps"] == ["01_filter", "02_summarize"]
    assert json.loads((d / "exit.json").read_text())["exit_code"] == 10
    # what the foreground verb prints now, for comparison: the same payload's shape
    again = json.loads(cli(p, "run", "--json", env=SPLIT).output)
    assert (
        again["kind"] == out["kind"] and again["holds"][0]["hold_id"] == out["holds"][0]["hold_id"]
    )


def test_detach_keeps_stdin_and_wait_job_refusals(
    held: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from stringency import __version__
    from stringency.jobs import detach, wait_job

    monkeypatch.chdir(held.root)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"the script\n")))
    job = detach(["--version", "-", "--detach"])
    d = held.root / "prov" / "jobs" / job["job_id"]
    assert (d / "stdin").read_text() == "the script\n"
    res = wait_job(held.root, job["job_id"], timeout=60, poll=0.1)
    assert res.state == "exited" and res.exit_code == 0 and res.stdout.strip() == __version__
    r = cli(held, "wait", "--job", "NOPE")
    assert r.exit_code == 15 and "no job NOPE" in str(r.stderr)
    r = cli(held, "wait", "--job", "a", "--hold", "b")
    assert r.exit_code == 15
    # in-process there is no command line to start again
    r = cli(held, "deliver", "--detach")
    assert r.exit_code == 15 and "--detach" in str(r.stderr)
    # a deliver of a held run, detached: its refusal and exit code come back through wait
    r = _engine(held.root, "deliver", "--detach", "--json")
    assert r.returncode == 0, r.stderr
    w = _engine(held.root, "wait", "--job", json.loads(r.stdout)["job_id"])
    assert w.returncode != 0 and w.stderr.strip(), (w.returncode, w.stdout, w.stderr)


# -- (d) the requests inline --------------------------------------------------------------------


def test_judgments_dispatch_print_and_run_print_requests(make_project: InitFn) -> None:
    p = _confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "judgments", "--dispatch", "--json")
    assert r.exit_code == 16 and "nothing is dispatching" in str(r.stderr)
    r = cli(p, "run", "--json", "--print-requests", env=MOCK_DISPATCH)
    assert r.exit_code == 20, r.output
    out = json.loads(r.output)
    assert (
        out["requests_inline"] is True and len(out["requests"]) == out["requests"][-1]["replicate"]
    )
    req = out["requests"][0]
    assert {"nonce", "prompt", "schema", "response_file", "request_file"} <= set(req)
    r = cli(p, "judgments", "--dispatch", "--print", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    got = json.loads(r.output)
    assert got["step_id"] == "03_label" and got["requests_inline"] is True
    assert [q["nonce"] for q in got["requests"]] == [q["nonce"] for q in out["requests"]]
    assert got["manifest"]["replicates"] == len(got["requests"])
    paths = json.loads(cli(p, "judgments", "--dispatch", "--json").output)["requests"]
    assert all(isinstance(x, str) and x.endswith(".json") for x in paths)
    assert cli(p, "judgments").exit_code == 15
    # without the flag the run payload names the directory only
    plain = json.loads(cli(p, "run", "--json", env=MOCK_DISPATCH).output)
    assert "requests_inline" not in plain


# -- (e) where: ---------------------------------------------------------------------------------


def test_where_clause_parses_and_filters() -> None:
    assert parse_where("unit_kind = animal") == ("unit_kind", ["animal"])
    assert parse_where("unit_kind in animal, punch") == ("unit_kind", ["animal", "punch"])
    rows = [{"k": "a", "v": 1}, {"k": "b", "v": 2}, {"k": "c", "v": 3}]
    assert [r["v"] for r in apply_where(rows, "k in a,c")] == [1, 3]
    assert apply_where(rows, "v = 2") == [{"k": "b", "v": 2}]
    for bad in ("k", "k ~ a", "k in a,,b"):
        with pytest.raises(ValueError):
            parse_where(bad)
    with pytest.raises(ValueError, match="no column z"):
        apply_where(rows, "z = 1")


def test_lint_errors_on_a_where_column_the_view_does_not_have(method_repo: MethodRepo) -> None:
    d = method_repo.path / "skills"
    d.mkdir(exist_ok=True)
    (d / "toy.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "pipeline": "toy",
                "after_delivery": [
                    {"source": "a.csv", "kind": "table", "columns": ["k", "v"], "where": "k = a"},
                    {"source": "b.csv", "kind": "table", "columns": ["k", "v"], "where": "z = a"},
                    {"source": "c.csv", "kind": "table", "where": "k ~ a"},
                    {"source": "d.csv", "kind": "table", "where": "anything = 1"},
                ],
            }
        )
    )
    errors = [e for e in lint_path(method_repo.path).errors if "where" in e]
    assert len(errors) == 2, errors
    assert "after_delivery[1]" in errors[0] and "column z" in errors[0]
    assert "after_delivery[2]" in errors[1]


def test_present_applies_where_and_names_a_missing_column(held: Project) -> None:
    d = held.method_root / "skills"
    d.mkdir(exist_ok=True)
    (d / "toy-engine.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "pipeline": "toy-engine",
                "step_view": [
                    {
                        "step": "01_filter",
                        "source": "01_filter/object.csv",
                        "kind": "table",
                        "where": "unit in u1,u4",
                        "title": "two units",
                    },
                    {
                        "step": "01_filter",
                        "source": "01_filter/object.csv",
                        "kind": "table",
                        "where": "animal = 1",
                        "title": "no such column",
                    },
                ],
            }
        )
    )
    out = json.loads(cli(held, "present", "--step", "01_filter", "--json").output)
    two, missing = out["sections"]
    unit = two["columns"].index("unit")
    assert two["rows"] and {r[unit] for r in two["rows"]} == {"u1", "u4"}
    assert "no column animal" in missing["error"]


# -- (f) --out ----------------------------------------------------------------------------------


def test_out_writes_the_payload_and_prints_a_line(held: Project, tmp_path: Path) -> None:
    f = tmp_path / "run.json"
    r = cli(held, "run", "--json", "--out", str(f), env=SPLIT)
    assert r.exit_code == 10, r.output
    small = json.loads(r.output)
    assert small["out"] == str(f) and small["payload_schema"] == "stringency.next/1"
    assert small["summary"].startswith("held: hold ")
    assert json.loads(f.read_text())["kind"] == "held" and small["bytes"] == len(f.read_bytes())
    g = tmp_path / "present.json"
    r = cli(held, "present", "--step", "01_filter", "--out", str(g))
    assert r.exit_code == 0 and r.output.startswith(f"wrote {g} (")
    assert json.loads(g.read_text())["step_id"] == "01_filter"


def test_deliver_out(make_project: InitFn, tmp_path: Path) -> None:
    from tests.test_deliver import completed_project

    p, run_id = completed_project(make_project)
    f = tmp_path / "deliver.json"
    r = cli(p, "deliver", "--out", str(f))
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert r.output.count("\n") == 1 and f"delivered run {run_id}" in r.output
    assert json.loads(f.read_text())["schema"] == "stringency.deliver/1"


# -- L132 ---------------------------------------------------------------------------------------


def test_an_idle_open_project_reads_open_with_its_last_call(questions: Project) -> None:  # noqa: F811
    q = questions
    qid = json.loads(cli(q, "ask", "Which group is higher?", "--json").output)["question_id"]
    r = cli(q, "call", "compare-groups", "--question", qid, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert cli(q, "deliver").exit_code == 0
    e = project_entry(q.root)
    run = e["run"]
    assert run["status"] == "running"  # the trace's derived status (design 7.1) is unchanged
    last = q.store.scalar(
        "SELECT MAX(ts) FROM step_events WHERE run_id = ? AND event != 'rendered'",
        (run["run_id"],),
    )
    assert run["state"] == "open" and run["idle_since"] == last
    assert run["questions"] == 1 and e["step"] is None
    s = sentence(e)
    assert f"open, idle since {last[:10]} {last[11:16]} UTC: 1 question(s)" in s
    _, text = board(q.root.parent)
    assert f"| open, idle since {last[:10]}" in text
    # a held call is not idle
    r = cli(q, "call", "compare-groups", "--set", "correction=bonferroni", "--json")
    assert r.exit_code == 10
    assert "state" not in project_entry(q.root)["run"]


def test_archive_marks_the_project_and_the_board_skips_it(held: Project) -> None:
    root = held.root.parent
    names = [e["name"] for e in board(root)[0]]
    assert held.root.name in names
    r = cli(held, "archive", "--reason", "a rehearsal, kept for the record", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.stdout)
    marker = held.root / "prov" / "archived.json"
    assert out["marker"] == str(marker) and json.loads(marker.read_text())["reason"].startswith(
        "a rehearsal"
    )
    assert "open hold(s) stay open" in str(r.stderr)
    assert held.root.name not in [e["name"] for e in board(root)[0]]
    assert project_entry(held.root)["archived"]["reason"].startswith("a rehearsal")
    r = cli(held, "archive", "--reason", "again")
    assert r.exit_code == 16 and "already archived" in str(r.stderr)
    assert cli(held, "archive", "--reason", " ").exit_code == 15
    # nothing in the trace changed
    assert held.store.scalar("SELECT COUNT(*) FROM run_events WHERE event LIKE '%archiv%'") == 0


@pytest.fixture
def console(held: Project) -> Iterator[tuple[str, Project]]:
    srv = make_server([held.root], port=0, token=TOKEN)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", held
    finally:
        srv.shutdown()
        srv.server_close()


def test_console_lists_archived_projects_apart(console: tuple[str, Project]) -> None:
    base, p = console
    status, body = get(f"{base}/?t={TOKEN}")
    assert status == 200 and "Archived:" not in body
    cli(p, "archive", "--reason", "put away after the rehearsal")
    status, body = get(f"{base}/?t={TOKEN}")
    assert status == 200 and "Archived: 1 project" in body
    assert "put away after the rehearsal" in body
    assert "Nothing waits on a person in 0 projects" in body  # its holds left the inbox


def test_console_names_a_plugin_it_cannot_load(
    console: tuple[str, Project], monkeypatch: pytest.MonkeyPatch
) -> None:
    base, p = console
    hid = p.store.scalar(
        "SELECT hold_id FROM holds WHERE resolved_by_review IS NULL AND kind != 'confirm' LIMIT 1"
    )
    monkeypatch.setattr("stringency.plugins.load_plugins", lambda **_: {})
    status, body = get(f"{base}/hold/{hid}?t={TOKEN}")
    assert status == 503, body
    assert "plugin stringency-toy not installed in this console&#39;s environment" in body
    status, body = get(f"{base}/?t={TOKEN}")
    assert status == 200 and "plugin stringency-toy not installed" in body


def test_the_site_reads_a_step_without_the_plugin(
    held: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stringency.plugins.load_plugins", lambda **_: {})
    site = Site.load(held.root)
    from stringency.present import present_completed_step

    assert present_completed_step(site, None, "02_summarize")["outputs"]
