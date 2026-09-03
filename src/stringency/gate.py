"""The gate (design 6.2): evaluate one phase over every registered predicate whose scope
includes the action, resolve effective dispositions from the policy, and write the results.

Reads: nothing from the trace. Writes: predicate_results (one row per predicate evaluated).
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass

from stringency.clock import now_iso
from stringency.db.store import Store
from stringency.modules import ModuleManifest
from stringency.predicates.context import Disposition, GateContext, Verdict
from stringency.predicates.registry import PredicateSpec, Registry

PREDICATE_BUDGET_S = 5.0


@dataclass(frozen=True)
class GateRecord:
    spec: PredicateSpec
    verdict: Verdict
    default: Disposition
    effective: Disposition

    @property
    def fired(self) -> bool:
        return self.verdict.fired

    def line(self) -> str:
        why = f": {self.verdict.reason}" if self.verdict.reason else ""
        return f"{self.spec.id}@{self.spec.version} [{self.effective}]{why}"


@dataclass(frozen=True)
class GateResult:
    phase: str
    records: tuple[GateRecord, ...]

    def fired(self, disposition: Disposition) -> list[GateRecord]:
        return [r for r in self.records if r.fired and r.effective == disposition]

    @property
    def blocked(self) -> list[GateRecord]:
        return self.fired(Disposition.BLOCK)

    @property
    def flagged(self) -> list[GateRecord]:
        return self.fired(Disposition.FLAG)

    @property
    def logged(self) -> list[GateRecord]:
        return self.fired(Disposition.LOG)

    @property
    def passed(self) -> bool:
        return not self.blocked and not self.flagged

    def evaluated_ids(self) -> list[str]:
        return [r.spec.id for r in self.records]


def in_scope_specs(
    registry: Registry,
    phase: str,
    *,
    operation: str,
    module: ModuleManifest | None,
    runner: str | None,
) -> list[PredicateSpec]:
    kind = module.kind if module else None
    stochastic = bool(module and module.stochastic)
    considered = bool(module and module.judgment and module.judgment.considered_set)
    return [
        s
        for s in registry.for_phase(phase)  # type: ignore[arg-type]
        if s.in_scope(
            operation, kind=kind, runner=runner, stochastic=stochastic, considered_set=considered
        )
    ]


def run_predicate(spec: PredicateSpec, ctx: GateContext) -> Verdict:
    """Call one predicate under a loose wall-clock budget. A predicate that raises is
    recorded as fired, with the exception as its reason: a broken check is not a passed one."""
    t0 = time.monotonic()
    try:
        v = spec.fn(ctx)
    except Exception as e:  # noqa: BLE001
        return Verdict(True, f"predicate raised {type(e).__name__}: {e}", {"error": str(e)})
    elapsed = time.monotonic() - t0
    if elapsed > PREDICATE_BUDGET_S:
        return Verdict(
            True, f"predicate exceeded its time budget ({elapsed:.1f}s)", {"elapsed_s": elapsed}
        )
    return v


def evaluate(
    ctx: GateContext,
    *,
    registry: Registry,
    store: Store | None,
    policy_digest: str,
    module: ModuleManifest | None,
    runner: str | None,
    only: Iterable[PredicateSpec] | None = None,
) -> GateResult:
    """Evaluate `ctx.phase` and record every verdict.

    Writes: predicate_results, one row per predicate in scope, fired or not, with default
    and effective disposition and the policy digest (design 6.3, 9.2).
    """
    specs = (
        list(only)
        if only is not None
        else in_scope_specs(
            registry, ctx.phase, operation=ctx.action.operation, module=module, runner=runner
        )
    )
    records: list[GateRecord] = []
    for spec in specs:
        verdict = run_predicate(spec, ctx)
        effective = ctx.policy.effective(spec, ctx.project.profile)
        records.append(GateRecord(spec, verdict, spec.default, effective))
        if store is not None:
            store.insert(
                "predicate_results",
                {
                    "run_id": ctx.action.run_id,
                    "action_id": ctx.action.action_id,
                    "phase": ctx.phase,
                    "predicate_id": spec.id,
                    "predicate_version": spec.version,
                    "fired": verdict.fired,
                    "default_disposition": str(spec.default),
                    "effective_disposition": str(effective),
                    "reason": verdict.reason,
                    "evidence_json": verdict.evidence,
                    "severity": verdict.severity,
                    "policy_digest": policy_digest,
                    "ts": now_iso(),
                },
            )
    return GateResult(ctx.phase, tuple(records))
