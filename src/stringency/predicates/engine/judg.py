"""`judg.*`: post-gate checks on judgment and report outputs (design 8)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate

NUMERAL = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w])")


def _valid_replicates(ctx: GateContext) -> list[tuple[int, Mapping[str, Any]]]:
    if ctx.output is None:
        return []
    return [
        (i, r)
        for i, (r, ok) in enumerate(
            zip(ctx.output.replicates, ctx.output.replicate_valid, strict=True), start=1
        )
        if ok
    ]


def _items(rep: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = rep.get("items", rep.get("judgments", []))
    return list(items) if isinstance(items, list) else []


def values_equal(a: Any, b: Any) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def numeral_matches(written: str, value: Any) -> bool:
    """`written` matches `value` after rounding the value to the precision written."""
    try:
        fv = float(value)
    except (TypeError, ValueError):
        return str(value) == written
    if "e" in written.lower():
        try:
            fw = float(written)
        except ValueError:
            return False
        return fw == fv or abs(fw - fv) <= abs(fv) * 1e-6 + 1e-12
    decimals = len(written.split(".", 1)[1]) if "." in written else 0
    try:
        fw = float(written)
    except ValueError:
        return False
    if abs(fw - fv) < 1e-12:
        return True
    return f"{fv:.{decimals}f}" == f"{fw:.{decimals}f}"


@predicate(
    id="judg.evidence_exists",
    version=1,
    scope=["kind:judgment"],
    phase="post",
    default=Disposition.BLOCK,
)
def evidence_exists(ctx: GateContext) -> Verdict:
    """Every non-abstained item cites at least one supporting ref, and every ref resolves to a
    cell of the declared evidence with the same value."""
    assert ctx.output is not None
    problems: list[dict[str, Any]] = []
    for rep_no, rep in _valid_replicates(ctx):
        for item in _items(rep):
            if item.get("abstain"):
                continue
            refs = list(item.get("supporting_evidence", []))
            if not refs:
                problems.append(
                    {
                        "replicate": rep_no,
                        "item": item.get("item_id"),
                        "problem": "no supporting evidence",
                    }
                )
            for ref in refs + list(item.get("contradicting_evidence", [])):
                table = ctx.output.evidence_tables.get(str(ref.get("table")))
                if table is None:
                    problems.append(
                        {
                            "replicate": rep_no,
                            "item": item.get("item_id"),
                            "ref": ref,
                            "problem": "unknown table",
                        }
                    )
                    continue
                ok, cell = table.cell(str(ref.get("row")), str(ref.get("column")))
                if not ok:
                    problems.append(
                        {
                            "replicate": rep_no,
                            "item": item.get("item_id"),
                            "ref": ref,
                            "problem": "no such cell",
                        }
                    )
                elif not values_equal(cell, ref.get("value")):
                    problems.append(
                        {
                            "replicate": rep_no,
                            "item": item.get("item_id"),
                            "ref": ref,
                            "problem": f"value differs from cell {cell!r}",
                        }
                    )
    if problems:
        return Verdict(
            True,
            "an evidence reference does not resolve to the declared evidence",
            {"problems": problems},
        )
    return Verdict(False)


@predicate(
    id="judg.vocabulary_resolves",
    version=1,
    scope=["kind:judgment"],
    phase="post",
    default=Disposition.BLOCK,
)
def vocabulary_resolves(ctx: GateContext) -> Verdict:
    m = ctx.project.module_for(ctx.action.module)
    if m is None or m.vocabulary is None:
        return Verdict(False)
    vocab = ctx.project.vocabularies.get(m.vocabulary)
    if vocab is None:
        return Verdict(
            True, f"vocabulary {m.vocabulary} is not loaded", {"vocabulary": m.vocabulary}
        )
    bad: list[dict[str, Any]] = []
    for rep_no, rep in _valid_replicates(ctx):
        for item in _items(rep):
            label = item.get("label")
            if label is not None and label not in vocab:
                bad.append({"replicate": rep_no, "item": item.get("item_id"), "label": label})
    if bad:
        return Verdict(
            True,
            "a label is not in the module's declared vocabulary",
            {"labels": bad, "vocabulary": m.vocabulary},
        )
    return Verdict(False)


@predicate(
    id="judg.confidence_consistent",
    version=1,
    scope=["kind:judgment"],
    phase="post",
    default=Disposition.FLAG,
)
def confidence_consistent(ctx: GateContext) -> Verdict:
    criteria = ctx.policy.confidence_criteria
    bad: list[dict[str, Any]] = []
    for rep_no, rep in _valid_replicates(ctx):
        for item in _items(rep):
            conf = item.get("confidence")
            if item.get("abstain") or conf not in criteria:
                continue
            c = criteria[conf]
            n_sup = len(item.get("supporting_evidence", []))
            n_con = len(item.get("contradicting_evidence", []))
            if n_sup < c.min_supporting or (
                c.max_contradicting is not None and n_con > c.max_contradicting
            ):
                bad.append(
                    {
                        "replicate": rep_no,
                        "item": item.get("item_id"),
                        "confidence": conf,
                        "supporting": n_sup,
                        "contradicting": n_con,
                    }
                )
    if bad:
        return Verdict(
            True, "declared confidence exceeds what the cited evidence supports", {"items": bad}
        )
    return Verdict(False)


def _numeral_problems(text: str, allowed: list[Any], where: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for num in NUMERAL.findall(text):
        if not any(numeral_matches(num, v) for v in allowed):
            out.append({**where, "numeral": num})
    return out


@predicate(
    id="judg.numeric_claims_match",
    version=1,
    scope=["kind:judgment", "kind:report"],
    phase="post",
    default=Disposition.BLOCK,
)
def numeric_claims_match(ctx: GateContext) -> Verdict:
    """Every numeral in a rationale matches a cited evidence value; every numeral in report
    prose matches some cell of the evidence tables. Rounding to the written precision."""
    assert ctx.output is not None
    problems: list[dict[str, Any]] = []
    for rep_no, rep in _valid_replicates(ctx):
        for item in _items(rep):
            cited = [
                r.get("value")
                for r in list(item.get("supporting_evidence", []))
                + list(item.get("contradicting_evidence", []))
            ]
            problems += _numeral_problems(
                str(item.get("rationale", "")),
                cited,
                {"replicate": rep_no, "item": item.get("item_id")},
            )
    if ctx.output.prose:
        cells = [
            v
            for t in ctx.output.evidence_tables.values()
            for row in t.rows.values()
            for v in row.values()
        ]
        problems += _numeral_problems(ctx.output.prose, cells, {"prose": True})
    if problems:
        return Verdict(
            True, "a numeral matches no value in the referenced evidence", {"problems": problems}
        )
    return Verdict(False)


@predicate(
    id="judg.replicates_below_min",
    version=1,
    scope=["kind:judgment"],
    phase="post",
    default=Disposition.BLOCK,
)
def replicates_below_min(ctx: GateContext) -> Verdict:
    assert ctx.output is not None
    n_valid = sum(1 for ok in ctx.output.replicate_valid if ok)
    minimum = ctx.policy.profile(ctx.project.profile).replicates_min
    if n_valid < minimum:
        return Verdict(
            True,
            f"{n_valid} valid replicate(s), policy minimum is {minimum}",
            {"valid": n_valid, "min": minimum},
        )
    return Verdict(False)


@predicate(
    id="judg.items_incomplete",
    version=1,
    scope=["kind:judgment"],
    phase="post",
    default=Disposition.BLOCK,
)
def items_incomplete(ctx: GateContext) -> Verdict:
    assert ctx.output is not None
    want = set(ctx.output.items)
    missing: dict[int, list[str]] = {}
    for rep_no, rep in _valid_replicates(ctx):
        have = {str(i.get("item_id")) for i in _items(rep)}
        gone = sorted(want - have)
        if gone:
            missing[rep_no] = gone
    if missing:
        return Verdict(
            True, "an item from items_from has no judgment in some replicate", {"missing": missing}
        )
    return Verdict(False)


@predicate(
    id="judg.considered_set_missing",
    version=1,
    scope=["considered_set:true"],
    phase="post",
    default=Disposition.BLOCK,
)
def considered_set_missing(ctx: GateContext) -> Verdict:
    m = ctx.project.module_for(ctx.action.module)
    if m is None or m.judgment is None or not m.judgment.considered_set:
        return Verdict(False)
    if ctx.output is None or ctx.output.considered_set is None:
        return Verdict(True, "the output carries no considered-set denominator", {})
    return Verdict(False)
