"""Pipeline topology model (design 3.1): steps, `$inputs`/`$steps` references, DAG order,
parameter declarations with defaults and ranges."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency.config import Runner, load_yaml
from stringency.exit_codes import ConfigError
from stringency.modules import parse_module_ref

REF = re.compile(
    r"^\$(?P<kind>inputs|steps)\.(?P<a>[A-Za-z0-9_.*-]+?)(?:\.(?P<b>[A-Za-z0-9_*-]+))?$"
)


class Ref(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: str  # inputs | steps
    name: str  # input name, or step id
    output: str | None = None  # output name for steps

    @classmethod
    def parse(cls, text: str) -> Ref:
        m = REF.match(text)
        if not m:
            raise ConfigError(
                f"bad reference {text!r}; expected $inputs.<name> or $steps.<id>.<out>"
            )
        kind, a, b = m.group("kind"), m.group("a"), m.group("b")
        if kind == "inputs":
            if b is not None:
                # $inputs.name has no output part; the regex may have split a dotted name
                a = f"{a}.{b}"
            return cls(kind="inputs", name=a)
        if b is None:
            raise ConfigError(f"bad reference {text!r}; $steps needs <id>.<output>")
        if "*" in a or "*" in b:
            raise ConfigError(f"bad reference {text!r}; a glob binds $inputs only")
        return cls(kind="steps", name=a, output=b)

    @property
    def pattern(self) -> bool:
        """`$inputs.<glob>`: every manifest input whose name matches, for an `arity: many`
        input (3.1, 2026-09-23)."""
        return self.kind == "inputs" and "*" in self.name

    def __str__(self) -> str:
        return f"${self.kind}.{self.name}" + (f".{self.output}" if self.output else "")


class ParamDecl(BaseModel):
    """`{default, range}` or `{default, options}` or `{default}` (fixed).
    A bare literal in the pipeline file is normalised to `{default: literal}`."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    default: Any
    range: list[float] | None = None
    options: list[Any] | None = None

    @model_validator(mode="after")
    def _shape(self) -> ParamDecl:
        if self.range is not None and self.options is not None:
            raise ValueError("a parameter declares range or options, not both")
        if self.range is not None and len(self.range) != 2:
            raise ValueError("range is [low, high]")
        return self

    @property
    def fixed(self) -> bool:
        return self.range is None and self.options is None

    def in_range(self, value: Any) -> bool:
        if self.range is not None:
            try:
                return self.range[0] <= float(value) <= self.range[1]
            except (TypeError, ValueError):
                return False
        if self.options is not None:
            return value in self.options
        return bool(value == self.default)


class StepDecl(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    module: str
    title: str | None = None  # plain phrase for a lay reader ("Filter low-count genes")
    # one reference, or for an `arity: many` module input a list of references or a
    # `$inputs.<glob>` (3.1, 2026-09-23)
    inputs: dict[str, str | list[str]] = Field(default_factory=dict)
    params: dict[str, ParamDecl] = Field(default_factory=dict)
    runner: Runner | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise_params(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("params"), dict):
            out: dict[str, Any] = {}
            for k, v in data["params"].items():
                if isinstance(v, dict) and "default" in v:
                    out[k] = v
                else:
                    out[k] = {"default": v}
            data = {**data, "params": out}
        return data

    @property
    def module_name(self) -> str:
        return parse_module_ref(self.module)[0]

    @property
    def module_version(self) -> str:
        return parse_module_ref(self.module)[1]

    def refs(self) -> dict[str, list[Ref]]:
        """Each wired input's references, one for a single binding, several for a list."""
        return {
            k: [Ref.parse(x) for x in (v if isinstance(v, list) else [v])]
            for k, v in self.inputs.items()
        }

    def is_list(self, name: str) -> bool:
        return isinstance(self.inputs.get(name), list)

    def predecessors(self) -> list[str]:
        seen: list[str] = []
        for rs in self.refs().values():
            for r in rs:
                if r.kind == "steps" and r.name not in seen:
                    seen.append(r.name)
        return seen

    def defaults(self) -> dict[str, Any]:
        return {k: v.default for k, v in self.params.items()}


class Pipeline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pipeline: int
    name: str
    version: str
    domain: str
    answers: list[str] = Field(default_factory=list)
    reference_build: str | None = None
    steps: list[StepDecl]

    @model_validator(mode="after")
    def _validate(self) -> Pipeline:
        if self.pipeline != 1:
            raise ValueError(f"pipeline must be 1, got {self.pipeline}")
        ids = [s.id for s in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError("step ids must be unique")
        known = set(ids)
        for s in self.steps:
            for pred in s.predecessors():
                if pred not in known:
                    raise ValueError(f"step {s.id} references unknown step {pred}")
        self._order()  # raises on cycles
        return self

    def step(self, step_id: str) -> StepDecl:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise ConfigError(f"no step {step_id} in pipeline {self.name}")

    def has_step(self, step_id: str) -> bool:
        return any(s.id == step_id for s in self.steps)

    def title(self, step_id: str) -> str:
        """The step's plain title, or its id when the pipeline declares none."""
        for s in self.steps:
            if s.id == step_id:
                return s.title or s.id
        return step_id

    def untitled(self) -> list[str]:
        return [s.id for s in self.steps if not s.title]

    def _order(self) -> list[str]:
        """Topological order; file order breaks ties (design 3.1)."""
        index = {s.id: i for i, s in enumerate(self.steps)}
        preds = {s.id: set(s.predecessors()) for s in self.steps}
        done: list[str] = []
        remaining = set(index)
        while remaining:
            ready = sorted((s for s in remaining if preds[s] <= set(done)), key=lambda s: index[s])
            if not ready:
                raise ValueError(f"cycle among steps {sorted(remaining)}")
            done.append(ready[0])
            remaining.remove(ready[0])
        return done

    def order(self) -> list[str]:
        return self._order()

    def successors(self, step_id: str) -> list[str]:
        return [s.id for s in self.steps if step_id in s.predecessors()]

    def downstream(self, step_id: str) -> list[str]:
        out: list[str] = []
        frontier = [step_id]
        while frontier:
            cur = frontier.pop()
            for s in self.successors(cur):
                if s not in out:
                    out.append(s)
                    frontier.append(s)
        return [s for s in self.order() if s in out]

    def consumers_of_object_output(self, step_id: str) -> list[str]:
        return self.successors(step_id)


def load_pipeline(path: Path) -> Pipeline:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping")
    try:
        return Pipeline.model_validate(data)
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None


def find_pipeline(method_root: Path, name: str) -> Path:
    for cand in (
        method_root / "pipelines" / f"{name}.yml",
        method_root / "pipelines" / f"{name}.yaml",
    ):
        if cand.exists():
            return cand
    raise ConfigError(f"no pipeline named {name} under {method_root / 'pipelines'}")
