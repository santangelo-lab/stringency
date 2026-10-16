"""`prov.*`: provenance at delivery."""

from __future__ import annotations

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


@predicate(
    id="prov.orphan_artifact", version=1, scope=["*"], phase="deliver", default=Disposition.BLOCK
)
def orphan_artifact(ctx: GateContext) -> Verdict:
    orphans = list(ctx.output.observed.get("missing_sidecars", [])) if ctx.output else []
    if orphans:
        return Verdict(True, "an artifact proposed as final has no sidecar", {"orphans": orphans})
    return Verdict(False)


@predicate(
    id="prov.controls_stale",
    version=1,
    scope=["*"],
    phase="pre",
    default=Disposition.LOG,
)
def controls_stale(ctx: GateContext) -> Verdict:
    """Open mode (open_mode_plan.md 2.5, 2026-10-16): the tool about to run has no control, no
    passing `controls_runs` row for its version, or a last passing row that ran under another
    digest of its environment. Logged: the label carries the consequence (an answer on its
    outputs is untested). Never outside open mode and never for an exec step. Reads
    `project.controls_current`."""
    if ctx.project.mode != "open" or ctx.action.operation == "exec":
        return Verdict(False)
    cur = ctx.project.controls_current.get(ctx.action.module)
    if cur is None:
        return Verdict(False)
    status = str(cur.get("status", "none"))
    if status == "current":
        return Verdict(False)
    why = (
        "no passing control is recorded for this tool version"
        if status == "none"
        else "the last passing control ran under another environment"
    )
    return Verdict(True, why, {"status": status, "last_passing": cur.get("last_passing")})
