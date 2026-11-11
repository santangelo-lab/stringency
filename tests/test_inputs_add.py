"""L160 (Lyons Lung, 2026-11-09; closes L48): a person's file as a tool input in an open
project. `inputs add` copies and hashes it and records the person's words; `$inputs.<name>`
binds it by name only; an answer from it is trusted and its qualifier names the file."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from stringency.project import Project
from tests.conftest import InitFn
from tests.test_open_answers import questions  # noqa: F401
from tests.test_run import cli

WORDS = "Jim's re-measured groups A and B, from the 2026-11-09 bench run"


def _their_file(tmp_path: Path, toy_data: Path) -> Path:
    """A frame the person brings: the toy groups, every value of group B lowered by ten."""
    with toy_data.open(newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["group"] == "B":
            r["value"] = f"{float(r['value']) - 10:.1f}"
    out = tmp_path / "theirs" / "remeasured.csv"
    out.parent.mkdir()
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return out


def _cell(path: str, contrast: str, column: str) -> str:
    with open(path, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["contrast"] == contrast:
                return str(r[column])
    raise AssertionError(f"no {contrast} in {path}")


def test_a_persons_file_is_added_bound_by_name_and_named_in_the_qualifier(
    questions: Project,  # noqa: F811
    tmp_path: Path,
    toy_data: Path,
) -> None:
    q = questions
    theirs = _their_file(tmp_path, toy_data)
    r = cli(q, "inputs", "add", "mine", str(theirs), "--type", "frame", "--source", WORDS, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    added = json.loads(r.output)
    copy = q.root / added["path"]
    assert added["ref"] == "$inputs.mine" and added["from"] == str(theirs.resolve())
    assert copy.read_bytes() == theirs.read_bytes() and added["source"] == WORDS
    ev = q.store.one("SELECT payload_json FROM run_events WHERE event = 'input_added'")
    assert json.loads(ev["payload_json"])["blake3"] == added["blake3"]
    # inputs.yml is never edited
    assert "mine" not in (q.root / "inputs.yml").read_text()
    # tools list offers it, bound by name only
    tl = json.loads(cli(q, "tools", "list", "--json").output)
    cands = [c for t in tl["tools"] for spec in t["inputs"].values() for c in spec["candidates"]]
    mine = [c for c in cands if c.get("ref") == "$inputs.mine"]
    assert mine and mine[0]["binds_by_name"] and mine[0]["added_by_person"] == WORDS

    asked = json.loads(cli(q, "ask", "Which group is higher in my file?", "--json").output)
    # unnamed, a tool binds the delivery as before: a person's file never binds by type alone
    r = cli(q, "call", "compare-groups", "--question", asked["question_id"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    first = json.loads(r.output)
    bound = q.store.scalar("SELECT inputs_json FROM actions WHERE step_id = ?", (first["step_id"],))
    assert added["blake3"] not in bound
    # named, it binds the person's file
    r = cli(
        q,
        "call",
        "compare-groups",
        "--question",
        asked["question_id"],
        "--in",
        "object=$inputs.mine",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    bound = q.store.scalar("SELECT inputs_json FROM actions WHERE step_id = ?", (out["step_id"],))
    assert added["blake3"] in bound
    art = out["artifacts"][0]
    diff = _cell(art["path"], "A_vs_B", "diff")
    assert diff != _cell(first["artifacts"][0]["path"], "A_vs_B", "diff")
    text = tmp_path / "a.md"
    text.write_text(f"In the re-measured file A is higher than B by {diff}.")
    r = cli(
        q,
        "answer",
        "--question",
        asked["question_id"],
        "--text",
        str(text),
        "--cite",
        f"{art['artifact_id']}:A_vs_B",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    ans = json.loads(r.output)
    # data with a source, not code: the label stays trusted, the qualifier says whose file
    assert ans["label"] == "trusted"
    assert f'person-supplied inputs: mine ("{WORDS}")' in ans["qualifier"]
    # the copy is hashed again like any input: changed, the next call is blocked
    copy.write_text(copy.read_text() + "r99,A,u1,1.0\n")
    r = cli(q, "call", "compare-groups", "--in", "object=$inputs.mine", "--json")
    assert r.exit_code == 11, r.output + str(r.stderr)
    blocked = json.loads(r.output)
    fired = {
        row["predicate_id"]
        for row in q.store.all(
            "SELECT p.predicate_id FROM predicate_results p JOIN actions a ON "
            "a.action_id = p.action_id WHERE a.step_id = ? AND p.fired = 1",
            (blocked["step_id"],),
        )
    }
    assert "repro.input_digest_mismatch" in fired


def test_what_inputs_add_refuses(
    questions: Project,  # noqa: F811
    tmp_path: Path,
    toy_data: Path,
    make_project: InitFn,
) -> None:
    q = questions
    theirs = _their_file(tmp_path, toy_data)
    ok = ["--type", "frame", "--source", WORDS]
    assert cli(q, "inputs", "add", "mine", str(theirs), *ok).exit_code == 0
    # a name already taken, a type no tool takes, no words, a missing file, a bad name
    assert cli(q, "inputs", "add", "mine", str(theirs), *ok).exit_code == 15
    r = cli(q, "inputs", "add", "other", str(theirs), "--type", "nope", "--source", WORDS)
    assert r.exit_code == 15 and "types: frame" in str(r.stderr) + r.output
    r = cli(q, "inputs", "add", "other", str(theirs), "--type", "frame", "--source", " ")
    assert r.exit_code == 15
    r = cli(q, "inputs", "add", "other", str(tmp_path / "none.csv"), *ok)
    assert r.exit_code == 15
    assert cli(q, "inputs", "add", "9bad", str(theirs), *ok).exit_code == 15
    assert not (q.root / "inputs" / "added" / "other").exists()
    assert q.store.scalar("SELECT COUNT(*) FROM run_events WHERE event='input_added'") == 1
    # a declared pipeline's inputs change only with a new project
    p = make_project()
    assert cli(p, "inputs", "add", "mine", str(theirs), *ok).exit_code == 16


def test_a_directory_is_copied_and_hashed_whole(
    questions: Project,  # noqa: F811
    tmp_path: Path,
) -> None:
    q = questions
    d = tmp_path / "bundle"
    d.mkdir()
    (d / "a.csv").write_text("row_id,group,unit,value\nr1,A,u1,1.0\n")
    (d / "b.txt").write_text("notes\n")
    r = cli(q, "inputs", "add", "bundle", str(d), "--type", "frame", "--source", WORDS, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert sorted(p.name for p in (q.root / out["path"]).iterdir()) == ["a.csv", "b.txt"]
