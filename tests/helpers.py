"""Builders for gate contexts in tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.actions import Action, build_action
from stringency.modules import Module
from stringency.predicates.context import (
    EvidenceTable,
    GateContext,
    OutputBundle,
    OutputInfo,
    ProjectConfig,
)
from stringency.project import Project
from stringency.state import ObjectState, State, StepRecord

FIXTURES = Path(__file__).parent / "fixtures"


def state_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / "state" / f"{name}.json").read_text())


def frame_object(name: str = "frame_default") -> ObjectState:
    summary = state_fixture(name)
    return ObjectState(
        type="frame", digest=hashing.prefixed(hashing.hash_json(summary)), summary=summary
    )


def make_action(
    project: Project,
    step_id: str,
    *,
    proposed: Mapping[str, Any] | None = None,
    run_id: str = "RUN",
    attempt: int = 1,
) -> tuple[Action, Module]:
    step = project.pipeline.step(step_id)
    module = project.modules.require(step.module)
    action = build_action(
        run_id=run_id,
        step=step,
        module=module,
        attempt=attempt,
        input_digests={k: "00" * 32 for k in step.inputs},
        proposed=dict(proposed or {}),
    )
    return action, module


def make_ctx(
    project: Project,
    step_id: str,
    *,
    phase: str = "pre",
    proposed: Mapping[str, Any] | None = None,
    objects: Mapping[str, ObjectState] | None = None,
    history: tuple[StepRecord, ...] = (),
    output: OutputBundle | None = None,
    step_status: Mapping[str, str] | None = None,
    env_digests: Mapping[str, str | None] | None = None,
    git_dirty: bool = False,
    allow_dirty_reason: str | None = None,
    input_digests_now: Mapping[str, str] | None = None,
    profile: str | None = None,
    action: Action | None = None,
) -> GateContext:
    if action is None:
        action, _ = make_action(project, step_id, proposed=proposed)
    cfg = (
        project.config
        if profile is None
        else project.config.model_copy(update={"profile": profile})
    )
    if env_digests is None:
        env_digests = {e: "lockhash" for e in project.env_names()}
    if step_status is None:
        # every predecessor completed
        step_status = {s: "completed" for s in project.pipeline.order() if s != step_id}
    if input_digests_now is None:
        input_digests_now = {i.name: i.blake3 for i in project.inputs.items}
    pc = ProjectConfig(
        config=cfg,
        pipeline=project.pipeline,
        modules=project.manifests(),
        inputs=project.inputs,
        git_dirty=git_dirty,
        allow_dirty_reason=allow_dirty_reason,
        input_digests_now=input_digests_now,
        env_digests=env_digests,
        step_status=step_status,
        plugin_modes=tuple(project.plugin.modes),
        vocabularies=project.plugin.vocabularies,
        object_types=tuple(project.plugin.object_types),
    )
    objs = dict(objects) if objects is not None else {"object": frame_object()}
    state = State(
        run_id=action.run_id,
        after_step=None,
        objects=objs,
        design=project.design.model_dump(),
        objective=project.objective.model_dump(),
        history=history,
        env={},
        mode=cfg.mode,
        profile=cfg.profile,
    )
    return GateContext(
        phase=phase,  # type: ignore[arg-type]
        project=pc,
        objective=project.objective,
        design=project.design,
        state=state,
        action=action,
        history=history,
        output=output,
        policy=project.policy,
    )


SUMMARY_TABLE = EvidenceTable(
    name="summary",
    key_column="group",
    columns=("group", "n_rows", "n_units", "mean_value", "sd_value", "top_unit"),
    rows={
        "A": {
            "group": "A",
            "n_rows": 17,
            "n_units": 3,
            "mean_value": 74.31,
            "sd_value": 8.9,
            "top_unit": "u1",
        },
        "B": {
            "group": "B",
            "n_rows": 17,
            "n_units": 3,
            "mean_value": 15.62,
            "sd_value": 2.4,
            "top_unit": "u4",
        },
        "C": {
            "group": "C",
            "n_rows": 16,
            "n_units": 3,
            "mean_value": 44.02,
            "sd_value": 31.7,
            "top_unit": "u7",
        },
    },
)


def ref(row: str, column: str, table: str = "summary") -> dict[str, Any]:
    ok, value = SUMMARY_TABLE.cell(row, column)
    assert ok
    return {"table": table, "row": row, "column": column, "value": value}


def judgment(
    item: str,
    label: str | None,
    confidence: str = "high",
    *,
    abstain: bool = False,
    supporting: list[dict[str, Any]] | None = None,
    contradicting: list[dict[str, Any]] | None = None,
    rationale: str = "",
) -> dict[str, Any]:
    sup = (
        supporting
        if supporting is not None
        else [ref(item, "mean_value"), ref(item, "sd_value"), ref(item, "n_units")]
    )
    return {
        "item_id": item,
        "label": None if abstain else label,
        "ontology_id": None,
        "confidence": "abstain" if abstain else confidence,
        "abstain": abstain,
        "supporting_evidence": [] if abstain else sup,
        "contradicting_evidence": contradicting or [],
        "rationale": rationale,
    }


def replicate(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": items}


def unanimous_replicates(
    labels: Mapping[str, str] | None = None, n: int = 3
) -> list[dict[str, Any]]:
    labels = labels or {"A": "abundant", "B": "sparse", "C": "variable"}
    return [replicate([judgment(i, lab) for i, lab in labels.items()]) for _ in range(n)]


def judgment_bundle(
    replicates: list[dict[str, Any]], valid: list[bool] | None = None, **kw: Any
) -> OutputBundle:
    return OutputBundle(
        outputs={"judgments": OutputInfo("judgments", "judgments", "x", "blake3:00")},
        replicates=tuple(replicates),
        replicate_valid=tuple(valid if valid is not None else [True] * len(replicates)),
        evidence_tables={"summary": SUMMARY_TABLE},
        items=("A", "B", "C"),
        **kw,
    )
