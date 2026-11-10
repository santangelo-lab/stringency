"""L157 (2026-11-09, the rule chosen 2026-11-10): a label with a numeral in it is not a
measurement. The Lyons Lung domain sweep's proposal (`at 5`, `at 6`, `4 is the cleaner cut`,
every one the key of a cited row) and a call's reason naming `cluster 6 in animal 6-2` from the
question both opened `param.reason_unmatched`.

The rule: a name is written in backticks and must resolve (a cited row's key, a design level, a
value the proposal sets or considered, a numeral of the question); a bare numeral is a
measurement and must match a cited cell; a hyphenated identifier, a year and a count before a
unit word need no mark. A reason whose only fault is a name written bare is refused before
anything is written, so a person is never asked to read a hold over a number that is only a
name. The proposal's reason and an answer are read by one classifier
(`ans.classify_numerals`)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from stringency.actions import Action
from stringency.predicates.registry import registry
from stringency.project import Project
from tests.helpers import make_action, make_ctx
from tests.test_open_answers import _answer, _ask_and_compare, questions  # noqa: F401
from tests.test_run import cli


def _sweep(tmp_path: Path) -> Path:
    path = tmp_path / "domain_sweep.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n_domains", "coherence_gain", "ari_to_previous", "max_single_replicate_share"])
        for row in [
            (4, 0.0613, 0.91, 0.21),
            (5, 0.023, 0.95, 0.3376),
            (6, -0.0207, 0.9792, 0.41),
            (7, 0.011, 0.7183, 0.52),
            (9, 0.004, 0.66, 0.7),
            (11, 0.001, 0.6, 0.8191),
        ]:
            w.writerow(row)
    return path


def _cite(path: Path, row: str, column: str | None, value: object) -> dict[str, object]:
    return {
        "source": "02_domain_sweep/domain_sweep",
        "path": str(path),
        "row": row,
        "column": column,
        "value": value if isinstance(value, dict) else str(value),
    }


def _proposal(project: Project, text: str, cited: list[dict[str, object]], **kw: object):  # type: ignore[no-untyped-def]
    action, _ = make_action(project, "01_filter", proposed={"min_value": 5})
    record = {"text": text, "cited": cited, "considered": kw.get("considered", []), **kw}
    action = Action(**{**action.__dict__, "rationale": record, "proposed_by": "agent"})
    spec = registry.get("param.reason_unmatched")
    assert spec is not None and spec.version == 3
    return spec.fn(make_ctx(project, "01_filter", phase="pre", action=action))


SWEEP_CITES = [
    ("5", "coherence_gain", 0.023),
    ("6", "coherence_gain", -0.0207),
    ("6", "ari_to_previous", 0.9792),
    ("4", "coherence_gain", 0.0613),
    ("11", "max_single_replicate_share", 0.8191),
]
# the Lyons Lung reason of 2026-11-06 in miniature, as it was written (every row named bare)
SWEEP_BARE = (
    "Five is where the sweep stops paying. coherence_gain is 0.023 at 5 and -0.0207 at 6, "
    "and ari_to_previous is 0.9792 at 6. 4 is the cleaner cut on its own numbers "
    "(coherence_gain 0.0613); max_single_replicate_share is 0.8191 at 11. 9 was weighed too."
)
# the same reason with each row named in backticks
SWEEP_MARKED = (
    "Five is where the sweep stops paying. coherence_gain is 0.023 at `5` and -0.0207 at `6`, "
    "and ari_to_previous is 0.9792 at `6`. `4` is the cleaner cut on its own numbers "
    "(coherence_gain 0.0613); max_single_replicate_share is 0.8191 at `11`. `9` was weighed too."
)


def test_the_domain_sweep_reason_names_its_rows_in_backticks_and_is_not_flagged(
    project: Project, tmp_path: Path
) -> None:
    sweep = _sweep(tmp_path)
    cited = [_cite(sweep, r, c, v) for r, c, v in SWEEP_CITES]
    v = _proposal(project, SWEEP_MARKED, cited, considered=[4, 5, 6, 7, 9])
    assert v.fired is False, v.reason
    # a measurement that no cited cell carries still fires, and it alone
    v = _proposal(
        project,
        SWEEP_MARKED + " boundary_share is 0.088 at `4`.",
        cited,
        considered=[4, 5, 6, 7, 9],
    )
    assert v.fired is True
    assert v.reason is not None and v.reason.startswith(
        "a numeral in the reason matches no cited cell: 0.088 (nearest: "
    )
    assert v.evidence["numerals"] == "0.088"
    assert {"numeral": "11", "class": "key"} in v.evidence["not_checked"]
    assert {"numeral": "9", "class": "considered"} in v.evidence["not_checked"]
    # a name that was weighed but not listed under --considered names nothing
    v = _proposal(project, SWEEP_MARKED, cited, considered=[4, 5])
    assert v.fired is True and v.evidence["numerals"] == "9"
    assert "in backticks it must name a cited row" in (v.reason or "")


def test_the_same_reason_written_bare_fails_only_on_its_names(
    project: Project, tmp_path: Path
) -> None:
    """Written as it was on 2026-11-06, every failure is a name that wants backticks and none is
    a number from nowhere: the case `propose` refuses before it writes anything."""
    from stringency.predicates.engine.ans import unmarked_names

    sweep = _sweep(tmp_path)
    cited = [_cite(sweep, r, c, v) for r, c, v in SWEEP_CITES]
    v = _proposal(project, SWEEP_BARE, cited, considered=[4, 5, 6, 7, 9])
    assert v.fired is True
    problems = v.evidence["problems"]
    assert [p["numeral"] for p in problems] == ["5", "6", "6", "4", "11", "9"]
    assert unmarked_names(problems) == problems
    assert (
        "5 (nearest: it equals a key value of a cited table; if it is that name, write it in backticks (`5`)"
        in (v.reason or "")
    )
    # one number from nowhere beside them, and it is no longer only a matter of form
    v = _proposal(project, SWEEP_BARE + " Roughly 3 of them agree.", cited, considered=[4, 5])
    assert unmarked_names(v.evidence["problems"]) == []


def test_a_name_in_backticks_must_be_a_row_the_reason_cites(
    project: Project, tmp_path: Path
) -> None:
    """A row of the table that was not cited is not a name the reason may use: cite the row
    (a citation of the row with no column), and it is."""
    sweep = _sweep(tmp_path)
    one = [_cite(sweep, "5", "coherence_gain", 0.023)]
    text = "At `7` the maps split the parenchyma; 0.023 at `5`."
    v = _proposal(project, text, one)
    assert v.fired is True
    assert "7 (nearest: in backticks it must name a cited row" in (v.reason or "")
    row7 = _cite(sweep, "7", None, {"coherence_gain": 0.011, "ari_to_previous": 0.7183})
    v = _proposal(project, text, [*one, row7])
    assert v.fired is False, v.reason
    # the value rule's blind spot: a wrong measurement that equals a row's key
    v = _proposal(project, "The gain at `6` is 4.", [_cite(sweep, "6", "coherence_gain", -0.0207)])
    assert v.fired is True and v.evidence["numerals"] == "4"


def test_a_reason_with_a_measurement_and_no_citation_still_fires(project: Project) -> None:
    v = _proposal(project, "A floor of `5`; 3 groups.", [])
    assert v.fired is True
    assert v.reason == "the reason carries numerals (3) and cites nothing"
    assert v.evidence["not_checked"] == [{"numeral": "5", "class": "param"}]


def test_a_call_names_the_question_s_cluster_in_backticks_and_its_animal_as_written(
    questions: Project,  # noqa: F811
) -> None:
    """The Lyons Lung call of 2026-11-09: `cluster 6 in animal 6-2` in the reason, nothing cited,
    opened `param.reason_unmatched` (6, 6, 2). The animal's identifier needs no mark. The
    cluster is the question's own word: bare, the call is refused before a step is registered;
    in backticks it passes; a number from nowhere still opens the hold. An agent-chosen value
    opens `param.agent_proposed` either way, so the holds are told apart by kind."""
    from stringency.review import queue

    q = questions
    asked = json.loads(
        cli(q, "ask", "Is group A above B for cluster 6 in animal 6-2?", "--json").output
    )
    qid = asked["question_id"]

    def call(reason: str):  # type: ignore[no-untyped-def]
        return cli(
            q,
            "call",
            "compare-groups",
            "--question",
            qid,
            "--set",
            "correction=bonferroni",
            "--reason",
            reason,
            "--json",
        )

    def steps() -> int:
        # the open run's own steps (the tool's controls run on first use, in runs of their own)
        return int(
            q.store.scalar(
                "SELECT COUNT(*) FROM steps s JOIN runs r ON r.run_id = s.run_id "
                "WHERE r.kind = 'run'"
            )
            or 0
        )

    before, holds_before = steps(), len(queue(q))
    r = call("the person asked about cluster 6 in animal 6-2")
    assert r.exit_code == 16, r.output + str(r.stderr)
    said = r.output + str(r.stderr)
    assert "matches no cited cell and equals a name: 6 (a numeral in the question)" in said
    assert "No proposal was recorded" in said
    assert steps() == before and len(queue(q)) == holds_before  # no step, no hold

    def holds_after(reason: str) -> dict[str, str]:
        seen = {h["hold_id"] for h in queue(q)}
        r = call(reason)
        assert r.exit_code == 10, r.output + str(r.stderr)
        return {
            h["reason"].split(":")[0]: h["reason"] for h in queue(q) if h["hold_id"] not in seen
        }

    by = holds_after("the person asked about cluster `6` in animal 6-2")
    assert sorted(by) == ["param.agent_proposed"], by
    by = holds_after("cluster `6` in animal 6-2, over 3 groups")
    assert sorted(by) == ["param.agent_proposed", "param.reason_unmatched"], by
    assert by["param.reason_unmatched"] == (
        "param.reason_unmatched: the reason carries numerals (3) and cites nothing"
    )


def test_an_answer_may_name_an_animal_by_its_identifier(
    questions: Project,  # noqa: F811
    tmp_path: Path,
) -> None:
    q = questions
    qid, aid, _ = _ask_and_compare(q)
    r = _answer(
        q,
        qid,
        "Animal 6-2 aside, the difference is 59.22.",
        f"{aid}:A_vs_B",
        path=tmp_path / "a.md",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["numerals"]["not_checked"] == [
        {"numeral": "6", "class": "id"},
        {"numeral": "2", "class": "id"},
    ]
    assert (out["numerals"]["matched"], out["numerals"]["total"]) == (1, 1)
