"""State (design 4): a structured summary of the analysis, never the data object."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from stringency import hashing
from stringency.clock import now_iso
from stringency.ids import new_id

if TYPE_CHECKING:
    from stringency.db.store import Store


@dataclass(frozen=True)
class StepRecord:
    step: str
    operation: str
    params: dict[str, Any]
    output_digests: dict[str, str]
    inherited: bool = False

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "step": self.step,
            "operation": self.operation,
            "params": self.params,
            "output_digests": self.output_digests,
        }
        if self.inherited:
            d["inherited"] = True
        return d

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> StepRecord:
        return cls(
            step=d["step"],
            operation=d["operation"],
            params=dict(d.get("params", {})),
            output_digests=dict(d.get("output_digests", {})),
            inherited=bool(d.get("inherited", False)),
        )


@dataclass(frozen=True)
class ObjectState:
    type: str
    digest: str
    summary: dict[str, Any]  # extractor output (design 4.2)

    @property
    def counts_per_group(self) -> dict[str, dict[str, dict[str, int]]]:
        cpg = self.summary.get("counts_per_group", {})
        return dict(cpg) if isinstance(cpg, dict) else {}

    @property
    def fields(self) -> dict[str, Any]:
        f = self.summary.get("fields", {})
        return dict(f) if isinstance(f, dict) else {}


@dataclass(frozen=True)
class State:
    run_id: str
    after_step: str | None
    objects: dict[str, ObjectState]
    design: dict[str, Any]
    objective: dict[str, Any]
    history: tuple[StepRecord, ...]
    env: dict[str, Any]
    mode: str
    profile: str
    state: int = 1

    def to_json(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "run_id": self.run_id,
            "after_step": self.after_step,
            "objects": {
                k: {"type": v.type, "digest": v.digest, "summary": v.summary}
                for k, v in self.objects.items()
            },
            "design": self.design,
            "objective": self.objective,
            "history": [h.to_json() for h in self.history],
            "env": self.env,
            "mode": self.mode,
            "profile": self.profile,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> State:
        return cls(
            run_id=d["run_id"],
            after_step=d.get("after_step"),
            objects={
                k: ObjectState(type=v["type"], digest=v["digest"], summary=v.get("summary", {}))
                for k, v in d.get("objects", {}).items()
            },
            design=dict(d.get("design", {})),
            objective=dict(d.get("objective", {})),
            history=tuple(StepRecord.from_json(h) for h in d.get("history", [])),
            env=dict(d.get("env", {})),
            mode=d["mode"],
            profile=d["profile"],
        )

    def digest(self) -> str:
        return hashing.prefixed(hashing.hash_json(self.to_json()))

    def advanced(
        self,
        step: str,
        operation: str,
        params: dict[str, Any],
        objects: dict[str, ObjectState],
        output_digests: dict[str, str],
    ) -> State:
        """The state after a step: objects replaced by name, history appended."""
        merged = dict(self.objects)
        merged.update(objects)
        return State(
            run_id=self.run_id,
            after_step=step,
            objects=merged,
            design=self.design,
            objective=self.objective,
            history=(*self.history, StepRecord(step, operation, params, output_digests)),
            env=self.env,
            mode=self.mode,
            profile=self.profile,
        )

    def any_object(self) -> ObjectState | None:
        for v in self.objects.values():
            return v
        return None


@dataclass(frozen=True)
class Extraction:
    """What the extractor printed, plus which extractor."""

    extractor: str
    version: str
    summary: dict[str, Any] = field(default_factory=dict)


def store_snapshot(
    store: Store, run_id: str, step_id: str, phase: str, state: State, extractor: str, version: str
) -> str:
    """Writes: state_snapshots. Returns snapshot_id."""
    sid = new_id()
    store.insert(
        "state_snapshots",
        {
            "snapshot_id": sid,
            "run_id": run_id,
            "step_id": step_id,
            "phase": phase,
            "extractor": extractor,
            "extractor_version": version,
            "summary_json": state.to_json(),
            "digest": state.digest(),
            "ts": now_iso(),
        },
    )
    return sid


def latest_state(store: Store, run_id: str, step_id: str | None = None) -> State | None:
    """Reads: state_snapshots. The newest post-phase snapshot for the run (or the step)."""
    if step_id is None:
        row = store.one(
            "SELECT summary_json FROM state_snapshots WHERE run_id = ? AND phase = 'post' "
            "ORDER BY ts DESC, rowid DESC LIMIT 1",
            (run_id,),
        )
    else:
        row = store.one(
            "SELECT summary_json FROM state_snapshots WHERE run_id = ? AND step_id = ? "
            "AND phase = 'post' ORDER BY ts DESC, rowid DESC LIMIT 1",
            (run_id, step_id),
        )
    if row is None:
        return None
    return State.from_json(json.loads(row["summary_json"]))
