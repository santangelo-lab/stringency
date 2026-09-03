"""Toy predicates (build plan 4). Each mirrors a real domain predicate."""

from __future__ import annotations

from stringency.predicates import Disposition, GateContext, Verdict, predicate

SRC = "stringency-toy"


@predicate(
    id="toy.replication_unit",
    version=1,
    scope=["compare_groups"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["compare_groups.replicate_unit"],
    source=SRC,
)
def replication_unit(ctx: GateContext) -> Verdict:
    """Mirrors de.replication_unit: a row-level test when the design declares units."""
    proposed = ctx.action.parameters.get("replicate_unit")
    declared = ctx.design.replication_unit
    if ctx.design.has_biological_replicates and proposed == "row":
        return Verdict(
            True,
            "row-level test with a declared replication unit",
            {"declared_replication_unit": declared, "proposed": proposed},
        )
    return Verdict(False)


@predicate(
    id="toy.no_correction",
    version=1,
    scope=["compare_groups"],
    phase="pre",
    default=Disposition.BLOCK,
    covers=["compare_groups.correction"],
    source=SRC,
)
def no_correction(ctx: GateContext) -> Verdict:
    """Mirrors test.multiple_comparison."""
    corr = ctx.action.parameters.get("correction")
    if corr == "none":
        return Verdict(True, "no multiple-comparison correction", {"correction": corr})
    return Verdict(False)


@predicate(
    id="toy.filter_after_summary",
    version=1,
    scope=["filter_rows"],
    phase="pre",
    default=Disposition.FLAG,
    covers=["filter_rows.*"],
    source=SRC,
)
def filter_after_summary(ctx: GateContext) -> Verdict:
    """Mirrors qc.filter_ordering: filtering after a summary already exists in history."""
    prior = [h.step for h in ctx.history if h.operation == "summarize_groups"]
    if prior:
        return Verdict(True, "filter proposed after summarize_groups", {"summarized_at": prior})
    return Verdict(False)
