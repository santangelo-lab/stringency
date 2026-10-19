"""Open mode S7: the whole chain on the toy through the CLI (spec/plans/open_mode_plan.md 7):
a pipeline delivers; tools are listed; the open project is bound from the delivery and the
switch accepted; a question is asked and answered with a tool (its controls run before its first
use), then with a script, then with a script on the upstream pipeline's own input; an answer is
blocked and then admissible; the answers are delivered under readable names and presented; the
project's README says what is where; `run` is refused."""

from __future__ import annotations

import json
from pathlib import Path

from stringency.echo import OPEN_SWITCH
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process
from tests.test_run import cli


def test_open_mode_end_to_end(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    # the operator reviews the tools and the questions before proposing the switch
    tools = json.loads(cli(up, "tools", "list", "--context", "--json").output)
    assert [t["name"] for t in tools["tools"]] == ["compare-groups", "plot-groups"]
    assert tools["context"]["objective"]["question"] == "process_rows"
    # the open project, bound from the delivery; its echo is the switch paragraph
    r = cli(
        up,
        "init",
        str(tmp_path / "questions"),
        "--method",
        method_repo.spec,
        "--mode",
        "open",
        "--from-delivery",
        str(delivery),
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--execution",
        "engine",
        "--owner",
        "tester",
        "--reviewer",
        "tester",
        "--json",
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    init = json.loads(r.output)
    assert " ".join(OPEN_SWITCH.split()) in " ".join(Path(init["echo"]).read_text().split())
    from stringency.project import Project

    q = Project.load(tmp_path / "questions")
    assert cli(q, "run").exit_code == 16 and cli(q, "ask", "x").exit_code == 10
    accept_hold(q.store, init["confirm_hold"], reason="the person said yes")
    # the upstream pipeline's own input is bound beside the delivery, read-only
    assert q.inputs.by_name()["upstream_groups"].upstream_input is not None
    # a trusted tool: its controls run before its first use, then it runs for the question
    qid = json.loads(cli(q, "ask", "Which group is higher, A or B?", "--json").output)[
        "question_id"
    ]
    call = json.loads(cli(q, "call", "compare-groups", "--question", qid, "--json").output)
    assert call["status"] == "completed"
    assert call["controls_run"] and all(c["passed"] for c in call["controls_run"])
    assert call["inputs"]["object"].endswith("01_filter.object.csv")  # the delivery, not raw
    aid = call["artifacts"][0]["artifact_id"]
    # a figure from the second tool, chained on the first
    plot = json.loads(cli(q, "call", "plot-groups", "--question", qid, "--json").output)
    assert plot["status"] == "completed" and plot["artifacts"][0]["kind"] == "figure"
    # a script for what no tool answers
    q2 = json.loads(cli(q, "ask", "How many rows per group?", "--json").output)["question_id"]
    script = tmp_path / "count.py"
    script.write_text(
        "import csv, json, sys\njob = json.load(sys.stdin)\nby = {}\n"
        "for r in csv.DictReader(open(job['inputs']['object'])): by[r['group']] = by.get(r['group'], 0) + 1\n"
        "f = open(job['outputs']['counts'], 'w'); f.write('group\\tn\\n')\n"
        "[f.write(f'{g}\\t{n}\\n') for g, n in sorted(by.items())]\n"
    )
    ex = json.loads(
        cli(
            q,
            "exec",
            str(script),
            "--out",
            "counts=table",
            "--allow-local",
            "--question",
            q2,
            "--json",
        ).output
    )
    assert ex["status"] == "completed" and ex["label"] == "untested"
    cid = ex["artifacts"][0]["artifact_id"]
    # an answer blocked on a numeral, then admissible and trusted; the untested one on the script
    r = cli(
        q,
        "answer",
        "--question",
        qid,
        "--text",
        "-",
        "--cite",
        f"{aid}:A_vs_B",
        input="A exceeds B by 60.",
    )
    assert r.exit_code == 12
    r = cli(
        q,
        "answer",
        "--question",
        qid,
        "--text",
        "-",
        "--cite",
        f"{aid}:A_vs_B",
        "--cite",
        plot["artifacts"][0]["artifact_id"],
        "--json",
        input="A exceeds B by 59.22; see the figure.",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    a1 = json.loads(r.output)
    assert a1["label"] == "trusted" and a1["label_sentence"].startswith("Label: trusted.")
    import csv

    with open(ex["artifacts"][0]["path"], newline="") as f:
        counts = {row["group"]: row for row in csv.DictReader(f, delimiter="\t")}
    text = ", ".join(f"{g} has {row['n']} rows" for g, row in counts.items()) + "."
    r = cli(q, "answer", "--question", q2, "--text", "-", "--cite", cid, "--json", input=text)
    assert r.exit_code == 0, r.output + str(r.stderr)
    a2 = json.loads(r.output)
    assert a2["label"] == "untested"
    assert "on the delivered data" in a2["label_sentence"]
    # a script on the pipeline's own input: what the filter removed
    q3 = json.loads(cli(q, "ask", "How many rows were there before filtering?", "--json").output)[
        "question_id"
    ]
    raw = tmp_path / "raw.py"
    raw.write_text(
        "import csv, json, sys\njob = json.load(sys.stdin)\n"
        "n = sum(1 for _ in csv.DictReader(open(job['inputs']['upstream_groups'])))\n"
        "open(job['outputs']['n'], 'w').write(f'rows\\n{n}\\n')\n"
    )
    ex3 = json.loads(
        cli(
            q,
            "exec",
            str(raw),
            "--in",
            "upstream_groups=$inputs.upstream_groups",
            "--out",
            "n=table",
            "--allow-local",
            "--question",
            q3,
            "--json",
        ).output
    )
    assert ex3["status"] == "completed", ex3
    r = cli(
        q,
        "answer",
        "--question",
        q3,
        "--text",
        "-",
        "--cite",
        ex3["artifacts"][0]["artifact_id"],
        "--json",
        input="Before filtering there were "
        + Path(ex3["artifacts"][0]["path"]).read_text().split()[1]
        + " rows.",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    # the delivered files are bound too, so the script could read both
    assert (
        "on the delivered data and the pipeline's inputs" in json.loads(r.output)["label_sentence"]
    )
    # delivered beside the upstream delivery, with the labels, then presented
    r = cli(q, "deliver", "--answer", a1["answer_id"], "--answer", a2["answer_id"], "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    d = json.loads(r.output)
    index = json.loads((Path(d["path"]) / "index.json").read_text())
    assert [a["label"] for a in index["answers"]] == ["trusted", "untested"]
    assert {f["kind"] for f in index["files"]} == {"table", "figure"}
    dest = Path(d["path"])
    assert dest.name == "answers-01"
    summary = (dest / "answers-summary.md").read_text()
    assert summary.count("## ") == 9 and "Shall I open it" not in summary
    assert [a["file"] for a in index["answers"]] == [
        "q01-which-group-is-higher-a-or-b.md",
        "q02-how-many-rows-per-group.md",
    ]
    readme = (q.root / "README.md").read_text()
    assert "Which group is higher, A or B?" in readme and "deliver/answers-01/" in readme
    assert "`controls/<tool>/<control>/`" in readme and "tool compare-groups" in readme
    shown = cli(q, "present", "--answer", a1["answer_id"]).output
    assert (
        "Label: trusted." in shown
        and "Which group is higher, A or B?" in shown
        and "diff=59.22" in shown
    )
    assert "figure:" in shown  # the cited figure is a section of the answer view
    listed = json.loads(cli(q, "present", "--answers", "--json").output)["answers"]
    assert sum(1 for a in listed if a["delivered"]) == 2
    # the upstream delivery is untouched
    assert (delivery / "01_filter.object.csv").exists()
    assert up.store.scalar("SELECT COUNT(*) FROM deliveries") == 1
    board = cli(q, "status", "--json").output
    assert "Open for questions: three asked, three answered" in json.loads(board)["plain"]
