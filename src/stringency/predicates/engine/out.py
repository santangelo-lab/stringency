"""`out.*`: output validation."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


@predicate(
    id="out.schema_conformance", version=1, scope=["*"], phase="post", default=Disposition.BLOCK
)
def schema_conformance(ctx: GateContext) -> Verdict:
    if ctx.output is None:
        return Verdict(False)
    if ctx.output.schema_errors:
        return Verdict(
            True,
            "an output declared with a schema fails validation",
            {"errors": dict(ctx.output.schema_errors)},
        )
    return Verdict(False)
