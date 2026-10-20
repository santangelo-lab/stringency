"""`--set k=v` coercion (backlog L47, L39): lists as `[a,b]`, string enums as spelled."""

from __future__ import annotations

from stringency.actions import coerce_value
from stringency.cli.verb_propose import parse_sets


def test_without_a_schema_the_old_rules_hold_and_brackets_make_a_list() -> None:
    assert coerce_value("3") == 3 and coerce_value("2.5") == 2.5
    assert coerce_value("true") is True and coerce_value("none") is None
    assert coerce_value("[a, b,c]") == ["a", "b", "c"]
    assert coerce_value("[1,2]") == [1, 2]


def test_an_array_schema_takes_both_forms_and_coerces_items() -> None:
    arr = {"type": "array", "items": {"type": "string", "enum": ["propeller", "edger_ql"]}}
    assert coerce_value("[propeller,edger_ql]", arr) == ["propeller", "edger_ql"]
    assert coerce_value("propeller, edger_ql", arr) == ["propeller", "edger_ql"]
    assert coerce_value("[1,2]", {"type": "array", "items": {"type": "integer"}}) == [1, 2]


def test_a_string_schema_keeps_none_as_the_word() -> None:
    enum = {"type": "string", "enum": ["bh", "bonferroni", "none"]}
    assert coerce_value("none", enum) == "none"
    assert coerce_value("null", {"type": "string"}) == "null"
    assert coerce_value("none") is None  # no schema: the old reading


def test_parse_sets_uses_the_properties_it_is_given() -> None:
    props = {
        "correction": {"type": "string", "enum": ["bh", "none"]},
        "tests": {"type": "array", "items": {"type": "string"}},
        "n": {"type": "integer"},
    }
    got = parse_sets(["correction=none", "tests=[a,b]", "n=4", "04_compare.other=x"], props)
    assert got == {"correction": "none", "tests": ["a", "b"], "n": 4, "other": "x"}
    assert parse_sets(["correction=none"]) == {"correction": None}
