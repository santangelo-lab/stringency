"""L95 (the owner, 2026-10-22): the engine's own proposal checks opened holds with no view of
their own. A `param.reason_unmatched` page showed the numerals that matched nothing and not
the cited cells they were compared with; a `param.uncited` page did not show what the method
names against what was cited. Both now carry a default view, ahead of anything the method's
skill adds."""

from __future__ import annotations

import json

from stringency.present import Site, present_hold, proposal_check_sections
from stringency.review import queue
from tests.conftest import InitFn, accept_hold
from tests.test_run import MOCK, cli


def test_a_reason_unmatched_hold_shows_the_cited_cells_beside_the_unmatched_numbers(
    make_project: InitFn,
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--until", "02_summarize", "--json", env=MOCK)
    assert r.exit_code == 0, r.output + str(r.stderr)
    r = cli(
        p,
        "propose",
        "04_compare",
        "--set",
        "correction=bonferroni",
        "--cite",
        "02_summarize/table:A:mean_value",
        "--reason",
        "A's mean is 74.82 and B's is 12.5, so the stricter correction",
        "--json",
        env=MOCK,
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    by = {h["reason"].split(":")[0]: h for h in queue(p)}
    assert sorted(by) == ["param.agent_proposed", "param.reason_unmatched"]
    site = Site.load(p.root)
    try:
        hp = present_hold(site, by["param.reason_unmatched"]["hold_id"])
        sections = {s["title"]: s for s in hp["sections"]}
        assert list(sections)[:3] == [
            "The operator's reason",
            "What the reason cited, with the value the engine read",
            "Numbers in the reason that match no cited cell",
        ]
        assert "B's is 12.5" in sections["The operator's reason"]["text"]
        cited = sections["What the reason cited, with the value the engine read"]
        assert cited["columns"] == ["source", "row", "column", "value"]
        assert cited["rows"] == [["02_summarize/table", "A", "mean_value", "74.82"]]
        unmatched = sections["Numbers in the reason that match no cited cell"]
        assert [row[0] for row in unmatched["rows"]] == ["12.5"]
        # the choice's own hold keeps its decision view and gains none of these
        own = present_hold(site, by["param.agent_proposed"]["hold_id"])
        assert "The operator's reason" not in [s["title"] for s in own["sections"]]
        # a param.uncited hold: what the method names beside what was cited
        h = by["param.reason_unmatched"]
        ctx = {"evidence": {"uncited": ["correction (02_summarize/table)"]}}
        got = {s["title"]: s for s in proposal_check_sections(site, h, ctx, "param.uncited")}
        named = got["The evidence the method names, which the proposal did not cite"]
        assert named["rows"] == [["correction", "02_summarize/table"]]
        assert got["What the proposal cited"]["rows"] == cited["rows"]
    finally:
        site.store.close()
    shown = cli(p, "present", "--hold", by["param.reason_unmatched"]["hold_id"]).output
    assert "What the reason cited, with the value the engine read" in shown
    assert json.loads(
        cli(p, "present", "--hold", by["param.reason_unmatched"]["hold_id"], "--json").output
    )["sections"]
