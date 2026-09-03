"""Anthropic Messages API adapter (design 10.2). Filled in at M11; installed as `stringency[api]`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from stringency.exit_codes import ConfigError
from stringency.harness.base import Family, Invocation, Request, Sampling


class ApiHarness:
    kind = "api"
    version = "0"
    family: Family = "direct"

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        raise ConfigError("api harness is not implemented yet (M11)")

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        raise NotImplementedError

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        raise NotImplementedError
