"""The predicate contract (design 6.1). Frozen.

`GateContext` carries exactly the fields the design lists. `project` is the bound project
configuration and everything static a predicate may need about it (pipeline, module
manifests, inputs); nothing in it is a data object or the agent's reasoning.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from stringency.actions import Action
    from stringency.config import Design, InputsManifest, Objective, StringencyConfig
    from stringency.modules import ModuleManifest
    from stringency.pipelines import Pipeline
    from stringency.policy import Policy
    from stringency.state import State, StepRecord


class Disposition(StrEnum):
    LOG = "log"
    FLAG = "flag"
    BLOCK = "block"


Phase = Literal["pre", "post", "init", "run_open", "deliver"]


@dataclass(frozen=True)
class ProjectConfig:
    """Static project facts available to predicates: mode, profile, roles, and the bound
    pipeline with its module manifests. Loaded once; predicates do no I/O."""

    config: StringencyConfig
    pipeline: Pipeline
    modules: Mapping[str, ModuleManifest]  # by name@version
    inputs: InputsManifest
    git_dirty: bool = False
    allow_dirty_reason: str | None = None
    input_digests_now: Mapping[str, str] = field(default_factory=dict)  # name -> hash at open
    env_digests: Mapping[str, str | None] = field(default_factory=dict)  # env name -> digest
    step_status: Mapping[str, str] = field(default_factory=dict)  # step id -> status
    plugin_modes: tuple[str, ...] = ("pipeline",)
    vocabularies: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    object_types: tuple[str, ...] = ()  # types that have a state extractor

    @property
    def mode(self) -> str:
        return self.config.mode

    @property
    def profile(self) -> str:
        return self.config.profile

    def module_for(self, action_module: str) -> ModuleManifest | None:
        return self.modules.get(action_module)


@dataclass(frozen=True)
class OutputBundle:
    """Post-gate view of what a step produced (design 6.1). All validated, none of it the
    data object itself."""

    outputs: Mapping[str, OutputInfo]
    replicates: tuple[Mapping[str, Any], ...] = ()  # judgment: one dict per replicate
    replicate_valid: tuple[bool, ...] = ()
    consensus: tuple[Mapping[str, Any], ...] = ()
    prose: str | None = None
    evidence_tables: Mapping[str, EvidenceTable] = field(default_factory=dict)
    items: tuple[str, ...] = ()
    observed: Mapping[str, Any] = field(
        default_factory=dict
    )  # operator evidence: params, seed, container
    env_status: str | None = None  # verified | as_reported
    schema_errors: Mapping[str, str] = field(default_factory=dict)
    considered_set: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OutputInfo:
    name: str
    type: str
    path: str
    digest: str
    schema_valid: bool | None = None


@dataclass(frozen=True)
class EvidenceTable:
    """A table the judge was shown: rows keyed by the item key, columns by name."""

    name: str
    key_column: str
    columns: tuple[str, ...]
    rows: Mapping[str, Mapping[str, Any]]  # row key -> {column: value}

    def cell(self, row: str, column: str) -> tuple[bool, Any]:
        r = self.rows.get(row)
        if r is None or column not in r:
            return False, None
        return True, r[column]


@dataclass(frozen=True)
class GateContext:
    phase: Phase
    project: ProjectConfig
    objective: Objective
    design: Design
    state: State
    action: Action
    history: tuple[StepRecord, ...]
    output: OutputBundle | None
    policy: Policy


@dataclass(frozen=True)
class Verdict:
    fired: bool
    reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: str | None = None
