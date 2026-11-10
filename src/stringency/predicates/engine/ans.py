"""`ans.*`: the operator's answer text against what it cites (open_mode_plan.md 2.5,
2026-10-16). Invariant: the exploratory profile's remap cannot soften the one promise open
mode makes, that every number in an answer is a cell the person can see.

`ans.numeral_unmatched@2` (L142, 2026-10-29) left unchecked a numeral that is not a
measurement: a level of a design factor, a key value of a cited table, a parameter value of the
step that produced a cited artifact, a numeral of the question itself, a year, or a count of
one or two digits before a unit word no table carries. The answer's qualifier line lists them
(`numerals not checked`), so a reader sees what was not checked.

Version 3 (L157, 2026-11-10; the owner's choice over the value rule drafted on 2026-11-09): a
name is marked, a measurement is bare. A numeral inside backticks is a name: it must be the key
of a cited row, a level of a design factor, a parameter value, a value the proposal considered
or a numeral of the question, and is then left unchecked and listed. A bare numeral is a
measurement and must match a cited cell; the classes of version 2 no longer excuse it, since a
value that happens to equal a row's key (`the gain at 6 is 5`, where a row 5 exists) says
nothing about what the numeral means in the sentence. Three things need no mark, because the
text alone shows what they are: part of a hyphenated identifier (`6-2`, `24-1-Lung-A`,
`ctrl-1`), a year, and a count before a unit word. `classify_numerals` is shared with
`param.reason_unmatched@3`, so a proposal's reason is read by the same rules as an answer. A
story (`deliver --story`) is a person's own paragraph and is still read by version 2's rule
(`names_anywhere`)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.engine.judg import NUMERAL, numeral_matches
from stringency.predicates.registry import predicate

LABEL_WORDS = re.compile(r"\b(trusted|untested)\b", re.IGNORECASE)

# The classes a numeral that is not a measurement falls in, with the words the reason and the
# qualifier use.
EXEMPT_CLASSES: dict[str, str] = {
    "level": "a level of a design factor",
    "key": "a key value of a cited table",
    "param": "a parameter value of the cited step",
    "considered": "a value the proposal considered",
    "question": "a numeral in the question",
    "year": "a year",
    "count": "a count before a unit word",
    "id": "part of an identifier",
}
# What a name may name, in the order tried; `year`, `count` and `id` read the text alone.
NAME_CLASSES = ("level", "key", "param", "considered", "question")
NAME_WORDS = (
    "a cited row, a design level, a parameter value, a considered value or a numeral of the "
    "question"
)
# A name: a span in backticks on one line.
MARK = re.compile(r"`([^`\n]+)`")
# Unit words no method table counts (DECISIONS 2026-10-29, L142): `cells` is not one, since
# cells are counted in tables. Kept short on purpose.
UNIT_WORDS = ("animals", "animal", "punches", "punch", "replicates", "replicate")
_UNIT_AFTER = re.compile(r"\s+(" + "|".join(UNIT_WORDS) + r")\b", re.IGNORECASE)
_WORD_AFTER = re.compile(r"\s+([A-Za-z]+)")
_YEAR = re.compile(r"[0-9]{4}")
_COUNT = re.compile(r"[0-9]{1,2}")
_IDENT_CHAR = re.compile(r"[A-Za-z0-9_]")
# The digits of a name the numeral reader does not see because a letter touches them
# (`Donor3`, `cluster_6`, `24h`): a marked `3` may name the row `Donor3`.
_DIGITS = re.compile(r"(?<![\d.])\d+(?:\.\d+)?")


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


def _same(written: str, value: str) -> bool:
    try:
        return float(written) == float(value)
    except ValueError:
        return written == value


def _numerals_of(values: Iterable[Any]) -> list[str]:
    """Every numeral written in the values as text; a comma list gives each of its numbers,
    and a name with digits against a letter (`Donor3`, `24h`) gives those digits too."""
    out: list[str] = []
    for v in values:
        text = str(v)
        strict = NUMERAL.findall(text)
        out += strict
        out += [d for d in _DIGITS.findall(text) if not any(_same(d, s) for s in strict)]
    return out


def numeral_sources(design: Any, observed: Mapping[str, Any]) -> dict[str, list[str]]:
    """The numerals each name class admits: the design's factor levels, and what the resolver
    put in `observed.numeral_sources` (the cited rows' key values, the parameter values, the
    values a proposal considered, the question's text)."""
    src = dict(observed.get("numeral_sources") or {})
    factors = getattr(design, "factors", {}) or {}
    levels = [lv for f in factors.values() for lv in getattr(f, "levels", [])]
    return {
        "level": _numerals_of(levels),
        "key": _numerals_of(src.get("key", [])),
        "param": _numerals_of(src.get("param", [])),
        "considered": _numerals_of(src.get("considered", [])),
        "question": _numerals_of([src.get("question", "")]),
    }


def in_identifier(text: str, start: int, end: int) -> bool:
    """Whether the numeral at `text[start:end]` is part of a hyphenated identifier: joined by
    `-` to a word character on either side (`6-2`, `24-1-Lung-A`, `ctrl-1`, `k-5`). A negative
    number after a space or an operator (`-0.64`, `x = -2`) is not; nor is a range written
    with spaces."""
    before = text[start - 2 : start] if start >= 2 else ""
    after = text[end : end + 2]
    return bool(
        (len(before) == 2 and before[1] == "-" and _IDENT_CHAR.match(before[0]))
        or (len(after) == 2 and after[0] == "-" and _IDENT_CHAR.match(after[1]))
    )


def _named(num: str, sources: Mapping[str, list[str]]) -> str | None:
    """The first name class that holds the numeral, or None."""
    for cls in NAME_CLASSES:
        if any(_same(num, v) for v in sources.get(cls, [])):
            return cls
    return None


def _by_the_text(num: str, text: str, end: int) -> str | None:
    """The class the text alone gives a numeral: a year, or a count before a unit word."""
    if _YEAR.fullmatch(num) and 1900 <= int(num) <= 2100:
        return "year"
    if _COUNT.fullmatch(num) and _UNIT_AFTER.match(text, end):
        return "count"
    return None


def _closest_name(num: str, sources: Mapping[str, list[str]]) -> tuple[str, str] | None:
    """(class, value) of the name numerically closest to the numeral, or None."""
    try:
        fw = float(num)
    except ValueError:
        return None
    best: tuple[float, str, str] | None = None
    for cls in NAME_CLASSES:
        for v in sources.get(cls, []):
            try:
                d = abs(float(v) - fw)
            except ValueError:
                continue
            if best is None or d < best[0]:
                best = (d, cls, v)
    return (best[1], best[2]) if best is not None else None


def _nearest(num: str, text: str, end: int, sources: Mapping[str, list[str]]) -> str:
    """What a bare numeral that matches no cited cell came nearest to, in words: the year class
    for four digits, else the class holding the numerically closest name; a count of one or two
    digits before a word adds that the word is not one of the unit words."""
    if _YEAR.fullmatch(num):
        return f"{EXEMPT_CLASSES['year']} (1900 to 2100)"
    best = _closest_name(num, sources)
    words = (
        f"{EXEMPT_CLASSES[best[0]]} ({best[1]})"
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
    text: str,
    cells: list[Any],
    sources: Mapping[str, list[str]],
    *,
    names_anywhere: bool = False,
) -> dict[str, list[dict[str, str]]]:
    """Each numeral of `text`, in the order written: `matched` (a cited cell, rounded to the
    written precision), `exempt` (not a measurement; left unchecked and listed with its
    class), or `failed` (neither, with `nearest` saying why in words).

    A numeral inside backticks is a name. It is exempt when a name class holds it (a cited
    row's key, a design level, a parameter value, a considered value, a numeral of the
    question); failing that it may still be a cited cell, an identifier, a year or a count, so
    a mark never costs a numeral a way to pass. A bare numeral is a measurement: a cited cell,
    else an identifier, a year or a count by the text alone, else it fails. When a bare
    numeral that fails is one a name class holds, the failure carries `unmarked` (the class):
    it would pass in backticks, and `nearest` says so.

    `names_anywhere` reads the text by version 2's rule, where a name class excuses a numeral
    with or without a mark: for a person's own paragraph (`deliver --story`), which is not
    asked to follow the operator's convention."""
    out: dict[str, list[dict[str, str]]] = {"matched": [], "exempt": [], "failed": []}
    spans = [m.span() for m in MARK.finditer(text)]
    for m in NUMERAL.finditer(text):
        num = m.group(0)
        marked = any(a < m.start() < b for a, b in spans)
        name = _named(num, sources)
        if marked and name is not None:
            out["exempt"].append({"numeral": num, "class": name})
            continue
        if any(numeral_matches(num, v) for v in cells):
            out["matched"].append({"numeral": num})
            continue
        if in_identifier(text, m.start(), m.end()):
            out["exempt"].append({"numeral": num, "class": "id"})
            continue
        if names_anywhere and name is not None:
            out["exempt"].append({"numeral": num, "class": name})
            continue
        # a unit word follows a marked count after its closing backtick
        after = m.end() + 1 if marked and text[m.end() : m.end() + 1] == "`" else m.end()
        cls = _by_the_text(num, text, after)
        if cls is not None:
            out["exempt"].append({"numeral": num, "class": cls})
            continue
        if marked:
            closest = _closest_name(num, sources)
            out["failed"].append(
                {
                    "numeral": num,
                    "nearest": f"in backticks it must name {NAME_WORDS}, and none is {num}"
                    + (
                        f"; the closest is {EXEMPT_CLASSES[closest[0]]} ({closest[1]})"
                        if closest is not None
                        else ""
                    ),
                    "marked": "yes",
                }
            )
        elif name is not None:
            out["failed"].append(
                {
                    "numeral": num,
                    "nearest": f"it equals {EXEMPT_CLASSES[name]}; if it is that name, write "
                    f"it in backticks (`{num}`); if it is a measurement, cite its cell",
                    "unmarked": name,
                }
            )
        else:
            out["failed"].append({"numeral": num, "nearest": _nearest(num, text, m.end(), sources)})
    return out


def unmarked_names(failed: list[dict[str, str]]) -> list[dict[str, str]]:
    """The failures when every one of them is a name written bare (it would pass in
    backticks), else []: the case where the text's form is wrong and nothing else is."""
    return failed if failed and all(f.get("unmarked") for f in failed) else []


@predicate(
    id="ans.numeral_unmatched",
    version=3,
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
    reason names each numeral that still fails with the nearest exemption class considered.
    Version 3 (L157): a name is exempt only in backticks, where it must name a cited row, a
    design level, a parameter value or a numeral of the question; a hyphenated identifier, a
    year and a count before a unit word need no mark. The reason says of each failing numeral
    whether it is a name to put in backticks or a measurement to cite."""
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
