"""Open mode S6, deliver and present (spec/plans/open_mode_plan.md 2.7): `deliver --answer`
from a running open run into its own directory, `index.json` with `answers` and per-file
`provenance`, the deliver gate's verdicts recorded, the summary with its open-mode sections
and `explored` (golden), the methods paragraph and coverage report for an open run, and
`present --answer` and `--answers`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from stringency.deliver import deliver
from stringency.exit_codes import ConfigError, RefusedError
from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_deliver import GOLDEN, normalise
from tests.test_open_init import delivered_process, open_project
from tests.test_run import MOCK, cli

MEANS = (
    "import csv, json, sys\njob = json.load(sys.stdin)\n"
    "rows = list(csv.DictReader(open(job['inputs']['object'])))\nby = {}\n"
    "for r in rows: by.setdefault(r['group'], []).append(float(r['value']))\n"
    "f = open(job['outputs']['means'], 'w'); f.write('group\\tmean\\n')\n"
    "[f.write(f'{g}\\t{sum(v)/len(v):.2f}\\n') for g, v in sorted(by.items())]\n"
)


@pytest.fixture
def answered(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> tuple[Project, Project, dict[str, str]]:
    """An open project with two admissible answers: one trusted (the controlled tool), one
    untested (a session script), and one blocked answer."""
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    cli(q, "controls", "run", "--module", "compare-groups", "--allow-mock", env=MOCK)
    q1 = json.loads(cli(q, "ask", "Which group is higher, A or B?", "--json").output)["question_id"]
    r = cli(q, "call", "compare-groups", "--question", q1, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    aid = json.loads(r.output)["artifacts"][0]["artifact_id"]
    q2 = json.loads(cli(q, "ask", "What is the mean per group?", "--suggested", "--json").output)[
        "question_id"
    ]
    script = tmp_path / "means.py"
    script.write_text(MEANS)
    r = cli(
        q,
        "exec",
        str(script),
        "--out",
        "means=table",
        "--allow-local",
        "--question",
        q2,
        "--seed",
        "3",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    mid = json.loads(r.output)["artifacts"][0]["artifact_id"]
    t = tmp_path / "t.md"
    t.write_text("A is higher than B: the difference is 59.22 (adjusted p 1.33e-75).")
    r = cli(q, "answer", "--question", q1, "--text", str(t), "--cite", f"{aid}:A_vs_B", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    a1 = json.loads(r.output)["answer_id"]
    cells = json.loads(
        cli(q, "answer", "--question", q2, "--text", "-", "--cite", mid, "--json", input="x").output
    )["cells"]
    t.write_text(
        f"The means are A {cells[mid]['A']['mean']}, B {cells[mid]['B']['mean']} and C {cells[mid]['C']['mean']}."
    )
    r = cli(q, "answer", "--question", q2, "--text", str(t), "--cite", mid, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    a2 = json.loads(r.output)["answer_id"]
    r = cli(
        q,
        "answer",
        "--question",
        q1,
        "--text",
        "-",
        "--cite",
        f"{aid}:A_vs_B",
        "--json",
        input="the difference is 60",
    )
    assert r.exit_code == 12
    blocked = json.loads(r.output)["answer_id"]
    return (
        up,
        q,
        {"q1": q1, "q2": q2, "a1": a1, "a2": a2, "blocked": blocked, "aid": aid, "mid": mid},
    )


def test_deliver_answers_writes_index_provenance_and_reports(
    answered: tuple[Project, Project, dict[str, str]], request: pytest.FixtureRequest
) -> None:
    up, q, ids = answered
    run_id = json.loads(cli(q, "next", "--json").output)["run_id"]
    rc = load_run(q, run_id)
    # refusals: no --answer, a blocked answer, and --answer on a pipeline run
    with pytest.raises(ConfigError, match="--answer"):
        deliver(rc)
    with pytest.raises(ConfigError, match="blocked"):
        deliver(rc, answer_ids=[ids["blocked"]])
    up_rc = load_run(up, up.store.scalar("SELECT run_id FROM runs"))
    with pytest.raises(RefusedError, match="declared topology"):
        deliver(up_rc, answer_ids=[ids["a1"]])
    r = cli(q, "deliver", "--answer", ids["a1"], "--answer", ids["a2"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    dest = Path(out["path"])
    # numbered per project, beside nothing of the pipeline's (2026-10-19)
    assert dest == q.root / "deliver" / "answers-01"
    index = json.loads((dest / "index.json").read_text())
    assert index["mode"] == "open" and [a["answer_id"] for a in index["answers"]] == [
        ids["a1"],
        ids["a2"],
    ]
    a1 = index["answers"][0]
    assert a1["label"] == "trusted" and a1["question"] == "Which group is higher, A or B?"
    assert a1["file"] == "q01-which-group-is-higher-a-or-b.md" and a1["files"] == [
        "01_compare-groups.comparison_table.tsv"
    ]
    assert a1["runs"].startswith(
        "one of 1 run(s) of compare-groups@0.1.1 on these inputs (1 distinct parameter set(s)); asked after 0 result(s)"
    )
    assert (
        a1["label_sentence"].startswith("Label: trusted.")
        and "controls: current" in a1["qualifier"]
    )
    a2 = index["answers"][1]
    assert (
        a2["label"] == "untested"
        and a2["origin"] == "suggested"
        and a2["files"] == ["02_exec.means.tsv"]
    )
    files = {f["file"]: f for f in index["files"]}
    assert set(files) == {"01_compare-groups.comparison_table.tsv", "02_exec.means.tsv"}
    for f in files.values():
        assert (dest / f["file"]).exists() and (dest / f["sidecar"]).exists()
        assert f["provenance"]["artifact_id"] == f["artifact_id"] and "qualifier" in f["provenance"]
    assert files["01_compare-groups.comparison_table.tsv"]["provenance"]["label"] == "trusted"
    assert files["02_exec.means.tsv"]["provenance"]["label"] == "untested"
    answer_md = (dest / a1["file"]).read_text()
    assert (
        answer_md.startswith("# Question 1: Which group is higher, A or B?")
        and "Asked in the person's own words; answer " + ids["a1"] in answer_md
        and "Label: trusted." in answer_md
    )
    assert (
        "Cited files: 01_compare-groups.comparison_table.tsv" in answer_md
        and "Runs: one of 1 run(s)" in answer_md
    )
    # the deliver gate's verdicts are recorded now
    rows = q.store.all(
        "SELECT predicate_id, fired FROM predicate_results WHERE run_id=? AND phase='deliver'",
        (run_id,),
    )
    assert {r_["predicate_id"] for r_ in rows} == {"prov.orphan_artifact"} and not any(
        r_["fired"] for r_ in rows
    )
    # the run stays running and may deliver again, into another directory
    assert (
        rc.status() == "running"
        and q.store.scalar("SELECT status FROM runs WHERE run_id=?", (run_id,)) == "running"
    )
    d2 = deliver(load_run(q, run_id), answer_ids=[ids["a2"]])
    assert d2.path == q.root / "deliver" / "answers-02" and [
        a["answer_id"] for a in d2.answers
    ] == [ids["a2"]]
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 2
    # the reports
    # the reader's files never share a name with the pipeline delivery's
    assert not (dest / "summary.md").exists() and index["summary"]["file"] == "answers-summary.md"
    cov = (dest / "answers-coverage.md").read_text()
    assert "open mode:" in cov and "tools run without current controls: none" in cov
    assert "scripts written in the session: 02_exec" in cov
    assert (
        "explored: compare-groups@0.1.1 1 run(s), 1 distinct parameter set(s), 1 delivered (steps 01_compare-groups)"
        in cov
    )
    assert "questions: 1 in the person's own words, 1 suggested by the operator" in cov
    assert f"upstream lineage:\n    object: run {up_rc.run_id} of {up.root} (toy-process)" in cov
    assert cov.rstrip().endswith(
        "whether the upstream delivery was re-run after a question here was answered; and anything not listed above"
    )
    methods = (dest / "answers-methods.md").read_text()
    assert (
        methods.startswith("Questions were answered with stringency")
        and "in open mode using the tools of method v0.1.0 (compare-groups@0.1.1, plot-groups@0.1.0"
        in methods
    )
    assert (
        "a script written in the session (blake3" in methods
        and "recorded untested (step 02_exec)" in methods
    )
    assert (
        f"Input object was delivered by stringency run {up_rc.run_id} (step 01_filter, output object)."
        in methods
    )
    summary = (dest / "answers-summary.md").read_text()
    assert "Shall I open it" not in summary
    assert (
        "## What was asked" in summary
        and "## What was untested" in summary
        and "## Explored" in summary
    )
    golden = GOLDEN / "summary_open.md"
    got = normalise(summary).replace(str(up.root), "<UPSTREAM>").replace(str(q.root), "<PROJECT>")
    # the echo wraps at 100 columns around the temporary path, whose length varies
    for pattern in (r"Delivery bound:.*?output object\)\.", r"The pipeline's own inputs.*?>\."):
        got = re.sub(pattern, lambda m: " ".join(m.group(0).split()), got, flags=re.S)
    if request.config.getoption("--update-golden"):
        golden.write_text(got)
    assert got == golden.read_text()
    # present: the run view defaults to the delivered run; the answer view; the list
    r = cli(q, "present", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    view = json.loads(r.output)
    assert view["kind"] == "run" and view["run_id"] == run_id and len(view["deliverables"]) == 1
    r = cli(q, "present", "--answer", ids["a1"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    ans = json.loads(r.output)
    assert ans["kind"] == "answer" and ans["label"] == "trusted" and ans["route"] == "tool"
    assert ans["question"] == "Which group is higher, A or B?" and ans["tools"] == [
        "compare-groups@0.1.1"
    ]
    assert ans["label_sentence"].startswith("Label: trusted.") and ans["qualifier"].startswith(
        "flags accepted"
    )
    assert ans["cells"][ids["aid"]]["A_vs_B"]["diff"] == 59.22
    assert (
        ans["sections"][0]["kind"] == "table"
        and ans["sections"][0]["title"] == "comparison_table (cited rows)"
    )
    assert ans["decisions"][0]["source"] == "default" and ans["files"] == [str(dest / a1["file"])]
    human = cli(q, "present", "--answer", ids["a1"]).output
    assert (
        "Label: trusted." in human
        and "Cells the numbers were checked against:" in human
        and "diff=59.22" in human
    )
    assert f"Delivered as {a1['file']}." in human
    r = cli(q, "present", "--answers", "--json")
    lst = json.loads(r.output)["answers"]
    listed = [a["answer_id"] for a in lst]
    assert listed[0] == ids["a1"] and listed[-1] == ids["blocked"] and ids["a2"] in listed
    assert len(listed) == 4  # the cells probe in the fixture filed a blocked answer too
    assert lst[0]["delivered"] and lst[-1]["status"] == "blocked" and not lst[-1]["delivered"]
    human = cli(q, "present", "--answers").output
    assert ids["blocked"] in human and "(blocked)" in human
    # a method's answer view for the tool: the tool's output through the view, with a head
    skills = q.method_root / "skills"
    skills.mkdir(exist_ok=True)
    (skills / "open.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "answer_view": [
                    {
                        "tool": "compare-groups",
                        "title": "The comparison",
                        "output": "comparison_table",
                        "kind": "table",
                        "columns": ["contrast", "diff", "p_adj"],
                        "head": 2,
                    }
                ],
            }
        )
    )
    ans = json.loads(cli(q, "present", "--answer", ids["a1"], "--json").output)
    assert ans["sections"][0]["title"] == "The comparison" and ans["sections"][0]["columns"] == [
        "contrast",
        "diff",
        "p_adj",
    ]
    assert ans["sections"][0]["note"] == "first 2 of 3 rows" and len(ans["sections"]) == 1
    assert ans["skill"] == "answer view from skills/open.yml"
    ans2 = json.loads(cli(q, "present", "--answer", ids["a2"], "--json").output)
    assert (
        ans2["route"] == "code"
        and ans2["label"] == "untested"
        and ans2["sections"][0]["title"] == "means (cited rows)"
    )
    assert re.match(r"^Label: untested\.", ans2["label_sentence"])
    r = cli(q, "present", "--answer", "01BADBADBADBADBADBADBADBAD")
    assert r.exit_code == 15

    # `all`: the latest admissible answer of every question, in the order asked
    d3 = deliver(load_run(q, run_id), answer_ids=["all"])
    assert [a["answer_id"] for a in d3.answers] == [ids["a1"], ids["a2"]]


def test_deliver_on_held_open_run_exits_10(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes")
    cli(q, "ask", "x")
    r = cli(
        q, "call", "compare-groups", "--set", "correction=bonferroni", "--reason", "r", "--json"
    )
    assert r.exit_code == 10
    r = cli(q, "deliver", "--answer", "01BADBADBADBADBADBADBADBAD")
    assert r.exit_code == 10 and "held" in str(r.stderr)
    r = cli(q, "present")
    assert r.exit_code == 0  # the open hold is presented
    r = cli(q, "present", "--run", json.loads(cli(q, "next", "--json").output)["run_id"], "--json")
    assert r.exit_code == 0 and json.loads(r.output)["deliverables"] == []
