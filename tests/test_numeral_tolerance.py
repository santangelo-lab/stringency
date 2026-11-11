"""L145 (found by the answers package, 2026-10-30): `numeral_matches` compared with an absolute
tolerance of 1e-12, so `1.33e-75` in an answer matched a cited cell of 4.44e-76, any two small
p values matched each other, and `ans.numeral_unmatched` passed a wrong p. The rule is the
value rounded to the precision written, with no absolute tolerance, and it is one rule for the
gate, the chat block and the provenance lookup."""

from __future__ import annotations

import pytest

from stringency.predicates.engine.ans import classify_numerals
from stringency.predicates.engine.judg import numeral_matches
from stringency.present import _said
from stringency.provenance import _matches_any


@pytest.mark.parametrize(
    "written,value,want",
    [
        ("1.33e-75", 4.44e-76, False),  # the case that was found
        ("1.33e-75", 1.3349e-75, True),
        ("1.33e-75", 1.336e-75, False),
        ("4e-76", 4.44e-76, True),  # one digit written, one digit checked
        ("4.4e-76", 4.44e-76, True),
        ("2e-13", 9e-13, False),  # both under the old absolute tolerance
        ("1E-5", 1.04e-5, True),
        ("1.2e3", 1204.0, True),
        ("1.2e3", 1260.0, False),
        ("0.0000000000002", 9e-13, False),  # decimal form of a tiny value
        ("0.000", 4e-13, True),  # three decimals of zero is what it rounds to
        ("0.05", 0.0499999999, True),
        ("0.05", 0.044, False),
        ("12", 12.0000000000001, True),
        ("0.1", 0.1, True),
        ("7", "7", True),
        ("7", "seven", False),
    ],
)
def test_a_numeral_matches_a_value_rounded_to_the_precision_written(
    written: str, value: object, want: bool
) -> None:
    assert numeral_matches(written, value) is want
    assert _said(written, value) is want  # the chat block marks the same cells


def test_a_wrong_small_p_fails_the_answer_s_numeral_check() -> None:
    cells = [4.44e-76, 2.1e-30, 0.031]
    got = classify_numerals("The adjusted p is 1.33e-75 for the first gene.", cells, {})
    assert [f["numeral"] for f in got["failed"]] == ["1.33e-75"] and not got["matched"]
    got = classify_numerals("The adjusted p is 4.44e-76, and 2.1e-30 for the next.", cells, {})
    assert [m["numeral"] for m in got["matched"]] == ["4.44e-76", "2.1e-30"]
    assert not got["failed"]


def test_the_provenance_lookup_finds_what_the_rule_matches_and_no_more() -> None:
    values = sorted([4.44e-76, 1.3349e-75, 9e-13, 0.031, 1204.0])
    assert _matches_any("1.33e-75", values) is True  # 1.3349e-75 rounds to it
    assert _matches_any("1.33e-75", [4.44e-76, 9e-13]) is False
    assert _matches_any("2e-13", values) is False
    assert _matches_any("1.2e3", values) is True
