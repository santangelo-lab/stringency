"""The analysis-skill renderer (Track 1d): the example renders; the nine body rules of
`spec/plans/ux-two-audiences.md` section 4 and the hold protocol of the operator skill's section 6
appear in the rendered skill verbatim; `--check` catches the drift it is meant to catch."""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CS = ROOT / "integrations" / "claude-science"
EXAMPLE = ROOT / "templates" / "method-repo" / "skills" / "example.analyze.yml"
UX_NOTE = ROOT / "spec" / "plans" / "ux-two-audiences.md"
OPERATOR = CS / "stringency-operator" / "SKILL.md"
TOY_METHOD = ROOT / "plugins" / "stringency-toy" / "method"


def _load_module():
    spec = importlib.util.spec_from_file_location("render_skill", CS / "render_skill.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


rs = _load_module()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _render_example() -> str:
    data = yaml.safe_load(EXAMPLE.read_text())
    ctx, problems = rs.validate(data, EXAMPLE, None)
    assert not problems, problems
    return rs.render(ctx)


def _body_rules() -> list[str]:
    """The numbered list under 'Body rules' in UX note section 4, one string per rule."""
    text = UX_NOTE.read_text()
    start = text.index("Body rules, each testable against a transcript:")
    end = text.index("Test set:", start)
    block = text[start:end]
    items = re.split(r"\n(?=\d+\. )", block)[1:]
    rules = [_norm(re.sub(r"^\d+\. ", "", it)) for it in items]
    assert len(rules) == 9
    return rules


def _hold_protocol() -> str:
    """Section 6 of the operator skill up to the paragraph that starts 'The person may instead'."""
    text = OPERATOR.read_text()
    start = text.index("## 6. Holds")
    start = text.index("\n", start) + 1
    end = text.index("The person may instead", start)
    return _norm(text[start:end])


def test_example_renders_with_frontmatter():
    out = _render_example()
    assert out.startswith("---\nname: stringency-analyze-example\ndescription: ")
    assert "Load when the person wants to compare two groups" in out
    assert "Do not load for single-cell, spatial, or sequencing data" in out
    assert "# Run the example analysis on a table of measurements" in out
    for title in ("Read the table", "Compare the groups", "Write the report"):
        assert f"- {title}\n" in out
    assert "1. Which file holds the measurements" in out
    assert "min_n_per_group" in out
    assert "comparison_table: one row per pair of groups" in out


def test_nine_body_rules_verbatim():
    out = _norm(_render_example())
    for rule in _body_rules():
        assert rule in out, rule


def test_hold_protocol_verbatim_from_operator_skill():
    protocol = _hold_protocol()
    assert protocol.startswith("When the engine stops with a hold")
    assert protocol.endswith("never starts `review --serve`.")
    assert protocol in _norm(_render_example())


def _decision_text() -> str:
    """Section 9 of the operator skill, its first paragraph (the shared text)."""
    text = OPERATOR.read_text()
    start = text.index("## 9. Decision points")
    start = text.index("\n", start) + 1
    end = text.index("A method's analysis skill lists", start)
    return _norm(text[start:end])


def test_decision_point_text_verbatim_from_operator_skill():
    shared = _decision_text()
    assert shared.startswith("Some steps take a parameter nobody can set")
    assert shared.endswith("the two must not drift.")
    assert shared in _norm(_render_example())


def test_decisions_render_and_are_checked(tmp_path):
    repo = _toy_repo(tmp_path)
    data = _toy_analyze()
    data["decisions"] = [
        {
            "step": "01_filter",
            "param": "min_value",
            "how": "declared",
            "ask": "What is the smallest value to keep?",
        },
        {
            "step": "04_compare",
            "param": "correction",
            "how": "proposed",
            "ask": "Which correction should the comparison use?",
            "after": "02_summarize",
            "evidence": ["02_summarize.summary"],
        },
    ]
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(data))
    ctx, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert not problems, problems
    out = rs.render(ctx)
    assert (
        '- What is the smallest value to keep? (`01_filter.min_value`, the step "Filter low-value rows")'
        in out
    )
    assert (
        '- Which correction should the comparison use?: `04_compare.correction` (the step "Compare the groups"), proposed after "Summarize each group" from 02_summarize.summary.'
        in out
    )
    for bad, fragment in [
        ({"step": "09_nope", "param": "x", "how": "declared", "ask": "?"}, "step ids"),
        (
            {"step": "01_filter", "param": "max_value", "how": "declared", "ask": "?"},
            "neither a decision point",
        ),
        (
            {"step": "01_filter", "param": "min_value", "how": "guessed", "ask": "?"},
            "`how` must be",
        ),
        (
            {
                "step": "04_compare",
                "param": "correction",
                "how": "proposed",
                "ask": "?",
                "after": "05_report",
                "evidence": ["x"],
            },
            "must come before",
        ),
        (
            {
                "step": "04_compare",
                "param": "correction",
                "how": "proposed",
                "ask": "?",
                "after": "02_summarize",
            },
            "names the `evidence`",
        ),
        (
            {
                "step": "01_filter",
                "param": "min_value",
                "how": "declared",
                "ask": "?",
                "after": "02_summarize",
            },
            "takes no `after`",
        ),
    ]:
        data["decisions"] = [bad]
        src.write_text(yaml.safe_dump(data))
        _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
        assert any(fragment in p for p in problems), (bad, problems)


def test_operator_skill_named_as_authority():
    out = _render_example()
    assert "the operator skill is right" in out
    assert "on conflict it wins" in out


def _toy_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "method"
    shutil.copytree(TOY_METHOD, repo)
    (repo / "skills").mkdir()
    return repo


def _toy_analyze() -> dict:
    data = yaml.safe_load(EXAMPLE.read_text())
    data.pop("decisions", None)  # the example's decision names its own pipeline's step
    data.update(
        pipeline="toy-engine",
        name="toy-compare",
        plugin="stringency-toy",
        question="compare_groups",
        steps={
            "01_filter": "Filter low-value rows",
            "02_summarize": "Summarize each group",
            "03_label": "Label the groups",
            "04_compare": "Compare the groups",
            "05_report": "Write the report",
        },
        deliverables={"comparison_table": "the comparison", "group_labels": "the labels"},
    )
    return data


def test_check_against_toy_method_is_clean(tmp_path):
    repo = _toy_repo(tmp_path)
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(_toy_analyze()))
    (repo / "skills" / "toy-engine.yml").write_text(
        yaml.safe_dump(
            {
                "skill": 1,
                "pipeline": "toy-engine",
                "after_delivery": [
                    {"title": "Groups compared", "source": "x.tsv", "kind": "table"}
                ],
                "never_show": [],
                "hold_view": [],
            }
        )
    )
    ctx, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert not problems, problems
    assert ctx["skill_name"] == "stringency-analyze-toy-compare"
    assert ctx["after_delivery_titles"] == ["Groups compared"]
    assert "- Groups compared\n" in rs.render(ctx)


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"question": "process_rows"}, "not among the pipeline's answers"),
        ({"steps": {"01_filter": "Filter low-value rows"}}, "ids must be the pipeline's"),
        ({"deliverables": {"nothing": "x"}}, "no module of the pipeline produces"),
        ({"method": "no-tag"}, "must be `<url or path>@<tag>`"),
        ({"phrasings": {"positive": ["x"]}}, "phrasings.negative"),
        ({"extra": 1}, "unknown key `extra`"),
        ({"name": "Toy Compare"}, "lowercase letters"),
    ],
)
def test_check_catches_drift(tmp_path, change, fragment):
    repo = _toy_repo(tmp_path)
    data = _toy_analyze()
    data.update(change)
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(data))
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert any(fragment in p for p in problems), problems


def test_check_flags_title_drift(tmp_path):
    repo = _toy_repo(tmp_path)
    data = _toy_analyze()
    data["steps"]["03_label"] = "Label groups"
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(data))
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert any("steps.03_label: title must be the pipeline's" in p for p in problems), problems
