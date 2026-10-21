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
JudgmentHarness = Literal["api", "openai-compatible", "subagent", "mock", "command"]
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


class EgressSetting(Strict):
    """The ceiling on what may leave the machine, set by the person at init (backlog L1).
    `max_class` 0 none to 4 data, None when not declared; `operator` says whether the agent
    operating the project runs on a hosted model (it reads hold packets and present output)."""

    max_class: int | None = Field(default=None, ge=0, le=4)
    operator: Literal["hosted", "local", "none"] = "hosted"


class JudgmentSetting(Strict):
    """How the judgment harness is reached (design 10.2; backlog L34 H3): `model` for `api`
    and `openai-compatible`; `base_url`, `temperature` and `seed` for `openai-compatible`;
    `command` and `timeout_s` for `command` (the command the engine runs per replicate, with
    `{schema}`, `{response}`, `{prompt_file}` and `{dir}` placeholders). Read-only after init."""

    model: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    seed: int | None = None
    command: str | None = None
    timeout_s: int | None = None


class StringencyConfig(Strict):
    """stringency.yml. Written by init, read-only after."""

    stringency: Literal[1] = 1
    project_id: str
    created: str
    stringency_version: str
    method: MethodRef
    pipeline: str | None  # None in open mode: the topology grows one step at a time
    mode: Mode = "pipeline"
    domain: str | None = None  # open mode: the plugin the tools belong to (design 2.2)
    profile: Profile = "standard"
    roles: Roles
    judgment_harness: JudgmentHarness = "subagent"
    judgment: JudgmentSetting = Field(default_factory=JudgmentSetting)  # the harness's settings
    execution: Runner = "operator"
    executor: ExecutorKind = "apptainer"
    policy: str = "method/policy.yml"
    splits: dict[str, Any] | None = None
    declarations: Declarations | None = None
    plugins: dict[str, str] = Field(default_factory=dict)  # installed at init, by name (L29)
    egress: EgressSetting = Field(default_factory=EgressSetting)  # the person's ceiling (L1)
    # the study this project opts into (confirm once, L67): siblings naming the same study
    # under the same parent directory share one design acceptance and one parameter acceptance
    study: str | None = None

    @model_validator(mode="after")
    def _refuse_open_strict(self) -> StringencyConfig:
        """Design 2.2: `open` is refused with `strict`; an open project binds no pipeline and
        names its domain; `staged` stays reserved (open_mode_plan.md 2.1, 2026-10-16)."""
        if self.mode == "open" and self.profile == "strict":
            raise ValueError("mode open with profile strict is refused")
        if self.mode == "staged":
            raise ValueError("mode staged is reserved")
        if self.mode == "open":
            if self.pipeline is not None:
                raise ValueError("mode open binds no pipeline; its tools are the method's modules")
            if not self.domain:
                raise ValueError("mode open needs domain (the plugin the tools belong to)")
        elif self.pipeline is None:
            raise ValueError("mode pipeline needs a pipeline")
        return self


class DerivedFrom(Strict):
    """An input that is a delivered artifact of an earlier stringency run (chained projects).
    `init` verifies it against the sidecar beside the file."""

    run_id: str
    step_id: str | None = None
    output: str | None = None
    project: str | None = None  # informational: where the upstream project lives


class UpstreamInput(Strict):
    """An input the upstream pipeline project itself declared, bound read-only beside its
    delivery in an open project (2026-10-19), so a question can reach the data before the
    pipeline ran. `init` verifies it against the upstream's `inputs.yml`."""

    project: str
    input: str  # its name in the upstream's inputs.yml


class InputItem(Strict):
    name: str
    path: str
    type: str
    blake3: str
    source: str | None = None
    build: str | None = None  # reference build, checked by init.reference_mismatch
    derived_from: DerivedFrom | None = None
    upstream_input: UpstreamInput | None = None
    # `reference`: the input describes other studies' observations (a table of earlier punches,
    # an atlas), not this design's; init.column_missing does not require the design columns in it
    role: Literal["observation", "reference"] = "observation"


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
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """Parameters declared before the run, by step (design 2.5, 2026-10-14): `init` checks each
    against the pipeline and the module schema, the echo-back lists them, and a step takes them
    with `param_source: declared`, so no `param.agent_proposed` hold opens for them."""

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
