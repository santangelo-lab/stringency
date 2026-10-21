"""Open mode, the report (spec/archive/open_mode_plan.md 2.7 and section 10, 2026-10-19): every
admissible answer lands in `deliver/<run>/` as it is filed, with `index.json` (`answers`, per-file
`provenance`, `report`), the deliver gate's verdicts recorded, a `deliveries` row only when the
content changed; `finding` marks and unmarks (append-only), and `report.md` (golden) leads with
the findings; the methods paragraph and coverage report for an open run; `present --answer` and
`--answers`; `deliver --answer` refused."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from stringency.deliver import deliver
from stringency.exit_codes import ConfigError, RefusedError
from stringency.project import Project
from stringency.provenance import TRUSTED_MEANS, UNTESTED_MEANS
from stringency.report import NO_FINDING_YET
from stringency.review import current_user
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
    # a probe for the cells: blocked (999 is no cell), so it is not in the report
    cells = json.loads(
        cli(
            q, "answer", "--question", q2, "--text", "-", "--cite", mid, "--json", input="probe 999"
        ).output
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


def test_answers_land_in_the_report_as_filed_and_findings_lead(
    answered: tuple[Project, Project, dict[str, str]], request: pytest.FixtureRequest
) -> None:
    up, q, ids = answered
    run_id = json.loads(cli(q, "next", "--json").output)["run_id"]
    rc = load_run(q, run_id)
    up_rc = load_run(up, up.store.scalar("SELECT run_id FROM runs"))
    dest = q.root / "deliver" / run_id
    # every admissible answer was written when it was filed: one `deliveries` row per change,
    # none for the two blocked answers
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 2
    index = json.loads((dest / "index.json").read_text())
    assert index["mode"] == "open" and index["report"]["file"] == "report.md"
    assert "summary" not in index and "written" in index
    assert [a["answer_id"] for a in index["answers"]] == [ids["a1"], ids["a2"]]
    assert all(a["finding"] is False for a in index["answers"])
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
    assert answer_md.startswith("# Question 1: Which group is higher, A or B?\n")
    assert (
        "Asked in the person's own words; answer " + ids["a1"] in answer_md
        and "Label: trusted." in answer_md
        and "Cited files: 01_compare-groups.comparison_table.tsv" in answer_md
        and "Runs: one of 1 run(s)" in answer_md
        and "Marked as a finding" not in answer_md
    )
    # the one reader-facing file is the report; nothing is marked yet
    assert not (dest / "summary.md").exists() and not (dest / "answers-summary.md").exists()
    report = (dest / "report.md").read_text()
    assert report.startswith(f"# Questions of {up.root.name}'s results\n")
    assert NO_FINDING_YET in report and "Shall I open it" not in report
    others = report[report.index("## Other questions") :]
    assert (
        "**1. Which group is higher, A or B?** (tool compare-groups; trusted). A is higher"
        in others
    )
    assert "**2. What is the mean per group?** (code written in the session; untested)." in others
    assert "Full answer with its tables: `q02-what-is-the-mean-per-group.md`." in others
    assert TRUSTED_MEANS in report and UNTESTED_MEANS in report
    # the deliver gate's verdicts are recorded on every regeneration
    rows = q.store.all(
        "SELECT predicate_id, fired FROM predicate_results WHERE run_id=? AND phase='deliver'",
        (run_id,),
    )
    assert {r_["predicate_id"] for r_ in rows} == {
        "prov.orphan_artifact",
        "prov.trace_inconsistent",
    } and not any(r_["fired"] for r_ in rows)
    # refusals: --answer is gone; a blocked, unknown or pipeline answer cannot be a finding
    r = cli(q, "deliver", "--answer", ids["a1"])
    assert r.exit_code == 16 and "finding" in str(r.stderr)
    with pytest.raises(RefusedError, match="finding"):
        deliver(rc, answer_ids=[ids["a1"]])
    with pytest.raises(RefusedError, match="declared topology"):
        deliver(up_rc, answer_ids=[ids["a1"]])
    assert cli(q, "finding", ids["blocked"]).exit_code == 15
    assert cli(q, "finding", "01BADBADBADBADBADBADBADBAD").exit_code == 15
    assert cli(up, "finding", ids["a1"]).exit_code == 16
    # `deliver` with nothing changed writes the same bytes and no row
    before = (dest / "index.json").read_bytes()
    r = cli(q, "deliver", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["changed"] is False
    assert (dest / "index.json").read_bytes() == before
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 2
    assert rc.status() == "running"
    # a finding: an append-only row, the index, the answer file, and the report leads with it
    r = cli(q, "finding", ids["a1"], "--reason", "this is the comparison I wanted", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["results"][0]["changed"] is True and out["findings"] == [ids["a1"]]
    frow = q.store.one("SELECT * FROM findings")
    assert frow["action"] == "mark" and frow["via"] == "tty" and frow["answer_id"] == ids["a1"]
    assert q.store.message(frow["reason_ref"]) == "this is the comparison I wanted"
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 3
    index = json.loads((dest / "index.json").read_text())
    assert index["answers"][0]["finding"] is True and index["answers"][1]["finding"] is False
    assert index["answers"][0]["finding_reason"] == "this is the comparison I wanted"
    answer_md = (dest / a1["file"]).read_text()
    assert answer_md.startswith("# Question 1: Which group is higher, A or B? (finding)\n")
    assert "Marked as a finding by" in answer_md
    report = (dest / "report.md").read_text()
    assert NO_FINDING_YET not in report and "one marked as a finding" in report
    found = report[report.index("## Findings") : report.index("## Other questions")]
    assert (
        "### Which group is higher, A or B?" in found
        and "Question 1, asked by the person." in found
    )
    assert (
        "| A_vs_B |" in found and "Label: trusted." in found and "Marked as a finding by" in found
    )
    assert "Full record: `q01-which-group-is-higher-a-or-b.md`." in found
    others = report[report.index("## Other questions") :]
    assert "**1. Which group" not in others and "**2. What is the mean per group?**" in others
    # marking again is a no-op; unmarking is a row; the report follows
    human = cli(q, "finding", ids["a1"]).output
    assert "already a finding" in human
    assert q.store.scalar("SELECT COUNT(*) FROM findings") == 1
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 3
    r = cli(q, "finding", ids["a1"], "--remove", "--json")
    assert r.exit_code == 0 and json.loads(r.output)["results"][0]["changed"] is True
    assert q.store.scalar("SELECT COUNT(*) FROM findings") == 2
    assert NO_FINDING_YET in (dest / "report.md").read_text()
    assert q.store.scalar("SELECT COUNT(*) FROM deliveries WHERE run_id=?", (run_id,)) == 4
    with pytest.raises(ConfigError, match="only an admissible"):
        from stringency.findings import mark

        mark(rc, [ids["blocked"]])
    r = cli(q, "finding", ids["a1"], "--reason", "this is the comparison I wanted")
    assert r.exit_code == 0
    # the reports
    cov = (dest / "coverage.md").read_text()
    assert "open mode:" in cov and "tools run without current controls: none" in cov
    assert "scripts written in the session: 02_exec" in cov
    assert (
        "explored: compare-groups@0.1.1 1 run(s), 1 distinct parameter set(s), 1 cited by findings (steps 01_compare-groups)"
        in cov
    )
    assert "questions: 1 in the person's own words, 1 suggested by the operator" in cov
    assert f"upstream lineage:\n    object: run {up_rc.run_id} of {up.root} (toy-process)" in cov
    assert cov.rstrip().endswith(
        "whether the upstream delivery was re-run after a question here was answered; and anything not listed above"
    )
    methods = (dest / "methods.md").read_text()
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
    report = (dest / "report.md").read_text()
    golden = GOLDEN / "report_open.md"
    got = (
        normalise(report)
        .replace(str(up.root), "<UPSTREAM>")
        .replace(str(q.root), "<PROJECT>")
        .replace(f"finding by {current_user()} on", "finding by <USER> on")
    )
    if request.config.getoption("--update-golden"):
        golden.write_text(got)
    assert got == golden.read_text()
    # present: the run view defaults to the run with the report; the answer view says where
    # the answer is in it; the list marks the finding
    r = cli(q, "present", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    view = json.loads(r.output)
    assert view["kind"] == "run" and view["run_id"] == run_id and len(view["deliverables"]) == 2
    r = cli(q, "present", "--answer", ids["a1"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    ans = json.loads(r.output)
    assert ans["kind"] == "answer" and ans["label"] == "trusted" and ans["route"] == "tool"
    assert ans["report"]["finding"] is True and ans["files"] == [str(dest / a1["file"])]
    assert ans["question"] == "Which group is higher, A or B?" and ans["tools"] == [
        "compare-groups@0.1.1"
    ]
    assert ans["cells"][ids["aid"]]["A_vs_B"]["diff"] == 59.22
    human = cli(q, "present", "--answer", ids["a1"]).output
    assert "Label: trusted." in human and "Cells the numbers were checked against:" not in human
    assert "In the report as q01-which-group-is-higher-a-or-b.md (a finding, marked by" in human
    detailed = cli(q, "present", "--answer", ids["a1"], "--details").output
    assert "Cells the numbers were checked against:" in detailed and "diff=59.22" in detailed
    assert "(not marked as a finding)" in cli(q, "present", "--answer", ids["a2"]).output
    r = cli(q, "present", "--answers", "--json")
    lst = json.loads(r.output)["answers"]
    listed = [a["answer_id"] for a in lst]
    assert listed[0] == ids["a1"] and listed[-1] == ids["blocked"] and ids["a2"] in listed
    assert len(listed) == 4  # the cells probe in the fixture filed a blocked answer too
    assert lst[0]["finding"] and lst[0]["in_report"]
    assert lst[-1]["status"] == "blocked" and not lst[-1]["in_report"]
    human = cli(q, "present", "--answers").output
    assert ids["blocked"] in human and "(blocked)" in human and "(trusted, finding)" in human
    # the console serves the report and the answer files by name
    from stringency.review_serve import served_files

    names = served_files(dest)
    assert "report.md" in names and names[a1["file"]][1] == "answer"
    # a second answer to a question gets its own file; the first keeps its name
    r = cli(
        q,
        "answer",
        "--question",
        ids["q1"],
        "--text",
        "-",
        "--cite",
        f"{ids['aid']}:A_vs_B:diff",
        "--json",
        input="The difference is 59.22.",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["report"]["file"] == "q01-which-group-is-higher-a-or-b-2.md"
    index = json.loads((dest / "index.json").read_text())
    # question order, then filing order
    assert [a["file"] for a in index["answers"]] == [
        "q01-which-group-is-higher-a-or-b.md",
        "q01-which-group-is-higher-a-or-b-2.md",
        "q02-what-is-the-mean-per-group.md",
    ]
    assert (dest / "q01-which-group-is-higher-a-or-b-2.md").exists()
    plain = json.loads(cli(q, "status", "--json").output)["plain"]
    assert "two asked, three answered, one marked as findings" in plain
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
    # the report takes the same view: regenerated, the finding shows the method's table
    cli(q, "deliver")
    report = (dest / "report.md").read_text()
    assert "**The comparison**" in report and "| contrast | diff | p_adj |" in report
    ans2 = json.loads(cli(q, "present", "--answer", ids["a2"], "--json").output)
    assert (
        ans2["route"] == "code"
        and ans2["label"] == "untested"
        and ans2["sections"][0]["title"] == "means (cited rows)"
    )
    assert re.match(r"^Label: untested\.", ans2["label_sentence"])
    r = cli(q, "present", "--answer", "01BADBADBADBADBADBADBADBAD")
    assert r.exit_code == 15


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
