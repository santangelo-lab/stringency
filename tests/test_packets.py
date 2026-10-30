"""What a person reads on a hold (PLAN L137, L133, L131): the open-mode confirm card and its
bound rows, the four-part packet of every flag, the confidence override on
`judg.confidence_consistent`, `scope: item` views, the hold table's named columns, the lint on
view columns, and the evidence's provenance line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from stringency.config import InputsManifest, Objective
from stringency.echo import OPEN_SWITCH, bound_lines, bound_structure, bound_table
from stringency.exit_codes import ConfigError
from stringency.packets import SAYS, Facts, flag_packet, says_for
from stringency.present import Site, present_hold, presented_line, render_markdown
from stringency.project import Project
from stringency.review import queue, record_review
from stringency.review_render import render, verdicts_for
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_review import held_project


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


# -- L133: the packet of every flag -------------------------------------------------------------


def test_every_registered_predicate_renders_a_packet_with_four_parts() -> None:
    """The packet contract: a question, the rule with the facts, the evidence's scope, and what
    each verdict does, for every predicate the engine and the loaded plugins register; a
    predicate without its own words takes the default ones, so none ships a bare reason."""
    import stringency.predicates.engine  # noqa: F401
    from stringency.plugins import load_plugins
    from stringency.predicates.registry import registry

    load_plugins()
    specs = registry.all()
    assert len(specs) > 40
    for spec in specs:
        phase = "pre" if "pre" in spec.phases else "post"
        h = {
            "hold_id": "H",
            "kind": "flag",
            "reason": f"{spec.id}: the condition it reports",
            "item_id": None,
            "run_id": None,
            "step_id": None,
        }
        for evidence in ({}, {"n": 3, "names": ["a", "b"], "rows": [{"x": 1}]}):
            ctx = {"predicate": spec.ref, "phase": phase, "evidence": evidence}
            p = flag_packet(h, ctx, verdicts_for("flag", "H", phase, predicate=spec.ref))
            assert p["question"].startswith("Is this acceptable") and p["question"].endswith("?")
            assert p["rule"] and all(isinstance(x, str) and x for x in p["rule"]), spec.id
            assert p["evidence"]["scope"] in ("item", "step")
            words = {v["verdict"]: v["effect"] for v in p["verdicts"]}
            assert {"accept", "reject", "defer"} <= set(words) and all(words.values()), spec.id
            assert p["says"] == ("own" if spec.id in SAYS else "default")
            if evidence:
                assert "n: 3" in p["rule"] or spec.id in SAYS, spec.id
    assert {"judg.confidence_consistent", "param.agent_proposed"} <= set(SAYS)


def test_confidence_packet_states_the_rule_with_the_bands_counts_and_contradiction() -> None:
    """The Lyons case (2026-10-29): replicate 1 called domain_1 lamina_propria at high with 9
    supporting and 1 contradicting citations."""
    facts_ctx = {
        "predicate": "judg.confidence_consistent@1",
        "phase": "post",
        "evidence": {
            "items": [
                {
                    "confidence": "high",
                    "contradicting": 1,
                    "item": "domain_1",
                    "replicate": 1,
                    "supporting": 9,
                }
            ]
        },
    }
    says = says_for("judg.confidence_consistent@1")
    assert says.question is not None and says.rule is not None
    facts = Facts(
        predicate="judg.confidence_consistent",
        reason="declared confidence exceeds what the cited evidence supports",
        evidence=facts_ctx["evidence"],
        criteria={
            "high": {"min_supporting": 3, "max_contradicting": 0},
            "medium": {"min_supporting": 2, "max_contradicting": 1},
            "low": {"min_supporting": 1, "max_contradicting": None},
        },
        calls={
            (1, "domain_1"): {
                "label": "lamina_propria",
                "contradicting": [
                    {
                        "table": "composition",
                        "row": "domain_1|enterocyte",
                        "column": "share_of_domain",
                        "value": "0.339",
                    }
                ],
            }
        },
    )
    assert says.question(facts) == (
        "Is this acceptable: reviewer 1 called domain_1 lamina_propria at high confidence, "
        "more than its citations support?"
    )
    rule = says.rule(facts)
    assert rule[0] == (
        "Reviewer 1 called domain_1 lamina_propria at high; high needs at least 3 supporting and "
        "at most 0 contradicting citations; this call cites 9 supporting and 1 contradicting."
    )
    assert rule[1] == (
        "The contradicting citation: composition[domain_1|enterocyte].share_of_domain = 0.339."
    )
    assert "low needs at least 1 supporting citation." in rule[2]
    h = {"hold_id": "H", "item_id": None, "reason": "x", "run_id": None, "step_id": None}
    packet = flag_packet(h, facts_ctx, [])
    assert packet["heading"] == "replicate 1, item domain_1"
    assert packet["evidence"] == {"scope": "item", "items": ["domain_1"]}


def test_judgment_flag_packet_on_a_held_run_and_its_override(make_project: InitFn) -> None:
    """A run held on `judg.confidence_consistent`: the packet from the trace, the fourth verdict,
    and `override --correction confidence=<band>` recorded with the calls it is for."""
    p, _ = held_project(make_project, "context_contradicting.yml")
    h = queue(p)[0]
    payload = present_hold(Site.load(p.root), h["hold_id"])
    packet = payload["packet"]
    assert packet["question"] == (
        "Is this acceptable: 6 calls declare a higher confidence than their citations support?"
    )
    assert any(
        line.startswith("Reviewer 1 called A abundant at medium; medium needs at least 2")
        for line in packet["rule"]
    )
    assert any(line.startswith("The contradicting citations: summary[") for line in packet["rule"])
    assert [v["verdict"] for v in packet["verdicts"]] == ["accept", "override", "reject", "defer"]
    assert payload["review"]["override"].endswith(
        '--correction confidence=<value> --reason "<why>"'
    )
    md = render_markdown(payload)
    assert md.index("Question: ") < md.index("The rule and the facts:") < md.index("override: ")
    # the terminal packet carries the same question and override
    view = render(p, h)
    assert "question: Is this acceptable: 6 calls" in view.text
    assert "--correction confidence=<value>" in view.text
    # refusals: a value the policy has no band for, another field, no correction
    for bad in ({"confidence": "certain"}, {"label": "abundant"}, None):
        with pytest.raises(ConfigError):
            record_review(p, h["hold_id"], "override", reason="lower it", correction=bad)
    r = record_review(
        p, h["hold_id"], "override", reason="labels stand at low", correction={"confidence": "low"}
    )
    assert r.verdict == "override" and r.step_status == "completed"
    row = p.store.one("SELECT correction_json FROM reviews WHERE review_id = ?", (r.review_id,))
    corr = json.loads(row["correction_json"])
    assert corr["confidence"] == "low" and len(corr["calls"]) == 6
    assert {"replicate": 1, "item": "A"} in corr["calls"]


def test_override_is_refused_on_a_flag_without_a_correction(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    hid = p.store.create_hold(
        {
            "run_id": None,
            "step_id": None,
            "kind": "flag",
            "reason": "toy.flagged: something looked off",
            "waits_on_role": "reviewer",
            "context_json": json.dumps({"predicate": "toy.flagged@1", "evidence": {"n": 1}}),
        }
    )
    with pytest.raises(ConfigError, match="accepted or rejected"):
        record_review(p, hid, "override", reason="no", correction={"confidence": "low"})


def test_correction_parses_field_equals_value() -> None:
    from stringency.cli.verb_review import parse_correction

    assert parse_correction("confidence=medium") == {"confidence": "medium"}
    assert parse_correction('{"label": "x"}') == {"label": "x"}
    assert parse_correction(None) is None
    with pytest.raises(ConfigError):
        parse_correction("[1]")


def test_console_offers_the_confidence_override(make_project: InitFn) -> None:
    from tests.test_review_serve import TOKEN, _serve, get, post

    p, _ = held_project(make_project, "context_contradicting.yml")
    h = queue(p)[0]
    for base in _serve(p):
        status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200
        assert '<h1 class="ask-flag">' in body  # a flag on calls, not the consensus
        assert "replicates 1, 2, 3, items A, B" in body
        assert "<h2>The question</h2>" in body and 'name="flag_correction"' in body
        assert all(f'<option value="{b}">' in body for b in ("high", "medium", "low"))
        status, body = post(
            f"{base}/hold/{h['hold_id']}",
            t=TOKEN,
            verdict="override",
            flag_correction="medium",
            reason="the labels stand at medium",
        )
        assert status == 200 and "override on hold" in body
    row = p.store.one("SELECT correction_json, via FROM reviews WHERE hold_id = ?", (h["hold_id"],))
    assert json.loads(row["correction_json"])["confidence"] == "medium" and row["via"] == "web"


def test_scope_item_keeps_the_items_rows_and_each_figure_once(make_project: InitFn) -> None:
    from tests.test_board_present import _skill

    p, _ = held_project(make_project, "context_contradicting.yml")
    h = queue(p)[0]
    run_dir = p.root / "runs" / h["run_id"]
    (run_dir / "groups.csv").write_text("key,group,n\nA|x,A,1\nB|x,B,2\nC|x,C,3\n")
    figs = run_dir / "maps"
    figs.mkdir()
    for name in ("map_A.png", "map_B.png", "map_C.png"):
        (figs / name).write_bytes(b"\x89PNG")
    view = {"predicate": "judg.confidence_consistent", "kind": "table", "source": "groups.csv"}
    _skill(
        p,
        [],
        hold_view=[
            {**view, "title": "scoped", "scope": "item"},
            {**view, "title": "named column", "scope": "item", "item_column": "group"},
            {**view, "title": "step-wide"},
            {
                "predicate": "judg.confidence_consistent",
                "kind": "figures",
                "source": "maps",
                "scope": "item",
                "title": "maps",
            },
            {
                "predicate": "judg.confidence_consistent",
                "kind": "figures",
                "source": "maps",
                "title": "maps again",
            },
        ],
    )
    sections = present_hold(Site.load(p.root), h["hold_id"])["sections"]
    by = {s["title"]: s for s in sections}
    assert [r[1] for r in by["scoped"]["rows"]] == ["A", "B"] and by["scoped"]["scope"] == "item"
    assert [r[1] for r in by["named column"]["rows"]] == ["A", "B"]
    assert len(by["step-wide"]["rows"]) == 3
    assert [im["file"] for im in by["maps"]["images"]] == ["map_A.png", "map_B.png"]
    # the second figures view shows only what the first did not
    assert [im["file"] for im in by["maps again"]["images"]] == ["map_C.png"]


# -- L131: the hold table's columns, the lint, the provenance line ------------------------------


def test_hold_table_adds_the_columns_the_reason_names(make_project: InitFn) -> None:
    from stringency.runs import open_or_resume
    from stringency.steps import propose
    from tests.test_board_present import _skill

    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    propose(
        rc,
        "01_filter",
        {"min_value": 12},
        rationale="Twelve: boundary_share is lowest there and coherence holds.",
    )
    h = queue(p)[0]
    (p.root / "runs" / h["run_id"] / "sweep.csv").write_text(
        "n,coherence,boundary_share,other\n4,0.5,0.13,x\n"
    )
    _skill(
        p,
        [],
        hold_view=[
            {
                "predicate": "param.agent_proposed",
                "title": "sweep",
                "source": "sweep.csv",
                "kind": "table",
                "columns": ["n"],
            }
        ],
    )
    payload = present_hold(Site.load(p.root), h["hold_id"])
    s = payload["sections"][0]
    # the view's own columns first, then the two the operator's reason names; `other` is not
    assert s["columns"] == ["n", "coherence", "boundary_share"]
    assert s["rows"] == [["4", "0.5", "0.13"]]
    assert "coherence, boundary_share" in s["note"]
    assert payload["presented"].startswith("not rendered: the operator proposed without")


def test_provenance_line_reads_a_rendered_step_event(project: Project) -> None:
    from stringency.runs import open_or_resume
    from stringency.steps import propose

    accept_hold(project.store, project.confirm_hold()["hold_id"])
    rc = open_or_resume(project)
    propose(rc, "01_filter", {"min_value": 12}, rationale="twelve")
    later = "2999-01-01T00:00:00Z"
    store = project.store
    assert presented_line(store, rc.run_id, later, [], ["01_filter"]).startswith(
        "not rendered: the operator proposed without rendering the evidence of 01_filter"
    )
    store.step_event(rc.run_id, "01_filter", "rendered", {"by": "present --step"})
    ts = store.scalar(
        "SELECT ts FROM step_events WHERE run_id=? AND event='rendered'", (rc.run_id,)
    )
    assert presented_line(store, rc.run_id, later, [], ["01_filter"]) == (
        f"rendered by present --step 01_filter at {ts}"
    )
    # a rendering after the proposal is not evidence the proposal read
    assert presented_line(store, rc.run_id, "2000-01-01T00:00:00Z", [], ["01_filter"]).startswith(
        "not rendered"
    )


def test_lint_warns_on_view_columns_against_the_produced_output(make_project: InitFn) -> None:
    from stringency.lint import lint_path
    from stringency.present import _header_of
    from tests.test_board_present import _delivered, _skill

    p, run_id, _ = _delivered(make_project)
    art = next(
        a
        for a in p.store.all(
            "SELECT step_id, name, path FROM artifacts WHERE run_id=? AND status='produced'",
            (run_id,),
        )
        if Path(a["path"]).suffix in (".tsv", ".csv") and len(_header_of(Path(a["path"]))) > 1
    )
    header = _header_of(Path(art["path"]))
    _skill(
        p,
        [
            {
                "title": "the table",
                "source": f"{art['step_id']}/{art['name']}",
                "kind": "table",
                "columns": [header[0], "not_a_column"],
            }
        ],
    )
    report = lint_path(p.root)
    text = "\n".join(report.warnings)
    assert f"names column(s) {art['step_id']}/{art['name']} lacks: not_a_column" in text
    assert (
        f"columns of {art['step_id']}/{art['name']} no view shows: " + ", ".join(header[1:]) in text
    )
    # the method repo alone has no run to read a header from: nothing is claimed
    assert not any("no view shows" in w for w in lint_path(p.method_root).warnings)


# -- L137: the open-mode confirm hold ------------------------------------------------------------


def test_open_confirm_hold_carries_the_bound_rows_and_the_card_branches(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    from tests.test_open_init import delivered_process, open_project
    from tests.test_review_serve import TOKEN, _serve, get

    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    h = q.confirm_hold()
    ctx = json.loads(h["context_json"])
    assert ctx["mode"] == "open"
    rows = ctx["bound"]["deliveries"][0]["rows"]
    assert rows[0]["name"] == "object" and rows[0]["step"] == "01_filter"
    assert ctx["bound"]["tools"] == ["compare-groups", "plot-groups"]
    payload = present_hold(Site.load(q.root), h["hold_id"])
    run_id = ctx["bound"]["deliveries"][0]["run_id"]
    assert payload["found"].startswith(
        f"The engine bound the delivery of run {run_id} of {up.root.name} ({len(rows)} files) "
        "and the method's 2 tools; accepting opens the project for questions of those files"
    )
    assert payload["guidance"] == [
        "The delivery is the run you meant.",
        "The tables your questions need are there, by name.",
        "The read-only upstream input is the right object.",
        "Reject to initialise from another delivery.",
    ]
    titles = [s["title"] for s in payload["sections"]]
    assert titles[0] == "What opening means" and "Echo-back" not in titles
    assert titles[1].startswith(f"The delivery: run {run_id}") and titles[-1] == "Bound to"
    assert payload["sections"][1]["columns"] == ["step", "name", "type", "what"]
    md = render_markdown(payload)
    assert md.count(OPEN_SWITCH) == 1 and "operation" not in md
    view = render(q, h)
    assert view.verdicts[0]["effect"].startswith("the project opens for questions")
    for base in _serve(q):
        status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
        assert status == 200
        card = body.split('<details class="packet">')[0]
        assert card.count("Shall I open it for questions?") == 1
        assert "The delivery is the run you meant." in card and "biological replicate" not in card
    # the accept still binds to the declaration hashes
    accept_hold(q.store, h["hold_id"])
    assert q.confirm_status() == "accepted"


def test_bound_rows_mark_an_output_shipped_from_several_steps(tmp_path: Path) -> None:
    up = tmp_path / "up"
    (up / "method" / "skills").mkdir(parents=True)
    (up / "stringency.yml").write_text("pipeline: layers\n")
    (up / "method" / "skills" / "layers.analyze.yml").write_text(
        yaml.safe_dump(
            {"deliverables": {"labels": "the domain of every cell", "cells": "one row per cell"}}
        )
    )

    def item(name: str, step: str, output: str) -> dict[str, object]:
        return {
            "name": name,
            "path": f"/x/{name}",
            "type": "table",
            "blake3": "0" * 64,
            "derived_from": {"run_id": "R", "step_id": step, "output": output, "project": str(up)},
        }

    inputs = InputsManifest.model_validate(
        {
            "items": [
                item("cells", "01_extract", "cells"),
                item("03_labels", "03_select", "labels"),
                item("05_labels", "05_apply", "labels"),
            ]
        }
    )
    objective = Objective.model_validate({"id": "o", "question": "processed_object"})
    bound = bound_structure(objective, inputs, ["t1", "t2"])
    rows = bound["deliveries"][0]["rows"]
    assert [r["twice"] for r in rows] == [[], ["05_apply"], ["03_select"]]
    assert rows[0]["what"] == "one row per cell"
    table = bound_table(bound)
    assert [r["step"] for r in table] == ["01_extract", "03_select", "05_apply"]
    assert table[1]["what"] == "labels as 03_select wrote it; the same name ships from 05_apply"
    assert table[2]["what"] == "the domain of every cell (also as labels from 03_select)"
    lines = bound_lines(bound)
    assert "Step 03_select:" in lines and all(len(x) <= 100 for x in lines)
    assert "- The method's 2 tools: t1, t2." in lines
