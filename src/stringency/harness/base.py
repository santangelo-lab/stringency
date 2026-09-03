"""Harness protocol, both families (design 10.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

Family = Literal["direct", "dispatch"]


@dataclass(frozen=True)
class Sampling:
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens}


@dataclass(frozen=True)
class Request:
    replicate: int
    nonce: str
    prompt: str
    schema: dict[str, Any]
    items: tuple[str, ...]
    module: str
    template_ref: str
    # in-memory only; never written to a request file. The mock reads cell values from it.
    evidence: Mapping[str, Mapping[str, Mapping[str, Any]]] = field(default_factory=dict)
    item_index: int | None = None  # per_item batching: which item this request is for


@dataclass
class Invocation:
    structured: dict[str, Any] | None
    raw_text: str
    schema_valid: bool
    model_requested: str | None
    model_resolved: str
    harness_kind: str
    harness_version: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    duration_ms: int | None = None
    via: str = "direct"  # direct | subagent
    isolation: str = "enforced"  # enforced | as_reported
    nonce_ok: bool | None = None
    tool_calls: list[Any] = field(default_factory=list)
    reported: dict[str, Any] | None = None
    request_path: str | None = None
    response_path: str | None = None
    error: str | None = None


class Harness(Protocol):
    kind: str
    version: str
    family: Family

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation: ...

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None: ...

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]: ...


def unknown(value: Any) -> Any:
    """Anything an adapter cannot report is recorded as `unknown`, never guessed."""
    return "unknown" if value is None else value
