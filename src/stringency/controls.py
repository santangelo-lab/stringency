"""Controls (design 11): the `controls/*.yml` model. Execution is filled in at M10."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency.config import load_yaml
from stringency.exit_codes import ConfigError

ControlKind = Literal["negative", "positive", "planted"]


class FixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: str
    blake3: str
    path: str | None = None


class FixtureTruth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    key: str
    column: str
    mapping: str | None = None


class Fixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input: FixtureInput
    truth: FixtureTruth | None = None


class Generator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class ControlSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    control: int
    name: str
    kind: ControlKind
    fixture: Fixture
    generator: Generator | None = None
    expect: dict[str, Any]

    @model_validator(mode="after")
    def _check(self) -> ControlSpec:
        if self.control != 1:
            raise ValueError("control must be 1")
        if self.kind == "positive" and self.fixture.truth is None:
            raise ValueError("a positive control needs fixture.truth")
        if self.kind in ("negative", "planted") and self.generator is None:
            raise ValueError(f"a {self.kind} control needs a generator")
        return self


def load_control(path: Path) -> ControlSpec:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping")
    try:
        return ControlSpec.model_validate(data)
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None
