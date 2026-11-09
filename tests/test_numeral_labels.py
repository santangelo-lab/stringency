"""L157 (2026-11-09): a label with a numeral in it is not a measurement. The Lyons Lung domain
sweep's proposal (`at 5`, `at 6`, `4 is the cleaner cut`, every one the key of a cited row) and
a call's reason naming `cluster 6 in animal 6-2` from the question both opened
`param.reason_unmatched`; the proposal's reason is now read by the answer's classifier
(`ans.classify_numerals`) with the row keys of the cited tables, the considered values, the
parameter values, the question and the identifier rule as exemptions. The answer side gains the
same three classes."""

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


def _cite(path: Path, row: str, column: str, value: object) -> dict[str, object]:
    return {
        "source": "02_domain_sweep/domain_sweep",
        "path": str(path),
        "row": row,
        "column": column,
        "value": str(value),
    }


def _proposal(project: Project, text: str, cited: list[dict[str, object]], **kw: object):  # type: ignore[no-untyped-def]
    action, _ = make_action(project, "01_filter", proposed={"min_value": 5})
    record = {"text": text, "cited": cited, "considered": kw.get("considered", []), **kw}
    action = Action(**{**action.__dict__, "rationale": record, "proposed_by": "agent"})
    spec = registry.get("param.reason_unmatched")
    assert spec is not None and spec.version == 3
    return spec.fn(make_ctx(project, "01_filter", phase="pre", action=action))


def test_the_domain_sweep_reason_names_rows_by_their_key_and_is_not_flagged(
    project: Project, tmp_path: Path
) -> None:
    """The Lyons Lung proposal of 2026-11-06, in miniature: every flagged numeral was the key of
    a cited row (the domain count), or a considered value."""
    sweep = _sweep(tmp_path)
    cited = [
        _cite(sweep, "5", "coherence_gain", 0.023),
        _cite(sweep, "6", "coherence_gain", -0.0207),
        _cite(sweep, "6", "ari_to_previous", 0.9792),
        _cite(sweep, "4", "coherence_gain", 0.0613),
        _cite(sweep, "11", "max_single_replicate_share", 0.8191),
    ]
    text = (
        "Five is where the sweep stops paying. coherence_gain is 0.023 at 5 and -0.0207 at 6, "
        "and ari_to_previous is 0.9792 at 6. 4 is the cleaner cut on its own numbers "
        "(coherence_gain 0.0613); max_single_replicate_share is 0.8191 at 11. 9 was weighed too."
    )
    v = _proposal(project, text, cited, considered=[4, 5, 6, 7, 9])
    assert v.fired is False, v.reason
    # a measurement that no cited cell carries still fires, with the nearest class named
    v = _proposal(project, text + " boundary_share is 0.088 at 4.", cited, considered=[4, 5])
    assert v.fired is True
    assert v.reason is not None and v.reason.startswith(
        "a numeral in the reason matches no cited cell: 0.088 (nearest: "
    )
    assert "0.088" in v.evidence["numerals"] and "4" not in v.evidence["numerals"]
    assert {"numeral": "11", "class": "key"} in v.evidence["not_checked"]
    # a row of the cited table that was not itself cited is a label too (the `table` class)
    v = _proposal(project, "At 7 the maps split the parenchyma; 0.023 at 5.", cited[:1])
    assert v.fired is False, v.reason
    assert v.reason is None


def test_a_reason_with_a_measurement_and_no_citation_still_fires(project: Project) -> None:
    v = _proposal(project, "A floor of 5; 3 groups.", [])
    assert v.fired is True
    assert v.reason == "the reason carries numerals (3) and cites nothing"
    assert v.evidence["not_checked"] == [{"numeral": "5", "class": "param"}]


def test_a_call_may_name_the_question_s_cluster_and_animal_without_a_citation(
    questions: Project,  # noqa: F811
) -> None:
    """The Lyons Lung call of 2026-11-09: `cluster 6 in animal 6-2` in the reason, nothing cited,
    opened `param.reason_unmatched` (6, 6, 2). The question's numerals and an identifier are
    names; a number from nowhere still opens the hold. An agent-chosen value opens
    `param.agent_proposed` either way, so the holds are told apart by kind."""
    from stringency.review import queue

    q = questions
    asked = json.loads(
        cli(q, "ask", "Is group A above B for cluster 6 in animal 6-2?", "--json").output
    )
    qid = asked["question_id"]

    def holds_after(reason: str) -> dict[str, str]:
        before = {h["hold_id"] for h in queue(q)}
        r = cli(
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
        assert r.exit_code == 10, r.output + str(r.stderr)
        return {
            h["reason"].split(":")[0]: h["reason"] for h in queue(q) if h["hold_id"] not in before
        }

    by = holds_after("the person asked about cluster 6 in animal 6-2")
    assert sorted(by) == ["param.agent_proposed"], by
    by = holds_after("cluster 6 in animal 6-2, over 3 groups")
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
