"""Open mode S5, answers and labels (spec/archive/open_mode_plan.md 2.5): `answer` files the
reply against cited cells; a wrong numeral is blocked (exit 12) and kept; a correct one is
admissible and `trusted` when its tool's control is current and the environment verified;
an answer citing an exec table is `untested`; a missing id and an authored label block; the
qualifier line names an accepted flag on the path and a person-set parameter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency import provenance
from stringency.answers import parse_cite
from stringency.echo import OPEN_SWITCH
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import MOCK, cli


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    return q


def _ask_and_compare(
    q: Project, text: str = "Which group is higher, A or B?"
) -> tuple[str, str, str]:
    asked = json.loads(cli(q, "ask", text, "--json").output)
    r = cli(q, "call", "compare-groups", "--question", asked["question_id"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    return asked["question_id"], out["artifacts"][0]["artifact_id"], out["run_id"]


def _answer(q: Project, qid: str, text: str, *cites: str, path: Path):  # type: ignore[no-untyped-def]
    path.write_text(text)
    args = ["answer", "--question", qid, "--text", str(path), "--json"]
    for c in cites:
        args += ["--cite", c]
    return cli(q, *args)


def test_answer_blocked_on_a_wrong_numeral_then_trusted_when_the_tool_is_controlled(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    qid, aid, run_id = _ask_and_compare(q)
    text = tmp_path / "a.md"
    # a numeral that is no cited cell: blocked, exit 12, the answer kept
    r = _answer(
        q, qid, "A is higher than B: the difference is 59.3 with n_a 3.", f"{aid}:A_vs_B", path=text
    )
    assert r.exit_code == 12, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "blocked" and any("ans.numeral_unmatched" in b for b in out["blocked"])
    assert out["cells"][aid]["A_vs_B"]["diff"] == 59.22 and out["numerals"] == {
        "matched": 1,
        "total": 2,
    }
    row = q.store.one("SELECT * FROM answers WHERE answer_id=?", (out["answer_id"],))
    assert row["status"] == "blocked" and row["label"] is None
    preds = {
        p["predicate_id"]: p["fired"]
        for p in q.store.all(
            "SELECT predicate_id, fired FROM predicate_results WHERE action_id=?",
            (out["answer_id"],),
        )
    }
    assert preds == {"ans.cited_missing": 0, "ans.numeral_unmatched": 1, "ans.label_authored": 0}
    # the right numerals: admissible and trusted, the tool's controls having run before its
    # first use (2026-10-19)
    r = _answer(
        q,
        qid,
        "A is higher than B: the difference is 59.22 (adjusted p 1.33e-75).",
        f"{aid}:A_vs_B",
        path=text,
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["label"] == "trusted" and out["numerals"] == {"matched": 2, "total": 2}
    assert out["label_sentence"] == (
        "Label: trusted. Produced by compare-groups (compare-groups@0.1.1), a tool shipped with "
        "the method, run by the engine on the delivered data. Numbers checked against the cited "
        "cells: 2 of 2. Everything else in this answer is the assistant's reading."
    )
    assert out["qualifier"] == (
        "flags accepted on the path: none | parameters outside range: none | person-set "
        "parameters: none | upstream: verified | controls: current | untested inputs: none"
    )
    assert [f["kind"] for f in out["provenance"]["lineage"]] == ["tool", "input"]
    assert out["provenance"]["lineage"][1]["derived_from"]["step_id"] == "01_filter"
    row = q.store.one("SELECT * FROM answers WHERE answer_id=?", (out["answer_id"],))
    assert row["label"] == "trusted" and q.store.message(row["text_ref"]).startswith("A is higher")
    ev = q.store.one(
        "SELECT payload_json FROM run_events WHERE run_id=? AND event='answer_recorded' ORDER BY seq DESC LIMIT 1",
        (run_id,),
    )
    assert json.loads(ev["payload_json"])["label"] == "trusted"
    # the human output carries the two pinned lines
    human = _answer(q, qid, "The difference is 59.22.", f"{aid}:A_vs_B:diff", path=text).output
    assert "Label: trusted." in human and "flags accepted on the path: none" in human
    # the second call finds the controls current and runs none
    r = cli(q, "call", "compare-groups", "--question", qid, "--json")
    assert r.exit_code == 0 and json.loads(r.output)["controls_run"] == []
    assert q.store.scalar("SELECT COUNT(*) FROM controls_runs WHERE module='compare-groups'") == 2
    # so the controls_stale verdict fired on neither call
    logged = q.store.all(
        "SELECT a.step_id, pr.fired FROM predicate_results pr JOIN actions a ON a.action_id=pr.action_id "
        "WHERE pr.run_id=? AND pr.predicate_id='prov.controls_stale' ORDER BY a.rowid",
        (run_id,),
    )
    assert [(r_["step_id"], r_["fired"]) for r_ in logged] == [
        ("01_compare-groups", 0),
        ("02_compare-groups", 0),
    ]


def test_label_sentence_names_why_a_tool_answer_is_untested() -> None:
    """A tool that missed a condition of trusted is never described as code (2026-10-19)."""
    tool = provenance.StepFact(
        step_id="01_plot-groups",
        kind="tool",
        module="plot-groups@0.1.0",
        title="Draw the differences",
        status="completed",
        runner="engine",
        env_status="verified",
        controls="none",
    )
    delivered = provenance.StepFact(
        step_id="input:comparison_table", kind="input", derived_from={"run_id": "R"}
    )
    facts = [tool, delivered]
    assert provenance.label_for(facts) == "untested"
    assert provenance.label_sentence("untested", facts, 0, 0) == (
        "Label: untested. Produced by Draw the differences (plot-groups@0.1.0), a tool shipped "
        "with the method, run by the engine on the delivered data; no passing control is on "
        "record for it. Numbers checked against the cited cells: 0 of 0. Everything else in "
        "this answer is the assistant's reading."
    )
    tool.controls = "failed"
    assert "; its control failed." in provenance.label_sentence("untested", facts, 0, 0)
    tool.controls, tool.env_status = "current", "unpinned"
    assert "; its environment was not verified." in provenance.label_sentence(
        "untested", facts, 0, 0
    )
    # code anywhere on the path outranks the tool's reason
    facts.insert(1, provenance.StepFact(step_id="02_exec", kind="exec", status="completed"))
    assert provenance.label_sentence("untested", facts, 0, 0).startswith(
        "Label: untested. Produced by code written in this session"
    )
    # an upstream pipeline input on the path changes what the sentence says it ran on
    raw = provenance.StepFact(
        step_id="input:upstream_groups", kind="input", upstream_input={"input": "groups"}
    )
    assert "on the pipeline's inputs" in provenance.label_sentence(
        "untested", [facts[1], raw], 0, 0
    )
    assert "on the delivered data and the pipeline's inputs" in provenance.label_sentence(
        "untested", [facts[1], delivered, raw], 0, 0
    )


def test_answer_on_exec_output_is_untested_and_missing_or_authored_block(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    qid = json.loads(cli(q, "ask", "what is the mean per group?", "--json").output)["question_id"]
    script = tmp_path / "s.py"
    script.write_text(
        "import csv, json, sys\njob = json.load(sys.stdin)\n"
        "rows = list(csv.DictReader(open(job['inputs']['object'])))\nby = {}\n"
        "for r in rows: by.setdefault(r['group'], []).append(float(r['value']))\n"
        "f = open(job['outputs']['means'], 'w'); f.write('group\\tmean\\n')\n"
        "[f.write(f'{g}\\t{sum(v)/len(v):.2f}\\n') for g, v in sorted(by.items())]\n"
    )
    r = cli(
        q, "exec", str(script), "--out", "means=table", "--allow-local", "--question", qid, "--json"
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    aid = json.loads(r.output)["artifacts"][0]["artifact_id"]
    cells = json.loads(
        cli(
            q, "answer", "--question", qid, "--text", "-", "--cite", aid, "--json", input="nothing"
        ).output
    )["cells"]
    mean_a = cells[aid]["A"]["mean"]
    text = tmp_path / "a.md"
    r = _answer(q, qid, f"Group A has mean {mean_a}.", f"{aid}:A", path=text)
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["label"] == "untested" and out["label_sentence"].startswith(
        "Label: untested. Produced by code written in this session"
    )
    assert out["qualifier"].endswith("controls: none | untested inputs: 01_exec")
    # a tool fed by the exec output is untested too, and the qualifier names the untested input
    # (a frame output from a script, then the tool on it)
    frame_script = tmp_path / "f.py"
    frame_script.write_text(
        "import csv, json, sys\njob = json.load(sys.stdin)\n"
        "rows = [r for r in csv.DictReader(open(job['inputs']['object'])) if r['group'] != 'C']\n"
        "w = csv.DictWriter(open(job['outputs']['object'], 'w', newline=''), fieldnames=list(rows[0]))\n"
        "w.writeheader(); w.writerows(rows)\n"
    )
    r = cli(q, "exec", str(frame_script), "--out", "object=frame/csv", "--allow-local", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    exec_step = json.loads(r.output)["step_id"]
    r = cli(q, "call", "compare-groups", "--in", f"object=$steps.{exec_step}.object", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    aid3 = json.loads(r.output)["artifacts"][0]["artifact_id"]
    r = _answer(q, qid, "A and B differ.", aid3, path=text)
    out = json.loads(r.output)
    assert out["label"] == "untested" and f"untested inputs: {exec_step}" in out["qualifier"]
    assert [f["kind"] for f in out["provenance"]["lineage"]] == ["tool", "exec", "input"]
    # a missing id, a missing row, a missing column: blocked by ans.cited_missing
    for cite in ("01BADBADBADBADBADBADBADBAD", f"{aid}:Z", f"{aid}:A:nope"):
        r = _answer(q, qid, "No numbers here.", cite, path=text)
        assert r.exit_code == 12, (cite, r.output)
        assert any("ans.cited_missing" in b for b in json.loads(r.output)["blocked"])
    # the operator writes the label: blocked by ans.label_authored
    r = _answer(q, qid, "This answer is trusted.", f"{aid}:A", path=text)
    assert r.exit_code == 12 and any(
        "ans.label_authored" in b for b in json.loads(r.output)["blocked"]
    )
    # configuration errors: no cite, empty text, a bad cite, a foreign question
    assert cli(q, "answer", "--question", qid, "--text", "-", input="x").exit_code == 15
    assert (
        cli(q, "answer", "--question", qid, "--text", "-", "--cite", aid, input="  ").exit_code
        == 15
    )
    assert (
        cli(
            q,
            "answer",
            "--question",
            "01NOTAQUESTION000000000000",
            "--text",
            "-",
            "--cite",
            aid,
            input="x",
        ).exit_code
        == 15
    )
    with pytest.raises(ConfigError, match="--cite expects"):
        parse_cite("not-an-id")
    assert parse_cite(f"{aid}:A_vs_B:diff").column == "diff"


def test_qualifier_names_accepted_flags_and_person_parameters(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    cli(q, "controls", "run", "--module", "compare-groups", "--allow-mock", env=MOCK)
    qid = json.loads(cli(q, "ask", "use bonferroni", "--json").output)["question_id"]
    # the agent's choice: held, accepted, run; the qualifier names the accepted flag
    r = cli(
        q,
        "call",
        "compare-groups",
        "--set",
        "correction=bonferroni",
        "--reason",
        "stricter",
        "--json",
    )
    assert r.exit_code == 10
    out = json.loads(r.output)
    hold = q.store.one(
        "SELECT hold_id FROM holds WHERE run_id=? AND step_id=?", (out["run_id"], out["step_id"])
    )
    accept_hold(q.store, hold["hold_id"], reason="fine")
    from stringency.machine import StepStatus, transition
    from stringency.steps import execute_engine, resume_after_hold

    rc = load_run(q, out["run_id"])
    transition(q.store, out["run_id"], out["step_id"], StepStatus.ADMISSIBLE)
    done = execute_engine(rc, resume_after_hold(rc, out["step_id"]))
    assert done.status == StepStatus.COMPLETED
    aid = q.store.scalar(
        "SELECT artifact_id FROM artifacts WHERE run_id=? AND step_id=?",
        (out["run_id"], out["step_id"]),
    )
    text = tmp_path / "a.md"
    r = _answer(q, qid, "A versus B: 59.22.", f"{aid}:A_vs_B:diff", path=text)
    assert r.exit_code == 0, r.output + str(r.stderr)
    out2 = json.loads(r.output)
    assert out2["label"] == "trusted"
    assert out2["qualifier"].startswith(
        f"flags accepted on the path: {out['step_id']}:param.agent_proposed | "
    )
    # the person's own value: no hold, named in the qualifier
    r = cli(
        q,
        "call",
        "compare-groups",
        "--set",
        "correction=bonferroni",
        "--asked-by",
        "person",
        "--reason",
        "the person said: use bonferroni",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out3 = json.loads(r.output)
    aid2 = out3["artifacts"][0]["artifact_id"]
    r = _answer(q, qid, "With bonferroni, A versus B: 59.22.", f"{aid2}:A_vs_B:diff", path=text)
    out4 = json.loads(r.output)
    assert out4["label"] == "trusted"
    assert f"person-set parameters: {out3['step_id']}.correction=bonferroni" in out4["qualifier"]
    assert "flags accepted on the path: none" in out4["qualifier"]
    # the provenance block of an artifact, as index.json will carry it (L35)
    block = provenance.block_for(rc, aid2)
    assert block["label"] == "trusted" and block["qualifier"]["person"].endswith(
        "correction=bonferroni"
    )


def test_pinned_sentences_are_the_engines() -> None:
    assert (
        provenance.SWITCH == OPEN_SWITCH and "Shall I open it for questions?" in provenance.SWITCH
    )
    assert set(provenance.LABEL_SENTENCES) == {"trusted", "untested", "untested, tool"}
    for s in provenance.LABEL_SENTENCES.values():
        assert "{matched} of {total}" in s and s.endswith(
            "Everything else in this answer is the assistant's reading."
        )
    assert provenance.QUALIFIER_LINE.count(" | ") == 5


def test_answer_cannot_records_an_unanswerable_question(questions: Project, tmp_path: Path) -> None:
    """L60: `answer --cannot --question <id> --reason` files an `answers` row with status
    unanswerable and no label, runs no predicate, names the question in the report's short list
    and counts it in the record; `--cannot` with `--text` or `--cite`, or without a reason, is
    a config error."""
    q = questions
    qid, aid, run_id = _ask_and_compare(q)
    r = cli(
        q,
        "answer",
        "--question",
        qid,
        "--cannot",
        "--reason",
        "the delivery holds no unit column",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "unanswerable" and out["label"] is None and out["run_id"] == run_id
    row = q.store.one("SELECT * FROM answers WHERE answer_id=?", (out["answer_id"],))
    assert row["status"] == "unanswerable" and row["label"] is None
    assert row["cited_json"] == "[]"
    assert q.store.message(row["text_ref"]) == "the delivery holds no unit column"
    assert (
        q.store.scalar(
            "SELECT COUNT(*) FROM predicate_results WHERE action_id=?", (out["answer_id"],)
        )
        == 0
    )
    ev = q.store.one(
        "SELECT payload_json FROM run_events WHERE run_id=? AND event='answer_recorded' ORDER BY rowid DESC LIMIT 1",
        (run_id,),
    )
    assert json.loads(ev["payload_json"])["status"] == "unanswerable"
    report = (q.root / "deliver" / run_id / "report.md").read_text()
    assert "could not be answered from the delivery. the delivery holds no unit column" in report
    assert "one could not be answered from the delivery." in report
    listing = json.loads(cli(q, "present", "--answers", "--json").output)
    mine = next(a for a in listing["answers"] if a["answer_id"] == out["answer_id"])
    assert mine["status"] == "unanswerable" and mine["label"] is None
    # an admissible answer filed later takes the question out of the unanswerable list
    text = tmp_path / "a.md"
    r = _answer(q, qid, "A is higher than B: the difference is 59.22.", f"{aid}:A_vs_B", path=text)
    assert r.exit_code == 0, r.output + str(r.stderr)
    report = (q.root / "deliver" / run_id / "report.md").read_text()
    assert "could not be answered" not in report
    # refusals
    r = cli(q, "answer", "--question", qid, "--cannot", "--reason", "x", "--text", "-", input="t")
    assert r.exit_code == 15
    r = cli(q, "answer", "--question", qid, "--cannot")
    assert r.exit_code == 15
    r = cli(q, "answer", "--question", "nope", "--cannot", "--reason", "x")
    assert r.exit_code == 16, r.output + str(r.stderr)
