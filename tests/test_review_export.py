"""L37: `review --export [--module]` writes the resolved holds as cases, one Markdown document
each with YAML frontmatter above the packet, into the run directory; `deliver` writes the same
documents into `deliver/<run>/reviews/` before it records the delivery, each listed in
`index.json` under its hash (the owner's ruling, 2026-11-12)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from stringency import hashing
from stringency.project import Project
from stringency.review import queue, record_review
from tests.conftest import InitFn, accept_hold
from tests.test_open_answers import questions  # noqa: F401
from tests.test_review import held_project
from tests.test_run import MOCK, cli


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def read_doc(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    assert text.startswith("---\n")
    _, head, body = text.split("---\n", 2)
    return yaml.safe_load(head), body


def test_export_writes_one_document_per_resolved_hold(make_project: InitFn) -> None:
    p, env = held_project(make_project)
    # an open hold is not a case yet
    r = cli(p, "review", "--export", "--json")
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["exported"] == []

    h = queue(p)[0]
    res = record_review(
        p, h["hold_id"], "override", correction={"label": "uniform"}, reason="the means overlap"
    )
    r = cli(p, "review", "--export", "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["schema"] == "stringency.review_export/1"
    [entry] = out["exported"]
    assert entry["hold_id"] == h["hold_id"] and entry["module"] == "label-groups@0.1.1"
    path = p.run_dir(h["run_id"]) / "reviews" / f"{h['hold_id']}.md"
    assert entry["paths"] == [str(path)]

    head, body = read_doc(path)
    assert head["hold"] == h["hold_id"] and head["kind"] == "run_disagreement"
    assert head["step"] == h["step_id"] and head["item"] == h["item_id"]
    assert head["module"] == "label-groups@0.1.1"
    assert head["review"] == res.review_id and head["reviewer"] == "tester"
    assert head["via"] == "tty" and head["verdict"] == "override"
    assert head["reason"] == "the means overlap"
    assert head["correction"] == {"label": "uniform"} and head["label"] == "uniform"
    assert head["bound"]["module_version"] == "label-groups@0.1.1"
    assert head["bound"]["params_hash"].startswith("blake3:")
    # the packet below: the replicates' calls as the reviewer saw them
    assert "replicate 1: abundant (high)" in body

    # --module: by name or by version; another module has no cases
    for name, n in (("label-groups", 1), ("label-groups@0.1.1", 1), ("compare-groups", 0)):
        r = cli(p, "review", "--export", "--module", name, "--json")
        assert len(json.loads(r.output)["exported"]) == n, name
    r = cli(p, "review", "--module", "label-groups")
    assert r.exit_code != 0 and "--export" in r.output

    # the delivery carries the same documents (the owner, 2026-11-12)
    r = cli(p, "run", "--deliver", "--json", env=env)
    assert r.exit_code == 0, r.output
    dest = Path(json.loads(r.output)["delivery"]["path"])
    assert (dest / "reviews" / f"{h['hold_id']}.md").read_text() == path.read_text()


def _delivered(make_project: InitFn) -> tuple[Project, dict[str, str], str]:
    """The toy run held on a split, the hold overridden, the run finished (not delivered)."""
    p, env = held_project(make_project)
    h = queue(p)[0]
    record_review(
        p, h["hold_id"], "override", correction={"label": "uniform"}, reason="the means overlap"
    )
    r = cli(p, "run", "--json", env=env)
    assert r.exit_code == 0, r.output
    return p, env, str(h["hold_id"])


def _recorded(p: Project) -> tuple[int, int, int]:
    """The deliveries rows, the `delivered` events and the deliver gate's verdicts."""
    s = p.store
    return (
        int(s.scalar("SELECT COUNT(*) FROM deliveries")),
        int(s.scalar("SELECT COUNT(*) FROM run_events WHERE event = 'delivered'")),
        int(s.scalar("SELECT COUNT(*) FROM predicate_results WHERE action_id LIKE 'deliver:%'")),
    )


def test_deliver_lists_the_review_documents_in_the_index_under_its_hash(
    make_project: InitFn,
) -> None:
    p, _, hold = _delivered(make_project)
    r = cli(p, "deliver", "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    dest = Path(out["path"])
    doc = dest / "reviews" / f"{hold}.md"
    head, _ = read_doc(doc)
    assert head["hold"] == hold and head["verdict"] == "override"
    index_text = (dest / "index.json").read_text()
    index = json.loads(index_text)
    [entry] = index["reviews"]
    assert entry["file"] == f"reviews/{hold}.md" and entry["hold"] == hold
    assert entry["module"] == "label-groups@0.1.1" and entry["step_id"] == head["step"]
    assert entry["blake3"] == hashing.hash_text(doc.read_text())
    assert out["reviews"] == index["reviews"]
    # the recorded index hash is the hash of the index that lists them
    row = p.store.one("SELECT * FROM deliveries WHERE delivery_id = ?", (out["delivery_id"],))
    assert row["index_hash"] == hashing.hash_text(index_text)
    ev = p.store.one("SELECT payload_json FROM run_events WHERE event = 'delivered'")
    assert json.loads(ev["payload_json"])["reviews"] == 1
    assert _recorded(p) == (1, 1, _recorded(p)[2]) and _recorded(p)[2] > 0


def test_deliver_twice_gives_the_same_review_files_and_hashes(make_project: InitFn) -> None:
    p, _, hold = _delivered(make_project)
    first = cli(p, "deliver", "--json")
    assert first.exit_code == 0, first.output
    dest = Path(json.loads(first.output)["path"])
    doc = dest / "reviews" / f"{hold}.md"
    text1, index1 = doc.read_text(), json.loads((dest / "index.json").read_text())
    second = cli(p, "deliver", "--json")
    assert second.exit_code == 0, second.output
    index2 = json.loads((dest / "index.json").read_text())
    assert doc.read_text() == text1
    assert sorted(x.name for x in (dest / "reviews").iterdir()) == [f"{hold}.md"]
    assert index2["reviews"] == index1["reviews"]
    # the index differs only in when it was delivered
    assert {k: v for k, v in index2.items() if k != "delivered"} == {
        k: v for k, v in index1.items() if k != "delivered"
    }


def test_an_export_error_stops_deliver_before_anything_is_recorded(
    make_project: InitFn, monkeypatch: pytest.MonkeyPatch
) -> None:
    p, _, _ = _delivered(make_project)
    before = _recorded(p)

    def broken(*_a: object, **_k: object) -> str:
        raise OSError("the packet could not be read")

    monkeypatch.setattr("stringency.review_export.document", broken)
    r = cli(p, "deliver", "--json")
    assert r.exit_code == 1, r.output
    assert "review documents could not be exported" in r.output
    assert "no delivery was recorded" in r.output
    assert _recorded(p) == before
    assert p.store.scalar("SELECT COUNT(*) FROM artifacts WHERE is_final = 1") == 0
    run_id = p.store.scalar("SELECT run_id FROM runs WHERE kind = 'run'")
    assert not (p.root / "deliver" / str(run_id) / "index.json").exists()


def test_a_review_file_that_cannot_be_written_stops_deliver_before_it_is_recorded(
    make_project: InitFn,
) -> None:
    p, _, _ = _delivered(make_project)
    before = _recorded(p)
    run_id = str(p.store.scalar("SELECT run_id FROM runs WHERE kind = 'run'"))
    dest = p.root / "deliver" / run_id
    dest.mkdir(parents=True)
    (dest / "reviews").write_text("a file where the directory goes")
    r = cli(p, "deliver", "--json")
    assert r.exit_code == 1, r.output
    assert "no delivery was recorded" in r.output
    assert _recorded(p)[:2] == before[:2]
    assert p.store.scalar("SELECT COUNT(*) FROM artifacts WHERE is_final = 1") == 0
    assert not (dest / "index.json").exists()


def test_a_run_without_resolved_holds_delivers_an_empty_list(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--deliver", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    dest = Path(json.loads(r.output)["delivery"]["path"])
    assert json.loads((dest / "index.json").read_text())["reviews"] == []
    assert not (dest / "reviews").exists()


@pytest.mark.parametrize(
    "extra",
    [
        ["--hold", "H"],
        ["--verdict", "accept"],
        ["--reason", "x"],
        ["--choose", "uniform"],
        ["--replicate", "1"],
        ["--attest"],
        ["--show"],
        ["--holds", "H1,H2"],
    ],
)
def test_export_refuses_what_it_would_ignore(make_project: InitFn, extra: list[str]) -> None:
    p, _ = held_project(make_project)
    r = cli(p, "review", "--export", *extra)
    assert r.exit_code == 15 and extra[0] in r.output, r.output
    assert p.store.scalar("SELECT COUNT(*) FROM reviews") == 1  # the confirm's only


def test_export_refuses_an_unknown_run(make_project: InitFn) -> None:
    p, _ = held_project(make_project)
    r = cli(p, "review", "--export", "--run", "NO-SUCH-RUN")
    assert r.exit_code == 15 and "no run NO-SUCH-RUN" in r.output, r.output


def test_an_open_delivery_carries_the_review_documents_and_regenerates_unchanged(
    questions: Project,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = questions
    monkeypatch.setattr("stringency.review.current_user", lambda: q.config.roles.owner)
    asked = json.loads(cli(q, "ask", "Is group A above B?", "--json").output)
    r = cli(
        q,
        "call",
        "compare-groups",
        "--question",
        asked["question_id"],
        "--set",
        "correction=bonferroni",
        "--reason",
        "the stricter one",
        "--json",
    )
    assert r.exit_code == 10, r.output
    [h] = queue(q)
    record_review(q, h["hold_id"], "accept", reason="fine")
    assert cli(q, "propose", h["step_id"], "--json").exit_code == 0
    first = cli(q, "deliver", "--json")
    assert first.exit_code == 0, first.output
    out = json.loads(first.output)
    dest = Path(out["path"])
    [entry] = out["reviews"]
    doc = dest / entry["file"]
    assert entry["hold"] == h["hold_id"] and doc.is_file()
    assert entry["blake3"] == hashing.hash_text(doc.read_text())
    index_text = (dest / "index.json").read_text()
    assert json.loads(index_text)["reviews"] == out["reviews"]
    latest = q.store.one("SELECT index_hash FROM deliveries ORDER BY rowid DESC LIMIT 1")
    assert latest["index_hash"] == hashing.hash_text(index_text)
    rows = q.store.scalar("SELECT COUNT(*) FROM deliveries")
    second = cli(q, "deliver", "--json")
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["changed"] is False
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries") == rows
    assert (dest / "index.json").read_text() == index_text
