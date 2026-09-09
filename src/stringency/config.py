"""Pydantic models for the project's bound files: stringency.yml, inputs.yml, and the
engine-known envelopes of design.yml and objective.yml (design 2.2 through 2.5).

Engine-known fields are validated here. The `domain` block of the objective and any extra
design fields are passed to the plugin's schema untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency.exit_codes import ConfigError

Mode = Literal["pipeline", "staged", "open"]
Profile = Literal["strict", "standard", "exploratory"]
JudgmentHarness = Literal["api", "openai-compatible", "subagent", "mock"]
Runner = Literal["operator", "engine"]
ExecutorKind = Literal["local", "apptainer"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Lenient(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class MethodRef(Strict):
    repo: str
    tag: str
    sha: str


class Roles(Strict):
    owner: str
    reviewer: str


class Declarations(Strict):
    """Who drafted the three declaration files, and the brief they were drafted from."""

    drafted_by: Literal["person", "agent"] = "person"
    harness: str | None = None
    session_ref: str | None = None
    brief: str | None = None  # file name in the project root, when a brief was given


class StringencyConfig(Strict):
    """stringency.yml. Written by init, read-only after."""

    stringency: Literal[1] = 1
    project_id: str
    created: str
    stringency_version: str
    method: MethodRef
    pipeline: str
    mode: Mode = "pipeline"
    profile: Profile = "standard"
    roles: Roles
    judgment_harness: JudgmentHarness = "subagent"
    execution: Runner = "operator"
    executor: ExecutorKind = "apptainer"
    policy: str = "method/policy.yml"
    splits: dict[str, Any] | None = None
    declarations: Declarations | None = None

    @model_validator(mode="after")
    def _refuse_open_strict(self) -> StringencyConfig:
        if self.mode == "open" and self.profile == "strict":
            raise ValueError("mode open with profile strict is refused")
        if self.mode != "pipeline":
            raise ValueError(f"mode {self.mode} is reserved; v1 accepts only pipeline")
        return self


class DerivedFrom(Strict):
    """An input that is a delivered artifact of an earlier stringency run (chained projects).
    `init` verifies it against the sidecar beside the file."""

    run_id: str
    step_id: str | None = None
    output: str | None = None
    project: str | None = None  # informational: where the upstream project lives


class InputItem(Strict):
    name: str
    path: str
    type: str
    blake3: str
    source: str | None = None
    build: str | None = None  # reference build, checked by init.reference_mismatch
    derived_from: DerivedFrom | None = None


class InputsManifest(Strict):
    inputs: Literal[1] = 1
    items: list[InputItem]

    def by_name(self) -> dict[str, InputItem]:
        return {i.name: i for i in self.items}

    @model_validator(mode="after")
    def _unique_names(self) -> InputsManifest:
        names = [i.name for i in self.items]
        if len(set(names)) != len(names):
            raise ValueError("input names must be unique")
        return self


class Factor(Lenient):
    column: str
    levels: list[str]


class HoldoutFixture(Lenient):
    type: str
    blake3: str
    note: str | None = None


class Design(Lenient):
    """Engine-known envelope of design.yml. The plugin schema validates the whole file."""

    design: Literal[1] = 1
    units: dict[str, str] = Field(default_factory=dict)
    factors: dict[str, Factor] = Field(default_factory=dict)
    batch: list[str] = Field(default_factory=list)
    replication_unit: str | None = None
    holdout: list[HoldoutFixture] = Field(default_factory=list)

    @property
    def has_biological_replicates(self) -> bool:
        return self.replication_unit is not None and self.replication_unit != self.units.get(
            "observation"
        )

    def columns(self) -> list[str]:
        """Columns the raw input must carry. The observation unit names the row itself and
        is not a column; every other unit, factor column, and batch variable is."""
        unit_cols = [v for k, v in self.units.items() if k != "observation"]
        cols = unit_cols + [f.column for f in self.factors.values()] + self.batch
        seen: list[str] = []
        for c in cols:
            if c not in seen:
                seen.append(c)
        return seen


class Objective(Lenient):
    """Engine-known core of objective.yml plus a plugin-interpreted `domain` block."""

    objective: Literal[1] = 1
    id: str
    question: str
    contrasts: list[list[str]] = Field(default_factory=list)
    replication_unit: str | None = None
    min_n_per_group: int = 0
    deliverables: list[str] = Field(default_factory=list)
    domain: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _contrast_shape(self) -> Objective:
        for c in self.contrasts:
            if len(c) != 3:
                raise ValueError(f"a contrast is [factor, level_a, level_b]; got {c}")
        return self


def load_yaml(path: Path) -> Any:
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"missing file: {path}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: invalid YAML: {e}") from None


def dump_yaml(obj: Any, path: Path) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False, default_flow_style=False))


def load_model[T: BaseModel](model: type[T], path: Path) -> T:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping at top level")
    try:
        return model.model_validate(data)
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None
