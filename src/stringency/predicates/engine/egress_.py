"""Data egress against the project ceiling (backlog L1). Invariant blocks at init and at run
open: an acknowledgement cannot clear them; only a setup within the ceiling, or a ceiling the
person raises, does.

Both read `ctx.project.egress`, the assessment the engine computed from the bound
configuration and the module scripts before the gate (predicates do no I/O). No assessment
means nothing to compare, and neither fires.
"""

from __future__ import annotations

from stringency.egress import exceeds_reason
from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


def _exceeds(ctx: GateContext) -> Verdict:
    a = ctx.project.egress
    if a is None or a.within is not False:
        return Verdict(False)
    return Verdict(
        True,
        exceeds_reason(a),
        {
            "max_class": a.max_class,
            "assessed_class": a.assessed_class,
            "over": [c.to_json() for c in a.over],
        },
    )


@predicate(
    id="init.egress_exceeds_ceiling",
    version=1,
    scope=["project"],
    phase="init",
    default=Disposition.BLOCK,
    invariant=True,
)
def init_egress_exceeds_ceiling(ctx: GateContext) -> Verdict:
    return _exceeds(ctx)


@predicate(
    id="prov.egress_exceeds_ceiling",
    version=1,
    scope=["*"],
    phase="run_open",
    default=Disposition.BLOCK,
    invariant=True,
)
def egress_exceeds_ceiling(ctx: GateContext) -> Verdict:
    return _exceeds(ctx)
