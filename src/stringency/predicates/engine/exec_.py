"""`exec.*`: what ran versus what was admitted (design 3.4 step 4)."""

from __future__ import annotations

from typing import Any

from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import predicate


def _same(a: Any, b: Any) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


@predicate(
    id="exec.plan_drift",
    version=1,
    scope=["runner:operator"],
    phase="post",
    default=Disposition.BLOCK,
)
def plan_drift(ctx: GateContext) -> Verdict:
    if ctx.output is None:
        return Verdict(False)
    observed = ctx.output.observed
    drift: dict[str, Any] = {}
    for k, v in dict(observed.get("params", {})).items():
        if k in ctx.action.parameters and not _same(v, ctx.action.parameters[k]):
            drift[f"param:{k}"] = {"admitted": ctx.action.parameters[k], "observed": v}
    m = ctx.project.module_for(ctx.action.module)
    if m is not None and m.stochastic and m.seed_param and observed.get("seed") is not None:
        admitted_seed = ctx.action.parameters.get(m.seed_param)
        if not _same(observed["seed"], admitted_seed):
            drift["seed"] = {"admitted": admitted_seed, "observed": observed["seed"]}
    expected_env = ctx.project.env_digests.get(m.env) if m is not None else None
    reported = observed.get("container_digest")
    if expected_env and reported and reported != expected_env:
        drift["container"] = {"admitted": expected_env, "observed": reported}
    if drift:
        return Verdict(
            True,
            "the evidence shows a different action ran than the one admitted",
            {"drift": drift},
        )
    return Verdict(False)


@predicate(
    id="exec.script_drift",
    version=1,
    scope=["*"],
    phase="post",
    default=Disposition.BLOCK,
)
def script_drift(ctx: GateContext) -> Verdict:
    """The module script that ran (hashed by the engine before running it, or at `submit` for an
    operator step) is not the script present when the run opened. The run's SHA and dirty flag
    describe the tree at open; an edit after that would otherwise run under the same SHA."""
    if ctx.output is None:
        return Verdict(False)
    script = ctx.output.observed.get("script")
    if not isinstance(script, dict) or not script.get("blob"):
        return Verdict(False)
    at_open = ctx.project.script_blobs.get(ctx.action.module)
    if at_open is None or at_open == script["blob"]:
        return Verdict(False)
    return Verdict(
        True,
        "the module script differs from the one present when the run opened",
        {"path": script.get("path"), "at_open": at_open, "at_execution": script["blob"]},
    )
