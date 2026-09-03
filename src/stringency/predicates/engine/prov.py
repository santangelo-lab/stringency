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
