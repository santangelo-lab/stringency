"""`stringency board` and `stringency present` (design 14.1, 14.4): a progress board that loads
no plugin, and the method-driven view of a delivery or a hold."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from stringency.board import BOARD_FILE, board, project_entry, refresh_if_present, write_board
from stringency.deliver import deliver
from stringency.present import Site, present_hold, present_run, render_markdown
from stringency.runs import load_run
from tests.conftest import InitFn
from tests.test_deliver import completed_project
from tests.test_run import cli


def _delivered(make_project: InitFn):  # type: ignore[no-untyped-def]
    p, run_id = completed_project(make_project)
    d = deliver(load_run(p, run_id))
    return p, run_id, d


def test_board_lists_projects_in_words_and_writes_status(
    make_project: InitFn, tmp_path: Path
) -> None:
    p, run_id, d = _delivered(make_project)
    (tmp_path / "superseded").mkdir()
    (tmp_path / "declarations").mkdir()
    entries, text = board(tmp_path)
    names = [e["name"] for e in entries]
    assert names == [p.root.name], (
        names
    )  # the method repo, the data dir and the skip dirs are not projects
    e = entries[0]
    assert e["confirm"] == "accepted" and e["run"]["status"] == "completed" and e["step"] is None
    assert set(e["delivered"]["files"]) == {f["file"] for f in d.files}
    assert "The latest run completed." in text and "Delivered:" in text
    assert f"run {run_id}" not in text  # the id appears only inside the delivery path
    target = write_board(tmp_path)
    assert target == tmp_path / BOARD_FILE and target.read_text().splitlines()[0].startswith(
        "# Status"
    )
    first = target.read_text()
    write_board(tmp_path)
    same = lambda t: "\n".join(t.splitlines()[3:])  # noqa: E731 - drop the timestamp line
    assert same(first) == same(target.read_text())  # idempotent apart from the time


def test_board_reports_pending_confirm_and_unreadable(make_project: InitFn, tmp_path: Path) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    e = project_entry(p.root)
    assert e["confirm"] == "pending" and e["holds"][0]["kind"] == "confirm"
    assert e["holds"][0]["waits_on"] == p.config.roles.owner and e["run"] is None
    broken = tmp_path / "broken"
    (broken / "prov").mkdir(parents=True)
    (broken / "stringency.yml").write_text("not: [valid")
    (broken / "prov" / "run.db").write_text("")
    b = project_entry(broken)
    assert "error" in b and "unreadable" in board(tmp_path)[1]


def test_refresh_if_present_only_when_status_exists(make_project: InitFn, tmp_path: Path) -> None:
    p, _, _ = _delivered(make_project)
    refresh_if_present(p.root)
    assert not (tmp_path / BOARD_FILE).exists()
    (tmp_path / BOARD_FILE).write_text("stale\n")
    refresh_if_present(p.root)
    assert p.root.name in (tmp_path / BOARD_FILE).read_text()


def _skill(p, items, hold_view=None):  # type: ignore[no-untyped-def]
    d = p.method_root / "skills"
    d.mkdir(exist_ok=True)
    doc = {
        "skill": 1,
        "pipeline": p.config.pipeline,
        "after_delivery": items,
        "never_show": ["run ids", "hashes"],
        "hold_view": hold_view or [],
    }
    (d / f"{p.config.pipeline}.yml").write_text(yaml.safe_dump(doc))
    return d


def test_present_renders_skill_tables_files_and_formats(make_project: InitFn) -> None:
    p, run_id, d = _delivered(make_project)
    table = next(f["file"] for f in d.files if f["file"].endswith(".tsv"))
    other = next(f["file"] for f in d.files if f["file"].endswith(".md"))
    run_dir = p.root / "runs" / run_id
    (run_dir / "extra.jsonl").write_text(
        json.dumps(
            {"item_id": "g1", "label": "up", "confidence": 0.5, "evidence": {"a": 1, "b": 2}}
        )
        + "\n"
        + json.dumps({"item_id": "g2", "label": "down", "confidence": 0.25, "evidence": ["x", "y"]})
        + "\n"
    )
    (run_dir / "nested.json").write_text(
        json.dumps({"summary": {"items": [{"k": 1234.5, "share": 0.1234}]}})
    )
    _skill(
        p,
        [
            {"title": "The table", "source": table, "kind": "table"},
            {
                "title": "Judgments",
                "source": "extra.jsonl",
                "kind": "jsonl",
                "columns": ["item_id", "confidence", "evidence"],
                "format": {"confidence": "percent"},
            },
            {
                "title": "Nested",
                "source": "nested.json",
                "kind": "json_table",
                "path": "summary.items",
                "format": {"k": "int", "share": "2f"},
            },
            {"title": "Report", "source": other, "kind": "file"},
            {"title": "Gone", "source": "missing.csv", "kind": "table"},
            {"title": "Odd", "source": table, "kind": "hologram"},
        ],
    )
    site = Site.load(p.root)
    payload = present_run(site, None)
    assert payload["run_id"] == run_id and payload["never_show"] == ["run ids", "hashes"]
    by = {s["title"]: s for s in payload["sections"]}
    assert by["The table"]["kind"] == "table" and by["The table"]["rows"]
    j = by["Judgments"]
    assert j["columns"] == ["item_id", "confidence", "evidence"]
    assert j["rows"][0] == ["g1", "50.0%", "a=1; b=2"] and j["rows"][1][2] == "x, y"
    assert by["Nested"]["rows"] == [["1,234", "0.12"]] or by["Nested"]["rows"] == [
        ["1,234", "0.12"]
    ]
    assert by["Report"]["kind"] == "file" and payload["files"] == [by["Report"]["path"]]
    assert "not found" in by["Gone"]["error"] and "unknown kind" in by["Odd"]["error"]
    md = render_markdown(payload)
    assert (
        "### Judgments" in md and "Files to send:" in md and "Not shown, by the method's rule" in md
    )
    r = cli(p, "present", "--json")
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["schema"] == "stringency.present/1"


def test_present_degrades_to_default_without_or_with_malformed_skill(make_project: InitFn) -> None:
    p, run_id, d = _delivered(make_project)
    site = Site.load(p.root)
    payload = present_run(site, run_id)
    assert payload["sections"] == [] and len(payload["deliverables"]) == len(d.files)
    assert "engine default" in payload["skill"]
    assert "Deliverables:" in render_markdown(payload)
    skills = p.method_root / "skills"
    skills.mkdir(exist_ok=True)
    (skills / f"{p.config.pipeline}.yml").write_text("skill: 2\nafter_delivery: 3\n")
    payload = present_run(site, run_id)
    assert payload["sections"] == [] and "engine default" in payload["skill"]
    (skills / f"{p.config.pipeline}.yml").write_text("skill: [\n")
    assert "engine default" in present_run(site, run_id)["skill"]


def test_present_hold_shows_review_commands_and_matching_view(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    site = Site.load(p.root)
    h = p.confirm_hold()
    payload = present_hold(site, h["hold_id"])
    assert payload["hold_kind"] == "confirm" and payload["waits_on"] == p.config.roles.owner
    assert payload["review"]["accept"].startswith(
        f"stringency review --verdict accept --hold {h['hold_id']}"
    )
    assert any(s["title"] == "Echo-back" for s in payload["sections"])
    # a flag hold with evidence and a matching hold_view table
    p2, run_id, _ = _delivered(make_project)
    site2 = Site.load(p2.root)
    run_dir = p2.root / "runs" / run_id
    (run_dir / "proposal.csv").write_text("item,verdict\ng1,exclude\n")
    _skill(
        p2,
        [],
        hold_view=[
            {"predicate": "toy.flagged", "source": "proposal.csv", "kind": "table"},
            {"predicate": "other.pred", "source": "proposal.csv", "kind": "table"},
        ],
    )
    hid = p2.store.create_hold(
        {
            "run_id": run_id,
            "step_id": "04_compare",
            "kind": "flag",
            "reason": "toy.flagged: something looked off",
            "waits_on_role": "reviewer",
            "context_json": json.dumps({"predicate": "toy.flagged@1", "evidence": {"n": 1}}),
        }
    )
    payload = present_hold(site2, None)
    assert payload["hold_id"] == hid and payload["predicate"] == "toy.flagged@1"
    assert [s["title"] for s in payload["sections"]] == ["proposal.csv"] and payload["sections"][0][
        "rows"
    ] == [["g1", "exclude"]]
    md = render_markdown(payload)
    assert "waits for" in md and "Evidence: n=1" in md and "--verdict reject" in md
