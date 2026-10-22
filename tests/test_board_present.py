"""`stringency board` and `stringency present` (design 14.1, 14.4): a progress board that loads
no plugin, and the method-driven view of a delivery or a hold."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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
    assert any(s["title"] == "Echo-back" and s.get("markdown") for s in payload["sections"])
    # the opening hold's plain block: what confirming means, and the echo-back's summary
    assert payload["check"].startswith("The engine read the three declaration files")
    assert payload["found"] and "input" in payload["found"]
    assert len(payload["guidance"]) == 5 and "What to check:" in render_markdown(payload)
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
    assert "waits for" in md and "--verdict reject" in md
    assert "What the engine found: something looked off" in md and "| n | 1 |" in md


def test_present_skips_a_tables_leading_comment_lines(make_project: InitFn) -> None:
    """Backlog L25: the draft exclusion file opens with a `# draft written by ...` line, which was
    read as the header and drew fifty blank rows."""
    p, run_id, d = _delivered(make_project)
    (p.root / "runs" / run_id / "draft.csv").write_text(
        "# draft written by exclusion-proposal 0.2.1; complete the excluded column\n"
        "punch_id,excluded,reason\n24-2-Gut-A,true,most of punch lost\n48-1-Liver,false,\n"
    )
    skills = _skill(p, [{"title": "The draft", "source": "draft.csv", "kind": "table"}])
    payload = present_run(Site.load(p.root), None, skills)
    s = payload["sections"][0]
    assert s["columns"] == ["punch_id", "excluded", "reason"]
    assert s["rows"] == [["24-2-Gut-A", "true", "most of punch lost"], ["48-1-Liver", "false", ""]]


def test_hold_view_where_filters_a_table_by_the_proposed_parameter(make_project: InitFn) -> None:
    """Backlog L26: the organ sign-off shows the punches the proposed organ keeps."""
    p, run_id, d = _delivered(make_project)
    (p.root / "runs" / run_id / "punches.csv").write_text(
        "punch_id,organ,animal\n6-1-Liver,liver,6-1\n6-1-Lung,lung,6-1\n24-1-Liver,liver,24-1\n"
    )
    skills = _skill(
        p,
        [],
        hold_view=[
            {
                "predicate": "param.agent_proposed",
                "source": "punches.csv",
                "kind": "table",
                "where": {"column": "organ", "equals": "$param.organ"},
            },
            {
                "predicate": "param.agent_proposed",
                "source": "punches.csv",
                "kind": "table",
                "where": {"column": "animal", "equals": "6-1"},
            },
            {
                "predicate": "param.agent_proposed",
                "source": "punches.csv",
                "kind": "table",
                "where": {"column": "organ", "equals": "$param.ndim"},
            },
        ],
    )
    hid = p.store.create_hold(
        {
            "run_id": run_id,
            "step_id": "04_compare",
            "kind": "flag",
            "reason": "param.agent_proposed: the agent chose organ",
            "waits_on_role": "reviewer",
            "context_json": json.dumps(
                {
                    "predicate": "param.agent_proposed@1",
                    "evidence": {"proposed": {"organ": {"default": "unset", "proposed": "liver"}}},
                }
            ),
        }
    )
    hp = present_hold(Site.load(p.root), hid, skills)
    by_param, literal, missing = hp["sections"]
    assert by_param["rows"] == [["6-1-Liver", "liver", "6-1"], ["24-1-Liver", "liver", "24-1"]]
    assert "note" not in by_param
    assert literal["rows"] == [["6-1-Liver", "liver", "6-1"], ["6-1-Lung", "lung", "6-1"]]
    assert len(missing["rows"]) == 3 and "proposes no value for ndim" in missing["note"]
    text = render_markdown(hp)
    assert (
        "(where organ = $param.ndim: this hold proposes no value for ndim; every row is shown)"
        in text
    )


def test_present_hold_shows_the_replicates_judgments_by_default(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A judgment item hold with no view from the method's skill shows the replicates' calls for
    the item (backlog K5), so the person decides on what was written at judgment time."""
    from stringency.review import queue, record_review
    from tests.conftest import accept_hold
    from tests.test_run import HARNESS, MOCK, cli

    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(p, "propose", "01_filter", "--set", "min_value=12", "--reason", "t", "--json", env=env)
    assert r.exit_code == 10, r.output
    record_review(p, queue(p)[0]["hold_id"], "accept", reason="fine")
    cli(p, "run", env=env)
    item = queue(p)[0]
    assert item["kind"] == "run_disagreement" and item["item_id"]
    payload = present_hold(Site.load(p.root), item["hold_id"], skills_dir=None)
    titles = [s["title"] for s in payload["sections"]]
    assert any(t.startswith("The replicates' judgments for") for t in titles), titles
    sec = next(s for s in payload["sections"] if s["title"].startswith("The replicates"))
    assert sec["kind"] == "table" and "replicate" in sec["columns"]
    assert all(
        row[sec["columns"].index("item_id")] == item["item_id"] for row in sec["rows"]
    ) or all(row[sec["columns"].index("item")] == item["item_id"] for row in sec["rows"])


def test_plain_block_says_what_was_checked_and_found() -> None:
    """The console's and `present`'s plain block for a flag hold: the predicate's first
    docstring sentence, the reason without its id prefix, the evidence as name and value rows
    with the proposal's own tables left out (the owner, 2026-10-22)."""
    from stringency.console import plain_block

    h = {"reason": "param.reason_unmatched: a numeral in the reason matches no cited cell: 5"}
    ctx = {
        "predicate": "param.reason_unmatched@1",
        "evidence": {
            "numerals": "5",
            "floor": 2000.0,
            "flag": True,
            "nested": {"a": 1.5, "b": [1, 2]},
            "proposed": {"x": {"default": 1}},
            "cited": [{"source": "s"}],
            "list": [1, 2.5, "z"],
        },
    }
    b = plain_block(h, ctx)
    # the predicate's own summary when it has one
    assert b["check"] == (
        "Every number in the operator's reason must appear in a cell the proposal cites or be "
        "a value the proposal sets; this lists the numbers that do neither."
    )
    assert b["found"] == "a numeral in the reason matches no cited cell: 5"
    assert b["compared"] == [
        {"name": "numerals", "value": "5"},
        {"name": "floor", "value": "2000"},
        {"name": "flag", "value": "yes"},
        {"name": "nested.a", "value": "1.5"},
        {"name": "list", "value": "1, 2.5, z"},
    ]
    none = plain_block({"reason": "x"}, {"predicate": "no.such@1", "evidence": None})
    assert none == {"check": None, "found": "x", "compared": []}
    # a proposal hold's finding is a sentence built from the proposal
    ctx = {
        "predicate": "param.agent_proposed@2",
        "evidence": {
            "proposed": {"flavor": {"default": "seurat", "proposed": "seurat"}, "n_top_genes": {}},
            "cited": [
                {"source": "01_qc/qc_summary", "value": 320},
                {"source": "x", "missing": "no"},
            ],
            "considered": ["seurat", "seurat_v3"],
        },
    }
    b = plain_block({"reason": "param.agent_proposed: cites 1 cell(s)"}, ctx)
    assert b["found"] == (
        "The operator proposed values for flavor and n_top_genes, citing 1 cell of "
        "01_qc/qc_summary, after weighing seurat, seurat_v3. The decision table shows each "
        "value beside its default."
    )
    assert b["check"].startswith("The operator chose a value for a parameter")
    # the docstring heuristic drops parenthesised asides and cuts at the earliest end
    from stringency.console import _first_sentence

    assert (
        _first_sentence(
            "The agent proposes, the person approves (owner decision 2026-09-18; roadmap Lane A 5a): an admitted parameter. More."
        )
        == "The agent proposes, the person approves"
    )
    assert _first_sentence("Plain sentence. Then more") == "Plain sentence."


def test_present_hold_markdown_opens_with_the_plain_block(make_project: InitFn) -> None:
    from stringency.review import queue
    from stringency.runs import open_or_resume
    from stringency.steps import propose
    from tests.conftest import accept_hold

    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    propose(rc, "01_filter", {"min_value": 12}, rationale="Twelve is the floor here.")
    h = queue(p)[0]
    payload = present_hold(Site.load(p.root), h["hold_id"])
    assert payload["found"].startswith(
        "The operator proposed a value for min_value, citing nothing."
    )
    assert payload["check"] and payload["compared"] == []
    text = render_markdown(payload)
    assert "What was checked: The operator chose a value for a parameter" in text
    assert "What the engine found: " in text and "The engine recorded" not in text


def test_md_html_renders_the_engines_markdown() -> None:
    from stringency.present import md_html

    text = (
        "# Echo-back\n\nThis is the reading.\n\n640 cells (input object);\nmore.\n\n"
        "## What leaves\n\n- operator session: class 3\n  to: the model\n- another\n\n"
        "Bound to:\n  design.yml: abc\n  inputs.yml: def\n\n```\nx < 1\n```\n"
    )
    html = md_html(text, "Echo-back")
    assert html.startswith("<p>This is the reading.</p>")
    assert "<p>640 cells (input object); more.</p>" in html
    assert "<h4>What leaves</h4>" in html
    assert "<ul><li>operator session: class 3 to: the model</li><li>another</li></ul>" in html
    assert "<p>Bound to:</p>" in html and "<tr><th>design.yml</th><td>abc</td></tr>" in html
    assert "<pre>x &lt; 1</pre>" in html
    assert md_html("# Other\n\ntext", "Echo-back").startswith("<h3>Other</h3>")
