"""`stringency flag` (the beta-tester package, 2026-11-03): a person says a delivered result is
wrong; the row binds to the file on screen, is append-only, and reaches the run's view."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from stringency import hashing
from stringency.flags import delivered_files, flags_for
from stringency.present import Site, present_run
from tests.conftest import InitFn
from tests.test_board_present import _delivered
from tests.test_review_serve import TOKEN, _serve, get, post
from tests.test_run import cli


def test_flag_binds_to_the_delivered_file_and_is_append_only(make_project: InitFn) -> None:
    p, run_id, d = _delivered(make_project)
    table = next(f["file"] for f in d.files if f["file"].endswith(".tsv"))
    files = delivered_files(p.store, run_id)
    assert table in files and "coverage.md" in files and files[table]["step_id"]
    r = cli(p, "flag", "--object", table, "--reason", "the B group mean is not what I measured")
    assert r.exit_code == 0, r.output
    assert f"{table} (table) from step {files[table]['step_id']}" in r.output
    assert "via tty" in r.output
    r = cli(p, "flag", "--reason", "the whole run looks off", "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["schema"] == "stringency.flag/1" and out["object_name"] is None
    rows = flags_for(p.store, run_id)
    assert [g["object_name"] for g in rows] == [table, None]
    assert rows[0]["object_hash"] and rows[0]["object_kind"] == "table"
    assert rows[0]["step_id"] == files[table]["step_id"]
    assert rows[0]["reason"] == "the B group mean is not what I measured"
    assert rows[1]["step_id"] is None and rows[1]["via"] == "tty"
    ev = p.store.all(
        "SELECT payload_json FROM run_events WHERE run_id = ? AND event = 'flagged'", (run_id,)
    )
    assert [json.loads(e["payload_json"])["object"] for e in ev] == [table, None]
    # the run's view carries them, so the console's JSON route and the bundle see them
    site = Site.load(p.root)
    try:
        assert [g["flag_id"] for g in present_run(site, run_id)["flags"]] == [
            g["flag_id"] for g in rows
        ]
    finally:
        site.store.close()
    # append-only
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        p.store._conn.execute("DELETE FROM flags")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        p.store._conn.execute("UPDATE flags SET reason_ref = 'x'")


def test_flag_refuses_what_the_run_did_not_deliver(make_project: InitFn) -> None:
    p, run_id, _d = _delivered(make_project)
    r = cli(p, "flag", "--object", "nope.tsv", "--reason", "x")
    assert r.exit_code == 15 and "not a delivered file" in r.output
    r = cli(p, "flag", "--step", "99_nothing", "--reason", "x")
    assert r.exit_code == 15 and "no step 99_nothing" in r.output
    r = cli(p, "flag", "--reason", "  ")
    assert r.exit_code == 15 and "needs the person's words" in r.output
    r = cli(p, "flag", "--run", "NOTARUN", "--reason", "x")
    assert r.exit_code == 15 and "no run NOTARUN" in r.output
    assert flags_for(p.store, run_id) == []
    # a session reference makes it a relayed flag, as a relayed review
    r = cli(
        p,
        "flag",
        "--reason",
        "said in chat",
        env={"STRINGENCY_OPERATOR": "claude-code", "STRINGENCY_SESSION_REF": "claude-code:s1"},
    )
    assert r.exit_code == 0, r.output
    g = flags_for(p.store, run_id)[0]
    assert (g["via"], g["operator_harness"], g["operator_session_ref"]) == (
        "relayed",
        "claude-code",
        "claude-code:s1",
    )


def test_console_run_page_offers_a_flag_per_file_and_records_it_via_web(
    make_project: InitFn,
) -> None:
    p, run_id, d = _delivered(make_project)
    table = next(f["file"] for f in d.files if f["file"].endswith(".tsv"))
    for base in _serve(p):
        status, body = get(f"{base}/run/{run_id}?t={TOKEN}")
        assert status == 200
        assert f'action="/flag/{run_id}"' in body and f'name="object" value="{table}"' in body
        assert "Flagged as wrong" not in body
        status, body = post(
            f"{base}/flag/{run_id}?t={TOKEN}", object=table, reason="the counts are wrong"
        )
        assert status == 200 and "Flag recorded" in body, body
        g = flags_for(p.store, run_id)
        assert len(g) == 1 and g[0]["via"] == "web" and g[0]["object_name"] == table
        assert g[0]["object_hash"] == hashing.hash_file(Path(d.path) / table)
        status, body = get(f"{base}/run/{run_id}?t={TOKEN}")
        assert "Flagged as wrong" in body and "the counts are wrong" in body
        # the JSON route carries the flag too
        status, body = get(f"{base}/api/run/{run_id}?t={TOKEN}")
        assert status == 200 and json.loads(body)["flags"][0]["flag_id"] == g[0]["flag_id"]
        # refusals: an empty reason, a file not delivered, no token
        assert post(f"{base}/flag/{run_id}?t={TOKEN}", reason="")[0] == 400
        assert post(f"{base}/flag/{run_id}?t={TOKEN}", object="x.tsv", reason="y")[0] == 400
        assert post(f"{base}/flag/{run_id}", reason="no token")[0] == 403
        assert post(f"{base}/flag/NOTARUN?t={TOKEN}", reason="z")[0] == 404
        assert len(flags_for(p.store, run_id)) == 1
    # the read-only standing instance shows no form and refuses the post
    for base in _serve(p, read_only=True):
        status, body = get(f"{base}/run/{run_id}?t={TOKEN}")
        assert status == 200 and f'action="/flag/{run_id}"' not in body
        assert post(f"{base}/flag/{run_id}?t={TOKEN}", reason="q")[0] == 405
