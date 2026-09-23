"""Batch review (Lane A 5c): sibling projects' confirm holds, one echo-back, one verdict."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency import hashing
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.review_batch import batch_view, locate_holds, record_batch
from tests.conftest import InitFn, write_declarations
from tests.test_run import cli


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def siblings(tmp_path: Path, toy_data: Path, make_project: InitFn) -> tuple[Project, Project]:
    """Two projects that differ only in the data file they bind (the Lyons CLP QC pattern)."""
    other = tmp_path / "data2" / "groups.csv"
    other.parent.mkdir()
    lines = toy_data.read_text().splitlines()
    other.write_text("\n".join(lines[:-1]) + "\n")  # one row fewer: a different hash
    f1 = write_declarations(tmp_path / "s1", toy_data)
    f2 = write_declarations(
        tmp_path / "s2",
        toy_data,
        inputs={
            "inputs": 1,
            "items": [
                {
                    "name": "groups",
                    "path": str(other),
                    "type": "frame",
                    "blake3": hashing.hash_file(other),
                    "source": "toy fixture, second region",
                }
            ],
        },
    )
    kw = dict(pipeline="toy-engine", execution="engine")
    a = make_project(
        objective=f1["objective.yml"], design=f1["design.yml"], inputs=f1["inputs.yml"], **kw
    )
    b = make_project(
        objective=f2["objective.yml"], design=f2["design.yml"], inputs=f2["inputs.yml"], **kw
    )
    return a, b


def test_batch_view_shows_shared_once_and_differences_per_project(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    a, b = siblings(tmp_path, toy_data, make_project)
    ids = [a.confirm_hold()["hold_id"], b.confirm_hold()["hold_id"]]
    members = locate_holds(ids, [], a.root.parent)
    assert [m.project.root for m in members] == [a.root, b.root]
    view = batch_view(members)
    assert "design.yml, objective.yml" in view.text  # identical files named once
    assert set(view.differing) >= {"inputs.items[groups].path", "inputs.items[groups].blake3"}
    assert "inputs.items[groups].source" in view.differing
    assert a.root.name in view.text and b.root.name in view.text
    assert "Factor group" in view.text  # the shared echo, shown once
    assert view.text.count("Factor group") == 1
    assert [v["verdict"] for v in view.verdicts] == ["accept", "reject"]


def test_batch_accept_records_one_review_per_hold(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    a, b = siblings(tmp_path, toy_data, make_project)
    ids = [a.confirm_hold()["hold_id"], b.confirm_hold()["hold_id"]]
    members = locate_holds(ids, [a.root, b.root], None)
    with pytest.raises(ConfigError, match="needs --reason"):
        record_batch(members, "accept", reason=None, attest=False)
    results = record_batch(members, "accept", reason="same layout on both slides", attest=False)
    assert len(results) == 2 and all(r.via == "tty" for r in results)
    for p, r in zip((a, b), results, strict=True):
        assert p.confirm_status() == "accepted"
        row = p.store.one("SELECT * FROM reviews WHERE review_id=?", (r.review_id,))
        assert row["reason_code"] == "batch" and row["reason"] == "same layout on both slides"
        assert row["reviewer"] == "tester"


def test_batch_refuses_non_confirm_missing_and_resolved(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    a, b = siblings(tmp_path, toy_data, make_project)
    ha, hb = a.confirm_hold()["hold_id"], b.confirm_hold()["hold_id"]
    with pytest.raises(ConfigError, match="not found"):
        locate_holds([ha, "01NOPE"], [a.root, b.root], None)
    record_batch(locate_holds([ha], [a.root], None), "accept", reason="ok", attest=False)
    with pytest.raises(ConfigError, match="already resolved"):
        locate_holds([ha, hb], [a.root, b.root], None)
    # a step-level hold is not batched: run b to its item hold and try
    from tests.conftest import accept_hold
    from tests.test_run import HARNESS, MOCK

    accept_hold(b.store, hb)
    env = {**MOCK, "STRINGENCY_MOCK_FIXTURE": str(HARNESS / "split.yml")}
    r = cli(b, "run", env=env)
    assert r.exit_code == 10, r.output
    item = b.store.one("SELECT hold_id FROM holds WHERE kind='run_disagreement'")["hold_id"]
    with pytest.raises(ConfigError, match="confirm holds only"):
        locate_holds([item], [b.root], None)


def test_batch_through_the_cli(tmp_path: Path, toy_data: Path, make_project: InitFn) -> None:
    a, b = siblings(tmp_path, toy_data, make_project)
    ids = ",".join([a.confirm_hold()["hold_id"], b.confirm_hold()["hold_id"]])
    r = cli(a, "review", "--holds", ids, "--projects", str(a.root.parent), "--json")
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["schema"] == "stringency.review_batch/1" and len(out["holds"]) == 2
    r = cli(
        a,
        "review",
        "--holds",
        ids,
        "--projects",
        str(a.root.parent),
        "--verdict",
        "accept",
        "--reason",
        "both regions follow the plan",
    )
    assert r.exit_code == 0, r.output
    assert a.confirm_status() == "accepted" and b.confirm_status() == "accepted"
