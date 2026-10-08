"""Every reviewer's call and rationale at a hold on a judgment step (backlog L16): the batch-route
hold is a plugin's flag on a judgment step, and its packet and console page showed no reviewer."""

from __future__ import annotations

import html

from stringency.holds import HoldRequest, open_hold
from stringency.project import Project
from stringency.review_render import render
from tests.conftest import InitFn
from tests.test_review_serve import TOKEN, get, held, server  # noqa: F401 - fixtures
from tests.test_run import MOCK, cli, confirmed


def _flag_on_the_judgment_step(p: Project) -> str:
    """A completed toy run, then a flag on 03_label as a plugin would raise after the judgment."""
    r = cli(p, "run", "--until", "03_label", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = p.store.scalar("SELECT run_id FROM runs ORDER BY started DESC LIMIT 1")
    a = p.store.one(
        "SELECT * FROM actions WHERE run_id = ? AND step_id = '03_label' ORDER BY attempt DESC",
        (run_id,),
    )
    assert a is not None
    out = open_hold(
        p.store,
        HoldRequest(
            run_id=run_id,
            step_id="03_label",
            kind="flag",
            reason="the reviewers agreed; does the owner agree with them",
            waits_on_role="owner",
            bound_module_version=a["module"],
            bound_input_digest="x",
            bound_params_hash="x",
            context={"predicate": "toy.route_review", "phase": "post", "evidence": {}},
        ),
    )
    return out.hold_id


def test_flag_on_a_judgment_step_shows_every_reviewer(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    hid = _flag_on_the_judgment_step(p)
    h = p.store.one("SELECT * FROM holds WHERE hold_id = ?", (hid,))
    view = render(p, h)
    n = p.store.scalar(
        "SELECT COUNT(*) FROM judgments WHERE run_id = ? AND step_id = '03_label'", (h["run_id"],)
    )
    assert n and len(view.replicates) == n
    assert "the reviewers' calls:" in view.text
    for rv in view.replicates:
        assert rv.item is not None and rv.rationale and f'rationale: "{rv.rationale}"' in view.text
    assert all(r["rationale"] for r in view.to_json()["replicates"])


def test_console_hold_page_has_the_reviewers_section(server: tuple[str, Project]) -> None:  # noqa: F811
    base, p = server
    h = p.store.one("SELECT * FROM holds WHERE item_id IS NOT NULL AND resolved_by_review IS NULL")
    assert h is not None
    status, body = get(f"{base}/hold/{h['hold_id']}?t={TOKEN}")
    assert status == 200 and "<h2>The reviewers</h2>" in body
    view = render(p, h)
    assert view.replicates
    for rv in view.replicates:
        assert f"Replicate {rv.replicate}: " in body
        assert html.escape(rv.rationale, quote=True) in body or html.escape(rv.rationale) in body
