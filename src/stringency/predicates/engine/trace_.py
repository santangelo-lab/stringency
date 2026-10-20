"""The trace against its own history (trace-integrity-plan.md T2, backlog L51). Invariant block
at run open and at deliver: a mutable row that disagrees with its events means the record was
changed outside the Store, and no acknowledgement clears that. Reads `ctx.project.trace_findings`,
the audit the engine ran before the gate (predicates do no I/O)."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


@predicate(
    id="prov.trace_inconsistent",
    version=1,
    scope=["*"],
    phase=["run_open", "deliver"],
    default=Disposition.BLOCK,
    invariant=True,
)
def trace_inconsistent(ctx: GateContext) -> Verdict:
    findings = ctx.project.trace_findings
    if not findings:
        return Verdict(False)
    shown = "; ".join(findings[:3]) + (
        f"; and {len(findings) - 3} more" if len(findings) > 3 else ""
    )
    return Verdict(
        True,
        f"the trace disagrees with its own history in {len(findings)} place(s): {shown}; run `stringency audit`",
        {"findings": list(findings)},
    )
