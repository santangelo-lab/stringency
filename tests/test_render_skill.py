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
    data.pop("tools", None)  # the example's tool is its own pipeline's module
    data.pop("open", None)
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


# -- open mode (O1, 2026-10-16): the pinned sentences in one place, the tools and paths checked --


def _pinned(text: str, section_heading: str) -> dict[str, str]:
    """The `- key: "sentence"` list under a heading, key to sentence."""
    start = text.index(section_heading)
    block = text[start:]
    nxt = re.search(r"\n## ", block[len(section_heading) :])
    if nxt:
        block = block[: len(section_heading) + nxt.start()]
    out: dict[str, str] = {}
    for m in re.finditer(r'^- ([^:\n]+?): "(.+)"$', block, re.M):
        out[m.group(1).strip()] = m.group(2)
    return out


def test_pinned_open_mode_sentences_identical_in_skill_template_and_engine():
    from stringency import provenance
    from stringency.echo import OPEN_SWITCH

    operator = _pinned(OPERATOR.read_text(), "### 10.7 The pinned sentences")
    rendered = _pinned(_render_toy_with_tools(), "The pinned sentences, said as written")
    assert len(operator) == 16, sorted(operator)
    assert operator == rendered
    assert operator["switch"] == OPEN_SWITCH
    assert operator["label, trusted"] == provenance.LABEL_SENTENCES["trusted"]
    assert operator["label, untested"] == provenance.LABEL_SENTENCES["untested"]
    assert operator["label, untested tool"] == provenance.LABEL_SENTENCES["untested, tool"]
    assert operator["qualifier"] == provenance.QUALIFIER_LINE


def _toy_tools() -> dict:
    return {
        "tools": [
            {
                "module": "compare-groups",
                "title": "Compare the groups",
                "use_when": "the person asks which group is higher or how two groups differ",
                "asks": {
                    "replicate_unit": "Should the comparison treat each unit, or each row, as one replicate?",
                    "correction": "Which multiple-testing correction do you want: bh, bonferroni, or none?",
                },
            },
            {
                "module": "plot-groups",
                "title": "Draw the differences",
                "use_when": "the person wants to see the differences between groups as a figure",
            },
        ],
        "open": {
            "intro": "The toy method answers questions of the comparison table and the filtered table.",
            "paths": [
                {
                    "answers": "which groups differ and by how much",
                    "tool": "compare-groups",
                    "needs": ["object"],
                },
                {
                    "answers": "a picture of the differences",
                    "tool": "plot-groups",
                    "needs": ["comparison_table"],
                },
                {"answers": "anything else about the rows", "code": True},
            ],
        },
    }


def _render_toy_with_tools() -> str:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        repo = _toy_repo(Path(d))
        data = {**_toy_analyze(), **_toy_tools()}
        src = repo / "skills" / "toy-engine.analyze.yml"
        src.write_text(yaml.safe_dump(data))
        ctx, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
        assert not problems, problems
        return rs.render(ctx)


def test_tools_render_with_their_words_and_paths():
    out = _render_toy_with_tools()
    assert "## 8. After delivery: questions" in out
    assert (
        "- Compare the groups (`compare-groups`): use when the person asks which group is higher"
        in out
    )
    assert "Ask before calling it: Which multiple-testing correction do you want" in out
    assert "--set correction=<value> --asked-by person" in out
    assert (
        "- which groups differ and by how much: Compare the groups (`compare-groups`), a tool, labelled trusted; needs object delivered."
        in out
    )
    assert (
        "- anything else about the rows: no tool ships for this, so code, labelled untested." in out
    )
    assert "The toy method answers questions of the comparison table" in out
    # without tools the section says open mode is not offered
    data = yaml.safe_load(EXAMPLE.read_text())
    data.pop("tools"), data.pop("open")
    ctx, problems = rs.validate(data, EXAMPLE, None)
    assert not problems, problems
    assert "ships no tools for questions" in _norm(rs.render(ctx))


def test_nine_body_rules_unchanged_with_open_mode():
    assert len(_body_rules()) == 9
    assert all(r in _norm(_render_toy_with_tools()) for r in _body_rules())


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (lambda t: t["tools"][0].pop("use_when"), "`use_when` must say"),
        (
            lambda t: t["tools"][0]["asks"].pop("correction"),
            "decision point `correction` of `compare-groups` is settled by nobody",
        ),
        (lambda t: t["tools"][0]["asks"].update({"nope": "?"}), "has no parameter `nope`"),
        (
            lambda t: t["tools"].append(
                {"module": "filter-rows", "title": "x", "use_when": "y", "asks": {"min_value": "?"}}
            ),
            "does not list `open`",
        ),
        (
            lambda t: t["tools"].append({"module": "ghost", "title": "x", "use_when": "y"}),
            "not a module of this method",
        ),
        (
            lambda t: t["open"]["paths"][0].update({"needs": ["nothing"]}),
            "needs `nothing`, which no step",
        ),
        (
            lambda t: t["open"]["paths"][0].update({"code": True}),
            "names a tool or says code, not both",
        ),
        (
            lambda t: t["open"]["paths"].append({"answers": "x", "tool": "ghost"}),
            "tool `ghost` is not in `tools`",
        ),
        (
            lambda t: t["open"]["paths"].append({"answers": "x"}),
            "names a listed tool or says `code: true`",
        ),
    ],
)
def test_check_catches_tool_and_path_drift(tmp_path, change, fragment):
    repo = _toy_repo(tmp_path)
    data = {**_toy_analyze(), **_toy_tools()}
    change(data)
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(data))
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert any(fragment in p for p in problems), problems


def test_questions_file_shape_is_checked(tmp_path):
    repo = _toy_repo(tmp_path)
    data = {**_toy_analyze(), **_toy_tools()}
    src = repo / "skills" / "toy-engine.analyze.yml"
    src.write_text(yaml.safe_dump(data))
    qf = repo / "skills" / "toy-engine.questions.yml"
    qf.write_text(
        yaml.safe_dump(
            {
                "questions": 1,
                "skill": "stringency-analyze-toy-compare",
                "positive": [
                    {"text": "Which group is higher?", "expect": "tool:compare-groups"},
                    {"text": "How many rows per group?", "expect": "exec"},
                ],
                "negative": [
                    {"text": "Is this a good result?", "expect": "cannot"},
                    {"text": "Rerun with bonferroni", "expect": "fork"},
                ],
            }
        )
    )
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert not problems, problems
    qf.write_text(
        yaml.safe_dump(
            {
                "questions": 1,
                "positive": [{"text": "x", "expect": "tool:ghost"}],
                "negative": [{"text": "y", "expect": "guess"}],
            }
        )
    )
    _, problems = rs.validate(yaml.safe_load(src.read_text()), src, repo)
    assert any("expects tool `ghost`" in p for p in problems) and any(
        "`expect` must be" in p for p in problems
    )
