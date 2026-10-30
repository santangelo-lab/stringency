"""The fit of a tool to the question (L139) and the label's two parts (L140), 2026-10-29.

L139: `ask --wants` is stored on the question and shown by `ask --json`; `call --gives` and
`exec --gives` go on the step's `created` event and into the answer's provenance; `present
--answer` shows wants and gives side by side under the text; the coverage report lists the
questions without a wants and counts the answers whose gives is not their wants (exact text);
an analyze file's `tools[i].not_for` is rendered under the use-when line and carried by `tools
list` in `words`.

L140: an exec whose bound inputs are all trusted, whose outputs are figures and a
`figure_drawn` table, and whose drawn numbers all match cells of its inputs is labelled
"trusted data, drawn by session code", the qualifier naming its script; a drawn number that
matches no input cell, or an exec that also writes a table, stays untested."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from stringency import provenance
from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import cli


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    return q


# A toy figure exec: reads the comparison table bound as `tbl`, draws one bar per row into an
# SVG, and writes the numbers it drew to `figure_drawn` (every column of every row, as read).
# `SCALE` multiplies `diff` (a drawn number no input holds when it is not 1); `EXTRA` adds a
# table output, which no drawing writes.
DRAW = """import csv, json, sys
job = json.load(sys.stdin)
SCALE = {scale}
rows = list(csv.DictReader(open(job['inputs']['tbl']), delimiter='\\t'))
cols = list(rows[0])
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">']
for i, r in enumerate(rows):
    if SCALE != 1:
        r['diff'] = str(float(r['diff']) * SCALE)
    svg.append(f'<rect x="{{10 + 30 * i}}" y="10" width="20" height="{{abs(float(r["diff"]))}}"/>')
svg.append('<text x="10" y="95">difference, new axis label</text></svg>')
open(job['outputs']['bars'], 'w').write('\\n'.join(svg))
w = csv.DictWriter(open(job['outputs']['figure_drawn'], 'w', newline=''), fieldnames=cols, delimiter='\\t')
w.writeheader(); w.writerows(rows)
if 'summary' in job['outputs']:
    open(job['outputs']['summary'], 'w').write('rows\\n' + str(len(rows)) + '\\n')
"""


def _compare(q: Project, qid: str, gives: str | None = None) -> tuple[str, str]:
    args = ["call", "compare-groups", "--question", qid, "--json"]
    if gives:
        args += ["--gives", gives]
    r = cli(q, *args)
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    return out["step_id"], out["artifacts"][0]["artifact_id"]


def _draw(
    q: Project, tmp_path: Path, step: str, qid: str, *, scale: float = 1, extra: bool = False
):  # type: ignore[no-untyped-def]
    script = tmp_path / f"draw_{scale}_{extra}.py"
    script.write_text(DRAW.format(scale=scale))
    args = [
        "exec",
        str(script),
        "--in",
        f"tbl=$steps.{step}.comparison_table",
        "--out",
        "bars=figure",
        "--out",
        "figure_drawn=table",
        "--question",
        qid,
        "--gives",
        "a bar per comparison of the difference",
        "--allow-local",
        "--json",
    ]
    if extra:
        args += ["--out", "summary=table"]
    r = cli(q, *args)
    assert r.exit_code == 0, r.output + str(r.stderr)
    return json.loads(r.output)


def _answer(q: Project, qid: str, text: str, *cites: str, path: Path) -> dict:  # type: ignore[type-arg]
    path.write_text(text)
    args = ["answer", "--question", qid, "--text", str(path), "--json"]
    for c in cites:
        args += ["--cite", c]
    r = cli(q, *args)
    assert r.exit_code == 0, r.output + str(r.stderr)
    return json.loads(r.output)


def _artifact(out: dict, name: str) -> str:  # type: ignore[type-arg]
    return next(a["artifact_id"] for a in out["artifacts"] if a["name"] == name)


# -- L140: the label's two parts ----------------------------------------------------------


def test_a_figure_drawn_from_a_trusted_table_is_trusted_data_drawn_by_session_code(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    qid = json.loads(cli(q, "ask", "draw the differences", "--json").output)["question_id"]
    step, table = _compare(q, qid)
    out = _draw(q, tmp_path, step, qid)
    assert out["label"] == provenance.DRAWN, out["drawing"]
    assert out["drawing"]["drawing"] is True and out["drawing"]["why"] is None
    assert out["drawing"]["matched"] == out["drawing"]["cells"] > 0
    human = cli(
        q,
        "exec",
        str(tmp_path / "draw_1_False.py"),
        "--in",
        f"tbl=$steps.{step}.comparison_table",
        "--out",
        "bars=figure",
        "--out",
        "figure_drawn=table",
        "--allow-local",
    ).output
    assert "trusted data, drawn by session code: every number its figure_drawn holds" in human
    fig = _artifact(out, "bars")
    ans = _answer(q, qid, "The bars show each comparison's difference.", fig, path=tmp_path / "a")
    assert ans["label"] == "trusted data, drawn by session code"
    assert ans["label_sentence"] == (
        "Label: trusted data, drawn by session code. The numbers are the cells of "
        "comparison_table from compare-groups (compare-groups@0.1.1), trusted; the drawing is "
        "code written in this session, which nothing has checked. Numbers checked against the "
        "cited cells: 0 of 0. Everything else in this answer is the assistant's reading."
    )
    script = f"runs/{out['run_id']}/{out['step_id']}/script.py"
    assert f"untested inputs: {out['step_id']} (drawing: {script})" in ans["qualifier"]
    row = q.store.one("SELECT label FROM answers WHERE answer_id=?", (ans["answer_id"],))
    assert row["label"] == provenance.DRAWN
    # the drawn table itself carries the same label, and a citation of the trusted table beside
    # the figure does not change it
    ans2 = _answer(
        q,
        qid,
        "A versus B: 59.22.",
        f"{table}:A_vs_B:diff",
        _artifact(out, "figure_drawn"),
        path=tmp_path / "b",
    )
    assert ans2["label"] == provenance.DRAWN
    # present --answer says the two parts
    shown = cli(q, "present", "--answer", ans["answer_id"]).output
    assert "Label: trusted data, drawn by session code. The numbers are" in shown


def test_a_drawn_number_that_matches_no_input_cell_stays_untested(
    questions: Project, tmp_path: Path
) -> None:
    q = questions
    qid = json.loads(cli(q, "ask", "draw the differences", "--json").output)["question_id"]
    step, _ = _compare(q, qid)
    out = _draw(q, tmp_path, step, qid, scale=2)
    assert out["label"] == provenance.UNTESTED
    assert out["drawing"]["drawing"] is False
    assert "match no cell of its inputs" in out["drawing"]["why"]
    ans = _answer(q, qid, "The bars.", _artifact(out, "bars"), path=tmp_path / "a")
    assert ans["label"] == "untested" and ans["label_sentence"].startswith(
        "Label: untested. Produced by code written for this question"
    )
    assert f"untested inputs: {out['step_id']} |" in ans["qualifier"]


def test_an_exec_that_writes_a_table_stays_untested(questions: Project, tmp_path: Path) -> None:
    q = questions
    qid = json.loads(cli(q, "ask", "draw the differences", "--json").output)["question_id"]
    step, _ = _compare(q, qid)
    out = _draw(q, tmp_path, step, qid, extra=True)
    assert out["label"] == provenance.UNTESTED
    assert out["drawing"]["why"] == "it writes summary (table), not a figure"
    ans = _answer(q, qid, "The bars.", _artifact(out, "bars"), path=tmp_path / "a")
    assert ans["label"] == "untested"


def test_a_drawing_of_an_untested_table_stays_untested(questions: Project, tmp_path: Path) -> None:
    """Each input's own label counts: a figure drawn from a table a session script wrote is not
    a drawing of trusted data, however exactly its numbers match."""
    q = questions
    qid = json.loads(cli(q, "ask", "draw the differences", "--json").output)["question_id"]
    step, _ = _compare(q, qid)
    copy = tmp_path / "copy.py"
    copy.write_text(
        "import json, shutil, sys\njob = json.load(sys.stdin)\n"
        "shutil.copy(job['inputs']['tbl'], job['outputs']['comparison_table'])\n"
    )
    r = cli(
        q,
        "exec",
        str(copy),
        "--in",
        f"tbl=$steps.{step}.comparison_table",
        "--out",
        "comparison_table=table",
        "--allow-local",
        "--json",
    )
    assert r.exit_code == 0, r.output
    out = _draw(q, tmp_path, json.loads(r.output)["step_id"], qid)
    assert out["label"] == provenance.UNTESTED
    assert out["drawing"]["why"] == "its input tbl is not trusted"


def test_drawn_numbers_match_with_the_numeral_tolerance() -> None:
    values = sorted([0.12345, 3.0, 59.22, 1.33e-75, 1500.0])
    assert provenance._matches_any("0.12", values)  # rounded to the precision written
    assert provenance._matches_any("59.22", values) and provenance._matches_any("3", values)
    assert provenance._matches_any("1.33e-75", values)
    assert not provenance._matches_any("0.13", values)
    assert not provenance._matches_any("118.44", values)
    assert not provenance._matches_any("1501", values)


def test_the_label_vocabulary_has_three_values() -> None:
    assert provenance.LABELS == ("trusted", "trusted data, drawn by session code", "untested")
    tool = provenance.StepFact(
        step_id="01_compare-groups",
        kind="tool",
        module="compare-groups@0.1.1",
        status="completed",
        runner="engine",
        env_status="verified",
        controls="current",
    )
    drawing = provenance.StepFact(
        step_id="02_exec",
        kind="exec",
        status="completed",
        runner="engine",
        env_status="verified",
        drawn={"drawing": True, "script": "runs/R/02_exec/script.py", "tables": ["t from x"]},
    )
    assert provenance.label_for([tool]) == provenance.TRUSTED
    assert provenance.label_for([drawing, tool]) == provenance.DRAWN
    drawing.env_status = "as_reported"  # code not run under a verified environment is untested
    assert provenance.label_for([drawing, tool]) == provenance.UNTESTED
    assert provenance.untested_reason([drawing, tool]) == "exec"
    drawing.env_status, drawing.drawn = "verified", {"drawing": False, "why": "x"}
    assert provenance.label_for([drawing, tool]) == provenance.UNTESTED


# -- L139: the fit ------------------------------------------------------------------------


def test_wants_and_gives_are_recorded_shown_and_counted(questions: Project, tmp_path: Path) -> None:
    """One question whose tool gives what it wants, one near miss (the tool's gives is not the
    wants), one question filed without a wants: the coverage report counts one of two answers
    as giving what its question did not want, and lists the question without a wants."""
    q = questions
    r = cli(
        q, "ask", "Which group is higher?", "--wants", "the difference between groups", "--json"
    )
    asked = json.loads(r.output)
    assert asked["wants"] == "the difference between groups"
    row = q.store.one("SELECT wants FROM questions WHERE question_id=?", (asked["question_id"],))
    assert row["wants"] == "the difference between groups"
    assert "\nwants: a count\n" in cli(q, "ask", "How many?", "--wants", "a count").output
    qid = asked["question_id"]
    step, aid = _compare(q, qid, gives="the difference between groups")
    entry = load_run(q, _run_id(q)).on_demand_entry(step)
    assert entry is not None and entry["gives"] == "the difference between groups"
    ans = _answer(q, qid, "A is higher: 59.22.", f"{aid}:A_vs_B:diff", path=tmp_path / "a")
    assert ans["provenance"]["fit"] == {
        "wants": "the difference between groups",
        "gives": "the difference between groups",
        "differs": False,
        "line": "wants: the difference between groups | gives: the difference between groups",
    }
    # the near miss: the question wants a per-unit spread, the tool gives the difference
    near = json.loads(
        cli(
            q, "ask", "How variable is A per unit?", "--wants", "the spread of A per unit", "--json"
        ).output
    )["question_id"]
    _, aid2 = _compare(q, near, gives="the difference between groups")
    miss = _answer(q, near, "A and B differ by 59.22.", f"{aid2}:A_vs_B:diff", path=tmp_path / "b")
    assert miss["provenance"]["fit"]["differs"] is True
    shown = cli(q, "present", "--answer", miss["answer_id"]).output
    text_at = shown.index("A and B differ by 59.22.")
    assert (
        shown.index("wants: the spread of A per unit | gives: the difference between groups")
        > text_at
    )
    assert (
        json.loads(cli(q, "present", "--answer", miss["answer_id"], "--json").output)["fit"][
            "differs"
        ]
        is True
    )
    # a question without a wants
    cli(q, "ask", "Anything else?")
    from stringency.coverage import coverage_data, fit_coverage, render_coverage

    rc = load_run(q, _run_id(q))
    fit = fit_coverage(rc)
    assert fit["answers"] == 2 and fit["gives_is_wants"] == 1 and fit["not_compared"] == 0
    assert [d["question"] for d in fit["gives_not_wants"]] == [3]
    assert fit["questions_without_wants"] == [4]
    text = render_coverage(coverage_data(rc))
    assert "questions filed without what would answer them (no --wants): #4" in text
    assert (
        "fit, by the exact text of gives against wants and no other rule: 1 of 2 answer(s) give "
        "what their question did not want, 1 give what it wanted, 0 not compared" in text
    )
    assert "#3 answer " in text and "wants the spread of A per unit; gives the difference" in text
    # the delivered coverage.md carries it
    cov = (q.root / "deliver" / rc.run_id / "coverage.md").read_text()
    assert "1 of 2 answer(s) give what their question did not want" in cov


def _run_id(q: Project) -> str:
    return str(
        q.store.scalar("SELECT run_id FROM runs WHERE kind='run' ORDER BY rowid DESC LIMIT 1")
    )


def test_not_for_is_rendered_and_listed(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    from tests.test_render_skill import _toy_analyze, _toy_repo, _toy_tools, rs

    repo = _toy_repo(tmp_path / "repo")
    tools = _toy_tools()
    tools["tools"][0]["not_for"] = "the spread of one group, which it does not compute"
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump({**_toy_analyze(), **tools}))
    ctx, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert not problems, problems
    out = rs.render(ctx)
    assert (
        "- Compare the groups (`compare-groups`): use when the person asks which group is "
        "higher or how two groups differ.\n"
        "  - not for the spread of one group, which it does not compute.\n"
    ) in out
    tools["tools"][0]["not_for"] = "  "
    src.write_text(yaml.safe_dump({**_toy_analyze(), **tools}))
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert any("`not_for` must say" in p for p in problems), problems
    # tools list carries it in words, and says it under use when
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    skills = up.method_root / "skills"
    skills.mkdir()
    (skills / "toy-process.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "pipeline": "toy-process",
                "tools": [
                    {
                        "module": "compare-groups",
                        "title": "Compare the groups",
                        "use_when": "the person asks which group is higher",
                        "not_for": "the spread of one group",
                    }
                ],
            }
        )
    )
    payload = json.loads(cli(up, "tools", "list", "--json").output)
    assert payload["tools"][0]["words"]["not_for"] == "the spread of one group"
    human = cli(up, "tools", "list").output
    assert (
        "  use when: the person asks which group is higher\n  not for: the spread of one group"
        in human
    )
