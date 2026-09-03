"""Executor protocol, Job, ExecResult (design 10.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Job:
    command: Sequence[str]
    env_name: str
    cwd: Path
    bind_paths: Sequence[Path] = ()
    stdin_json: Mapping[str, Any] | None = None
    timeout: float | None = None
    resources: Mapping[str, Any] = field(default_factory=dict)
    stdout_path: Path | None = None
    stderr_path: Path | None = None


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout_path: Path
    stderr_path: Path
    duration_ms: int
    env_digest: str | None
    command: str
    timed_out: bool = False

    def stdout(self) -> str:
        return self.stdout_path.read_text() if self.stdout_path.exists() else ""

    def stderr(self) -> str:
        return self.stderr_path.read_text() if self.stderr_path.exists() else ""


class Executor(Protocol):
    kind: str

    def env_digest(self, env_name: str) -> str | None:
        """The environment digest for `env_name`, or None when it cannot be reported."""
        ...

    def run(self, job: Job) -> ExecResult: ...
