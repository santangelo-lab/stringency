"""`ans.*`: the operator's answer text against what it cites (open_mode_plan.md 2.5,
2026-10-16). Invariant: the exploratory profile's remap cannot soften the one promise open
mode makes, that every number in an answer is a cell the person can see."""

from __future__ import annotations

import re

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.engine.judg import _numeral_problems
from stringency.predicates.registry import predicate

LABEL_WORDS = re.compile(r"\b(trusted|untested)\b", re.IGNORECASE)


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
    step that did not complete (the resolver lists them in `observed.missing`)."""
    if ctx.output is None:
        return Verdict(False)
    missing = list(ctx.output.observed.get("missing", []))
    if missing:
        return Verdict(True, "a citation resolves to nothing", {"missing": missing})
    return Verdict(False)


@predicate(
    id="ans.numeral_unmatched",
    version=1,
    scope=["answer"],
    phase="post",
    default=Disposition.BLOCK,
    invariant=True,
)
def numeral_unmatched(ctx: GateContext) -> Verdict:
    """Every numeral in the text matches a cited cell, rounded to the written precision (the
    same rule as report prose and rationales); the denominator is the cited cells, not every
    cell of every table, because any numeral matches something in a ten-thousand-row table."""
    if ctx.output is None or not ctx.output.prose:
        return Verdict(False)
    cells = [
        v
        for t in ctx.output.evidence_tables.values()
        for row in t.rows.values()
        for v in row.values()
    ]
    problems = _numeral_problems(ctx.output.prose, cells, {"answer": True})
    if problems:
        return Verdict(
            True,
            "a numeral in the answer matches no cited cell: "
            + ", ".join(p["numeral"] for p in problems),
            {"problems": problems, "cited_cells": len(cells)},
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
