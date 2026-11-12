"""L175 (the owner, 2026-10-27: the operator must reach the citation of anything borrowed from a
paper): a method names a tool's sources with `cites:` on its analyze-file entry; `tools list`,
`present --answer` and the open report's `methods.md` carry them."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from stringency.project import Project
from tests.test_open_answers import _answer, _ask_and_compare, questions  # noqa: F401
from tests.test_run import cli

BH = "Benjamini and Hochberg 1995, J R Stat Soc B 57:289"


def _cite_compare_groups(q: Project) -> None:
    skills = q.method_root / "skills"
    skills.mkdir(exist_ok=True)
    (skills / "toy-engine.analyze.yml").write_text(
        yaml.safe_dump(
            {
                "tools": [
                    {
                        "module": "compare-groups",
                        "title": "Compare the groups",
                        "use_when": "the person asks which group is higher",
                        "cites": [BH],
                    }
                ]
            }
        )
    )


def test_a_tools_sources_reach_tools_list_the_answer_and_methods(
    questions: Project,  # noqa: F811
    tmp_path: Path,
) -> None:
    q = questions
    qid, aid, run_id = _ask_and_compare(q)
    _cite_compare_groups(q)
    out = json.loads(cli(q, "tools", "list", "--json").output)
    tool = next(t for t in out["tools"] if t["ref"].startswith("compare-groups@"))
    assert tool["words"]["cites"] == [BH]
    assert f"  sources: {BH}" in cli(q, "tools", "list").output
    r = _answer(
        q,
        qid,
        "A is higher than B: the difference is 59.22 (adjusted p 1.33e-75).",
        f"{aid}:A_vs_B",
        path=tmp_path / "a.md",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    answer_id = json.loads(r.output)["answer_id"]
    shown = json.loads(cli(q, "present", "--answer", answer_id, "--json").output)
    assert shown["sources"] == [{"tool": "compare-groups@0.1.1", "cites": [BH]}]
    line = f"Sources the method names for compare-groups@0.1.1: {BH}."
    assert line in cli(q, "present", "--answer", answer_id).output
    assert line in cli(q, "present", "--answer", answer_id, "--chat").output
    methods = (q.root / "deliver" / run_id / "methods.md").read_text()
    assert f"The method names the sources of compare-groups@0.1.1: {BH}." in methods


def test_no_sources_no_line(
    questions: Project,  # noqa: F811
    tmp_path: Path,
) -> None:
    q = questions
    qid, aid, run_id = _ask_and_compare(q)
    r = _answer(
        q,
        qid,
        "A is higher than B: the difference is 59.22 (adjusted p 1.33e-75).",
        f"{aid}:A_vs_B",
        path=tmp_path / "a.md",
    )
    answer_id = json.loads(r.output)["answer_id"]
    shown = json.loads(cli(q, "present", "--answer", answer_id, "--json").output)
    assert shown["sources"] == []
    assert "Sources the method names" not in cli(q, "present", "--answer", answer_id).output
    assert "names the sources" not in (q.root / "deliver" / run_id / "methods.md").read_text()
