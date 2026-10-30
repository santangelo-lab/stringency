"""The cited rows shown, figures attached, the report's order (engine 0.2.35; PLAN L141, L143,
L144): `present --answer --chat` prints the cited rows as one table per cited table restricted
to the key columns and the cited cells, then the figures, then the label sentence; `answer
--figure` attaches a figure with its own label, shown by `present`, `finding` and the report;
`finding --order` and `--under` arrange the findings; `deliver --story` opens the report with
the person's paragraph and refuses a numeral no finding cites; the lint on an open tool with no
answer view."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from stringency.lint import lint_path
from stringency.project import Project
from tests.conftest import MethodRepo
from tests.test_open_deliver import answered  # noqa: F401  (the fixture)
from tests.test_run import cli

FIGURE = (
    "import json, sys\njob = json.load(sys.stdin)\n"
    "open(job['outputs']['fig'], 'w').write("
    '\'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>\')\n'
)

Answered = tuple[Project, Project, dict[str, str]]


def _run_id(q: Project) -> str:
    return str(json.loads(cli(q, "next", "--json").output)["run_id"])


def _exec_figure(q: Project, tmp_path: Path, qid: str) -> str:
    script = tmp_path / "fig.py"
    script.write_text(FIGURE)
    r = cli(
        q,
        "exec",
        str(script),
        "--out",
        "fig=figure",
        "--allow-local",
        "--question",
        qid,
        "--reason",
        "a drawing of the comparison",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    return str(json.loads(r.output)["artifacts"][0]["artifact_id"])


def test_chat_block_shows_the_cited_rows_first(answered: Answered) -> None:  # noqa: F811
    _, q, ids = answered
    r = cli(q, "present", "--answer", ids["a1"], "--chat", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    chat = json.loads(r.output)["chat"]
    # a row cited by key: the key column and the cells the text's numerals are, not the row's
    # eight columns (p_value, 4.44e-76, is not said, though the gate's tolerance matches it)
    (t,) = chat["tables"]
    assert t["title"] == "comparison_table" and t["artifact_id"] == ids["aid"]
    assert t["columns"] == ["contrast", "diff", "p_adj"]
    assert t["rows"] == [["A_vs_B", "59.22", "1.33e-75"]]
    assert chat["figures"] == []
    block = cli(q, "present", "--answer", ids["a1"], "--chat").output
    assert block == (
        "**comparison_table**\n\n"
        "| contrast | diff | p_adj |\n|---|---|---|\n| A_vs_B | 59.22 | 1.33e-75 |\n\n"
        "Label: trusted. Produced by compare-groups (compare-groups@0.1.1), a tool shipped with "
        "the method, run by the engine on the delivered data. Numbers checked against the cited "
        "cells: 2 of 2. Everything else in this answer is the assistant's reading.\n"
    )
    # the question, the text and the full view only with --details, after the block
    assert "## Question 1" not in block and "mean_a" not in block
    detailed = cli(q, "present", "--answer", ids["a1"], "--chat", "--details").output
    assert detailed.startswith(block) and "\n---\n" in detailed
    assert "## Question 1: Which group is higher, A or B?" in detailed and "mean_a" in detailed
    # a table cited whole: the rows holding a said numeral, with their key
    block = cli(q, "present", "--answer", ids["a2"], "--chat").output
    assert block.startswith(
        "**means**\n\n| group | mean |\n|---|---|\n| A | 74.82 |\n| B | 15.86 |\n| C | 74.37 |\n"
    )
    assert "Label: untested." in block
    # without --chat the answer view is as before
    plain = cli(q, "present", "--answer", ids["a1"]).output
    assert plain.startswith("## Question 1: Which group is higher, A or B?")


def test_a_figure_is_attached_with_its_own_label(
    answered: Answered,  # noqa: F811
    tmp_path: Path,
) -> None:
    _, q, ids = answered
    fig = _exec_figure(q, tmp_path, ids["q1"])
    # a table, an unknown id: configuration errors, nothing filed
    n = q.store.scalar("SELECT COUNT(*) FROM answers")
    for bad in (ids["aid"], "01BADBADBADBADBADBADBADBAD"):
        r = cli(
            q,
            "answer",
            "--question",
            ids["q1"],
            "--cite",
            f"{ids['aid']}:A_vs_B",
            "--figure",
            bad,
            "--text",
            "-",
            input="The difference is 59.22.",
        )
        assert r.exit_code == 15, r.output
    assert q.store.scalar("SELECT COUNT(*) FROM answers") == n
    r = cli(
        q,
        "answer",
        "--question",
        ids["q1"],
        "--cite",
        f"{ids['aid']}:A_vs_B",
        "--figure",
        fig,
        "--text",
        "-",
        "--json",
        input="A is higher than B by 59.22.",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    a3 = out["answer_id"]
    # the answer keeps the tool's label; the figure, drawn by session code, carries its own
    assert out["label"] == "trusted" and out["provenance"]["route"] == "tool"
    (f,) = out["figures"]
    assert f["artifact_id"] == fig and f["name"] == "fig" and f["label"] == "untested"
    assert f["label_line"].startswith("Figure label: untested. Drawn by code written in this")
    stored = json.loads(
        q.store.scalar("SELECT provenance_json FROM answers WHERE answer_id=?", (a3,))
    )
    assert [g["artifact_id"] for g in stored["figures"]] == [fig]
    assert json.loads(
        q.store.scalar("SELECT cited_json FROM answers WHERE answer_id=?", (a3,))
    ) == [{"artifact_id": ids["aid"], "row": "A_vs_B"}]
    # present: beside the answer's label, and in the chat block with its path
    view = json.loads(cli(q, "present", "--answer", a3, "--json").output)
    assert view["label"] == "trusted" and view["figures"][0]["label"] == "untested"
    human = cli(q, "present", "--answer", a3).output
    assert "### Figure attached: fig" in human and "Figure label: untested." in human
    block = cli(q, "present", "--answer", a3, "--chat").output
    assert f"Figure fig: {f['path']}\nFigure label: untested." in block
    assert block.rstrip().endswith("the assistant's reading.") and "Label: trusted." in block
    # finding marks the answer with its figure; the report shows it under the answer
    r = cli(q, "finding", a3, "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["results"][0]["figures"] == [
        {"artifact_id": fig, "name": "fig", "label": "untested"}
    ]
    assert "marked as a finding, with figure fig" in cli(q, "finding", a3).output.replace(
        "already a finding", "marked as a finding"
    )
    dest = q.root / "deliver" / _run_id(q)
    index = json.loads((dest / "index.json").read_text())
    entry = next(e for e in index["answers"] if e["answer_id"] == a3)
    (ef,) = entry["figures"]
    assert ef["file"] and (dest / ef["file"]).exists() and ef["label"] == "untested"
    assert ef["file"] in {x["file"] for x in index["files"]}
    report = (dest / "report.md").read_text()
    found = report[report.index("## Findings") : report.index("## Other questions")]
    assert f"**Figure: fig**\n\n![fig]({ef['file']})\n\nFigure label: untested." in found
    assert found.index("Figure label: untested.") < found.index("Label: trusted.")
    assert f"Figure: {ef['file']}. Figure label: untested." in (dest / entry["file"]).read_text()


def test_order_headings_and_the_story(answered: Answered) -> None:  # noqa: F811
    _, q, ids = answered
    dest = q.root / "deliver" / _run_id(q)
    a1, a2 = ids["a1"], ids["a2"]
    assert cli(q, "finding", a1, a2).exit_code == 0
    report = (dest / "report.md").read_text()
    found = report[report.index("## Findings") : report.index("## Other questions")]
    assert found.index("### Which group is higher") < found.index("### What is the mean")
    # a place: the placed finding first, the rest in question order
    r = cli(q, "finding", a2, "--order", "1", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["placed"][0]["order"] == 1
    found = (dest / "report.md").read_text()
    assert found.index("### What is the mean") < found.index("### Which group is higher")
    # a heading in the person's words groups; the findings without one follow under their own
    r = cli(q, "finding", a1, "--under", "The comparison the study was for")
    assert r.exit_code == 0 and 'under "The comparison the study was for"' in r.output
    report = (dest / "report.md").read_text()
    found = report[report.index("## Findings") : report.index("## Other questions")]
    assert found.index("### The comparison the study was for\n\n#### Which group is higher") < (
        found.index("### Other findings\n\n#### What is the mean")
    )
    index = json.loads((dest / "index.json").read_text())
    by = {e["answer_id"]: e for e in index["answers"]}
    assert by[a1]["finding_heading"] == "The comparison the study was for"
    assert by[a2]["finding_order"] == 1 and by[a1]["finding_order"] is None
    assert q.store.scalar("SELECT COUNT(*) FROM run_events WHERE event='finding_placed'") == 2
    # --order and --under on an answer that is no finding mark it first; --remove takes neither
    assert cli(q, "finding", a1, "--remove", "--order", "2").exit_code == 15
    # the story: refused on a number no finding cites, nothing recorded
    r = cli(q, "deliver", "--story", "-", input="B trails A by 60 points.")
    assert r.exit_code == 16 and "60 is in no cell a finding cites" in str(r.stderr)
    assert q.store.scalar("SELECT COUNT(*) FROM run_events WHERE event='story_recorded'") == 0
    story = "We asked whether A is higher. It is, by 59.22, and C sits near A."
    r = cli(q, "deliver", "--story", "-", "--json", input=story)
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["story"]["numerals"]["matched"] == 1
    report = (dest / "report.md").read_text()
    head = report[: report.index("## Findings")]
    assert head.startswith("# Questions of ") and head.index(f"> {story}") < head.index(
        "What was asked"
    )
    assert f"\n> {story}\n\nThe paragraph above is in the person's own words, recorded by " in head
    assert "the engine did not write it" in head
    # a finding unmarked since: the report names the number no finding cites any longer
    assert cli(q, "finding", a1, "--remove").exit_code == 0
    assert "No finding cites 59.22 any longer." in (dest / "report.md").read_text()


def test_lint_warns_on_an_open_tool_without_an_answer_view(method_repo: MethodRepo) -> None:
    report = lint_path(method_repo.path)
    warned = [w for w in report.warnings if "no answer_view entry" in w]
    assert len(warned) == 2 and any("compare-groups lists open" in w for w in warned)
    skills = method_repo.path / "skills"
    skills.mkdir(exist_ok=True)
    (skills / "open.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "answer_view": [
                    {"tool": "compare-groups", "output": "comparison_table", "kind": "table"}
                ],
            }
        )
    )
    warned = [w for w in lint_path(method_repo.path).warnings if "no answer_view entry" in w]
    assert len(warned) == 1 and "plot-groups lists open" in warned[0]
