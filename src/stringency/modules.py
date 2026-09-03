"""Module manifest model and loading (design 3.2). The contract is frozen at v1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency.config import Runner, load_yaml
from stringency.exit_codes import ConfigError

Kind = Literal["deterministic", "judgment", "report"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IOSpec(Frozen):
    type: str
    format: str | None = None
    hash: bool = True
    schema_: str | None = Field(default=None, alias="schema")
    item_key: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class JudgmentSpec(Frozen):
    items_from: str
    item_key: str
    evidence: list[str]
    batching: Literal["all_items", "per_item"] = "all_items"
    replicates: int = 3
    abstain: Literal["required", "optional"] = "required"
    confidence: Literal["ordinal"] = "ordinal"
    considered_set: bool = False


class PromptSpec(Frozen):
    template: str = "prompt.md"
    vars: list[str] = Field(default_factory=list)


class ControlsSpec(Frozen):
    required: list[str] = Field(default_factory=list)


class EvidenceSpec(Frozen):
    kind: Literal["nextflow_trace", "nextflow_log", "apptainer_inspect", "job_log"]
    path: str


class Resources(Frozen):
    cpus: int | None = None
    memory: str | None = None
    timeout: str | None = None


class ModuleManifest(Frozen):
    contract: int
    name: str
    version: str
    kind: Kind
    operation: str
    domain: str
    modes: list[str] = Field(default_factory=lambda: ["pipeline"])
    env: str
    runner: Runner | None = None
    entry: str | None = None
    post: str | None = None
    inputs: dict[str, IOSpec] = Field(default_factory=dict)
    outputs: dict[str, IOSpec] = Field(default_factory=dict)
    decision_points: list[str] = Field(default_factory=list)
    stochastic: bool = False
    seed_param: str | None = None
    judgment: JudgmentSpec | None = None
    prompt: PromptSpec | None = None
    vocabulary: str | None = None
    gates: list[str] = Field(default_factory=list)
    controls: ControlsSpec = Field(default_factory=ControlsSpec)
    resources: Resources = Field(default_factory=Resources)
    evidence: list[EvidenceSpec] = Field(default_factory=list)
    confirm: bool = False
    model: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"

    @model_validator(mode="after")
    def _shape(self) -> ModuleManifest:
        if self.contract != 1:
            raise ValueError(f"contract must be 1, got {self.contract}")
        if self.stochastic and not self.seed_param:
            raise ValueError("stochastic: true requires seed_param")
        return self


MODULE_REF = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)@(?P<version>[A-Za-z0-9_.+-]+)$")


def parse_module_ref(ref: str) -> tuple[str, str]:
    m = MODULE_REF.match(ref)
    if not m:
        raise ConfigError(f"module reference must be name@version: {ref}")
    return m.group("name"), m.group("version")


class Module:
    """A module directory: manifest plus the files it names, loaded once."""

    def __init__(self, path: Path, manifest: ModuleManifest) -> None:
        self.path = path
        self.manifest = manifest
        self._params_schema: dict[str, Any] | None = None
        self._output_schema: dict[str, Any] | None = None

    @property
    def ref(self) -> str:
        return self.manifest.ref

    @property
    def params_schema(self) -> dict[str, Any]:
        if self._params_schema is None:
            p = self.path / "params.schema.json"
            if p.exists():
                self._params_schema = _load_json(p)
            else:
                self._params_schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                }
        return self._params_schema

    @property
    def declared_params(self) -> dict[str, Any]:
        props = self.params_schema.get("properties", {})
        return dict(props) if isinstance(props, dict) else {}

    @property
    def output_schema(self) -> dict[str, Any] | None:
        if self._output_schema is None:
            p = self.path / "schema.json"
            if p.exists():
                self._output_schema = _load_json(p)
        return self._output_schema

    def output_schema_for(self, output_name: str) -> dict[str, Any] | None:
        spec = self.manifest.outputs.get(output_name)
        if spec is None or spec.schema_ is None:
            return None
        return _load_json(self.path / spec.schema_)

    @property
    def prompt_template(self) -> str | None:
        if self.manifest.prompt is None:
            return None
        p = self.path / self.manifest.prompt.template
        return p.read_text() if p.exists() else None

    @property
    def entry_script(self) -> Path | None:
        """The `pre.*` script, or whatever `entry:` names."""
        if self.manifest.entry:
            return self.path / self.manifest.entry
        for cand in sorted(self.path.glob("pre.*")):
            return cand
        return None

    @property
    def post_script(self) -> Path | None:
        if self.manifest.post:
            return self.path / self.manifest.post
        for cand in sorted(self.path.glob("post.*")):
            return cand
        return None

    def control_files(self) -> list[Path]:
        return sorted((self.path / "controls").glob("*.yml"))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"missing file: {path}") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path}: invalid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a JSON object")
    return data


def load_module(path: Path) -> Module:
    data = load_yaml(path / "module.yml")
    if not isinstance(data, dict):
        raise ConfigError(f"{path / 'module.yml'}: expected a mapping")
    try:
        manifest = ModuleManifest.model_validate(data)
    except ValueError as e:
        raise ConfigError(f"{path / 'module.yml'}: {e}") from None
    return Module(path, manifest)


class ModuleIndex:
    """Modules of a method repo, by `name@version`. One directory per name under modules/."""

    def __init__(self, method_root: Path) -> None:
        self.root = method_root / "modules"
        self._by_ref: dict[str, Module] = {}
        self._by_name: dict[str, Module] = {}
        if self.root.exists():
            for d in sorted(p for p in self.root.iterdir() if (p / "module.yml").exists()):
                m = load_module(d)
                self._by_ref[m.ref] = m
                self._by_name[m.manifest.name] = m

    def get(self, ref: str) -> Module | None:
        return self._by_ref.get(ref)

    def by_name(self, name: str) -> Module | None:
        return self._by_name.get(name)

    def all(self) -> list[Module]:
        return list(self._by_ref.values())

    def require(self, ref: str) -> Module:
        m = self.get(ref)
        if m is None:
            name, version = parse_module_ref(ref)
            have = self.by_name(name)
            if have is not None:
                raise ConfigError(
                    f"module {name} is at version {have.manifest.version} in the method repo; "
                    f"the pipeline asks for {version}"
                )
            raise ConfigError(f"module {ref} is not in the method repo")
        return m
