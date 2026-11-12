"""L37: `review --export [--module]` writes the resolved holds as cases, one Markdown document
each with YAML frontmatter above the packet, into the run directory and the delivery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from stringency.review import queue, record_review
from tests.conftest import InitFn
from tests.test_review import held_project
from tests.test_run import cli


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

    # the delivery does not carry them (the owner's ruling: reviewer names and packets in a
    # shareable directory), and an export after delivery writes nothing there
    r = cli(p, "run", "--deliver", "--json", env=env)
    assert r.exit_code == 0, r.output
    dest = Path(json.loads(r.output)["delivery"]["path"])
    assert not (dest / "reviews").exists()
    r = cli(p, "review", "--export", "--json")
    assert json.loads(r.output)["exported"][0]["paths"] == [str(path)]
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
