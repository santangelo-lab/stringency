"""A judgment whose label is a route a person signs off (backlog L10): `judgment.sign_off` in the
manifest holds every item, agreed or not; `labels` narrows what a person may choose; a chosen
label is recorded as accept (a replicate called it) or override; `wait` returns the label."""

from __future__ import annotations

import json
import threading

import pytest

from stringency import git
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.review import choose, item_choices, record_review
from stringency.review_serve import make_server
from tests.conftest import InitFn
from tests.test_review_serve import TOKEN, get
from tests.test_run import MOCK, cli, confirmed

LABELS = ["abundant", "sparse", "uniform"]


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def signed_project(make_project: InitFn, labels: list[str] | None = None) -> Project:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    mod = p.method_root / "modules" / "label-groups" / "module.yml"
    extra = (
        "  sign_off: {when: always" + (f", labels: [{', '.join(labels)}]" if labels else "") + "}\n"
    )
    text = mod.read_text().replace("  considered_set: false\n", "  considered_set: false\n" + extra)
    mod.write_text(text)
    git.commit_all(p.method_root, "sign off the labels")
    return Project.load(p.root)


def item_holds(p: Project) -> dict[str, dict[str, str]]:
    rows = p.store.all("SELECT * FROM holds WHERE item_id IS NOT NULL ORDER BY item_id")
    return {str(r["item_id"]): dict(r) for r in rows}


def test_agreed_items_hold_for_sign_off(make_project: InitFn) -> None:
    p = signed_project(make_project)
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 10, r.output
    holds = item_holds(p)
    assert holds and {h["kind"] for h in holds.values()} == {"sign_off"}
    assert {h["waits_on_role"] for h in holds.values()} == {"owner"}
    a = holds["A"]
    assert a["reason"] == "the reviewers agreed on abundant; a person signs off the label"
    row = p.store.one("SELECT * FROM consensus WHERE item_id = 'A'")
    assert row is not None and row["source"] == "unresolved" and row["label"] is None
    # accept needs a reason, then the agreed label stands as accepted
    with pytest.raises(ConfigError, match="needs --reason"):
        record_review(p, a["hold_id"], "accept")
    record_review(p, a["hold_id"], "accept", reason="agreed")
    row = p.store.one("SELECT * FROM consensus WHERE item_id = 'A'")
    assert row["label"] == "abundant" and row["source"] == "accepted"


def test_labels_narrow_the_choice_and_choose_maps_to_the_verdict(make_project: InitFn) -> None:
    p = signed_project(make_project, LABELS)
    assert cli(p, "run", env=MOCK).exit_code == 10
    holds = item_holds(p)
    c = holds["C"]  # the reviewers agreed on `variable`, which a person may not sign off
    assert "not a label a person may sign off" in c["reason"]
    assert item_choices(p, c) == LABELS
    with pytest.raises(ConfigError, match="not one this module lets a person choose"):
        record_review(p, c["hold_id"], "accept", reason="fine")
    with pytest.raises(ConfigError, match="not one this module lets a person choose"):
        record_review(p, c["hold_id"], "override", reason="x", correction={"label": "variable"})
    assert choose(p, holds["A"], "abundant")[0] == "accept"
    assert choose(p, c, "uniform") == ("override", None, {"label": "uniform"})
    r = cli(p, "review", "--hold", c["hold_id"], "--choose", "uniform", "--reason", "mine")
    assert r.exit_code == 0, r.output
    row = p.store.one("SELECT * FROM consensus WHERE item_id = 'C'")
    assert row["label"] == "uniform" and row["source"] == "override"
    out = json.loads(cli(p, "wait", "--hold", c["hold_id"], "--json").output)
    assert out["review"]["label"] == "uniform" and out["review"]["reason"] == "mine"
    r = cli(p, "review", "--hold", c["hold_id"], "--choose", "x", "--verdict", "accept")
    assert r.exit_code != 0


def test_settled_items_complete_the_step(make_project: InitFn) -> None:
    p = signed_project(make_project, LABELS)
    assert cli(p, "run", env=MOCK).exit_code == 10
    for item, h in item_holds(p).items():
        label = "uniform" if item == "C" else None
        verdict, rep, corr = choose(
            p, h, label or str(json.loads(h["context_json"])["replicate_labels"][0])
        )
        record_review(p, h["hold_id"], verdict, reason="route", replicate=rep, correction=corr)
    assert p.store.scalar("SELECT status FROM steps WHERE step_id = '03_label'") == "completed"
    doc = json.loads(next((p.root / "runs").rglob("03_label/consensus.json")).read_text())
    by = {i["item_id"]: i for i in doc["items"]}
    assert by["C"]["label"] == "uniform" and by["A"]["source"] == "accepted"


def test_console_offers_the_labels_and_records_the_choice(make_project: InitFn) -> None:
    p = signed_project(make_project, LABELS)
    assert cli(p, "run", env=MOCK).exit_code == 10
    c = item_holds(p)["C"]
    srv = make_server([p.root], port=0, token=TOKEN)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        status, body = get(f"{base}/hold/{c['hold_id']}?t={TOKEN}")
        assert status == 200
        for label in LABELS:
            assert f'name="choice" value="{label}"' in body
        assert 'value="variable"' not in body and 'name="label"' not in body
        assert "Sign off the route the reviewers chose" in body
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode({"choice": "sparse", "reason": "the owner's route"}).encode()
        req = urllib.request.Request(f"{base}/hold/{c['hold_id']}?t={TOKEN}", data=data)
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.status == 200
    finally:
        srv.shutdown()
    row = p.store.one("SELECT * FROM consensus WHERE item_id = 'C'")
    assert row["label"] == "sparse" and row["source"] == "override"


def test_lint_checks_sign_off_labels(make_project: InitFn) -> None:
    p = signed_project(make_project, ["abundant", "nonsense"])
    r = cli(p, "lint", str(p.method_root))
    assert r.exit_code != 0 and "sign_off label nonsense is not in vocabulary" in r.output
