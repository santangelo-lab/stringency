"""`ans.*`: the operator's answer text against what it cites (open_mode_plan.md 2.5,
2026-10-16). Invariant: the exploratory profile's remap cannot soften the one promise open
mode makes, that every number in an answer is a cell the person can see.

`ans.numeral_unmatched@2` (L142, 2026-10-29) leaves unchecked a numeral that is not a
measurement: a level of a design factor, a key value of a cited table, a parameter value of the
step that produced a cited artifact, a numeral of the question itself, a year, or a count of
one or two digits before a unit word no table carries. The answer's qualifier line lists them
(`numerals not checked`), so a reader sees what was not checked."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.engine.judg import NUMERAL, numeral_matches
from stringency.predicates.registry import predicate

LABEL_WORDS = re.compile(r"\b(trusted|untested)\b", re.IGNORECASE)

# The exemption classes of `ans.numeral_unmatched@2`, in the order a numeral is tried against
# them, with the words the reason and the qualifier use.
EXEMPT_CLASSES: dict[str, str] = {
    "level": "a level of a design factor",
    "key": "a key value of a cited table",
    "param": "a parameter value of the cited step",
    "question": "a numeral in the question",
    "year": "a year",
    "count": "a count before a unit word",
}
# Unit words no method table counts (DECISIONS 2026-10-29, L142): `cells` is not one, since
# cells are counted in tables. Kept short on purpose.
UNIT_WORDS = ("animals", "animal", "punches", "punch", "replicates", "replicate")
_UNIT_AFTER = re.compile(r"\s+(" + "|".join(UNIT_WORDS) + r")\b", re.IGNORECASE)
_WORD_AFTER = re.compile(r"\s+([A-Za-z]+)")
_YEAR = re.compile(r"[0-9]{4}")
_COUNT = re.compile(r"[0-9]{1,2}")


@predicate(
    id="ans.cited_missing",
    version=1,
    scope=["answer"],
    phase="post",
    default=Disposition.BLOCK,
    invariant=True,
)
def cited_missing(ctx: GateContext) -> Verdict:
    """A cited artifact or cell does not exist, is rejected or superseded, or belongs to a
    step that did not complete (the resolver lists them in `observed.missing`). The reason says
    the key form each missed table expects and its keys nearest the miss (`observed.cite_help`,
    L138)."""
    if ctx.output is None:
        return Verdict(False)
    missing = list(ctx.output.observed.get("missing", []))
    if missing:
        helps = [h for h in ctx.output.observed.get("cite_help", []) if isinstance(h, dict)]
        reason = "a citation resolves to nothing"
        if helps:
            reason += "; " + "; ".join(
                f"{h['cite']}: rows of {h['table']} are cited as {h['form']}"
                + (f", nearest {', '.join(h['near'])}" if h.get("near") else "")
                for h in helps
            )
        return Verdict(True, reason, {"missing": missing, "cite_help": helps})
    return Verdict(False)


def _numerals_of(values: Iterable[Any]) -> list[str]:
    """Every numeral written in the values as text; a comma list gives each of its numbers."""
    return [n for v in values for n in NUMERAL.findall(str(v))]


def numeral_sources(design: Any, observed: Mapping[str, Any]) -> dict[str, list[str]]:
    """The numerals each exemption class admits: the design's factor levels, and what the
    answer's resolver put in `observed.numeral_sources` (the cited rows' key values, the
    producing steps' parameter values, the question's text)."""
    src = dict(observed.get("numeral_sources") or {})
    factors = getattr(design, "factors", {}) or {}
    levels = [lv for f in factors.values() for lv in getattr(f, "levels", [])]
    return {
        "level": _numerals_of(levels),
        "key": _numerals_of(src.get("key", [])),
        "param": _numerals_of(src.get("param", [])),
        "question": _numerals_of([src.get("question", "")]),
    }


def _same(written: str, value: str) -> bool:
    try:
        return float(written) == float(value)
    except ValueError:
        return written == value


def _exempt(num: str, text: str, end: int, sources: Mapping[str, list[str]]) -> str | None:
    for cls in ("level", "key", "param", "question"):
        if any(_same(num, v) for v in sources.get(cls, [])):
            return cls
    if _YEAR.fullmatch(num) and 1900 <= int(num) <= 2100:
        return "year"
    if _COUNT.fullmatch(num) and _UNIT_AFTER.match(text, end):
        return "count"
    return None


def _nearest(num: str, text: str, end: int, sources: Mapping[str, list[str]]) -> str:
    """The exemption class a failing numeral came nearest to, in words: the year class for four
    digits, else the class holding the numerically closest value; a count of one or two digits
    before a word adds that the word is not one of the unit words."""
    if _YEAR.fullmatch(num):
        return f"{EXEMPT_CLASSES['year']} (1900 to 2100)"
    best: tuple[float, str, str] | None = None
    fw = float(num)
    for cls in ("level", "key", "param", "question"):
        for v in sources.get(cls, []):
            try:
                d = abs(float(v) - fw)
            except ValueError:
                continue
            if best is None or d < best[0]:
                best = (d, cls, v)
    words = (
        f"{EXEMPT_CLASSES[best[1]]} ({best[2]})"
        if best is not None
        else "none: no design level, key value, parameter or question numeral to compare"
    )
    word = _WORD_AFTER.match(text, end)
    if _COUNT.fullmatch(num) and word:
        words += (
            f"; {word.group(1)} is not a unit word of {EXEMPT_CLASSES['count']} "
            f"({', '.join(UNIT_WORDS[::2])})"
        )
    return words


def classify_numerals(
    text: str, cells: list[Any], sources: Mapping[str, list[str]]
) -> dict[str, list[dict[str, str]]]:
    """Each numeral of `text`: `matched` (a cited cell, rounded to the written precision),
    `exempt` (no cell, but one of the exemption classes; not checked), or `failed` (neither,
    with the nearest class considered). Shared by the predicate and the answer's qualifier."""
    out: dict[str, list[dict[str, str]]] = {"matched": [], "exempt": [], "failed": []}
    for m in NUMERAL.finditer(text):
        num = m.group(0)
        if any(numeral_matches(num, v) for v in cells):
            out["matched"].append({"numeral": num})
            continue
        cls = _exempt(num, text, m.end(), sources)
        if cls is not None:
            out["exempt"].append({"numeral": num, "class": cls})
        else:
            out["failed"].append({"numeral": num, "nearest": _nearest(num, text, m.end(), sources)})
    return out


@predicate(
    id="ans.numeral_unmatched",
    version=2,
    scope=["answer"],
    phase="post",
    default=Disposition.BLOCK,
    invariant=True,
)
def numeral_unmatched(ctx: GateContext) -> Verdict:
    """Every numeral in the text matches a cited cell, rounded to the written precision (the
    same rule as report prose and rationales); the denominator is the cited cells, not every
    cell of every table, because any numeral matches something in a ten-thousand-row table.
    Version 2 (L142): a numeral that is not a measurement is exempt (`classify_numerals`); the
    reason names each numeral that still fails with the nearest exemption class considered."""
    if ctx.output is None or not ctx.output.prose:
        return Verdict(False)
    cells = [
        v
        for t in ctx.output.evidence_tables.values()
        for row in t.rows.values()
        for v in row.values()
    ]
    sources = numeral_sources(ctx.design, ctx.output.observed)
    got = classify_numerals(ctx.output.prose, cells, sources)
    if got["failed"]:
        return Verdict(
            True,
            "a numeral in the answer matches no cited cell: "
            + ", ".join(f"{p['numeral']} (nearest: {p['nearest']})" for p in got["failed"]),
            {
                "problems": [{"answer": True, **p} for p in got["failed"]],
                "not_checked": got["exempt"],
                "cited_cells": len(cells),
            },
        )
    return Verdict(False)


@predicate(
    id="ans.label_authored",
    version=1,
    scope=["answer"],
    phase="post",
    default=Disposition.BLOCK,
    invariant=True,
)
def label_authored(ctx: GateContext) -> Verdict:
    """The text contains the word trusted or untested: the operator may not write the mark;
    the engine prints it from what ran."""
    if ctx.output is None or not ctx.output.prose:
        return Verdict(False)
    found = sorted({m.group(1).lower() for m in LABEL_WORDS.finditer(ctx.output.prose)})
    if found:
        return Verdict(
            True,
            "the answer writes the label itself: " + ", ".join(found),
            {"words": found},
        )
    return Verdict(False)
