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
    # bound read-only (design 10.3, 2026-10-14): the project's method checkout, so a module
    # reaches the shared code beside the modules; a read-write bind nested under one is dropped
    ro_bind_paths: Sequence[Path] = ()
    stdin_json: Mapping[str, Any] | None = None
    timeout: float | None = None
    # the step's allocation (L130): {cpus, memory_gb, timeout_s}; the executor sets the
    # environment from it (`resources.env_for`) and, under apptainer, the cgroup limits
    resources: Mapping[str, Any] = field(default_factory=dict)
    stdout_path: Path | None = None
    stderr_path: Path | None = None
    # `none`: isolate the container's network when the host allows it (open mode `exec`,
    # open_mode_plan.md 2.4); None: the executor's default
    network: str | None = None


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout_path: Path
    stderr_path: Path
    duration_ms: int
    env_digest: str | None
    command: str
    timed_out: bool = False
    # what became of a `network: none` request: `none` (enforced) | `unenforced` | None (not asked)
    network: str | None = None

    def stdout(self) -> str:
        return self.stdout_path.read_text() if self.stdout_path.exists() else ""

    def stderr(self) -> str:
        return self.stderr_path.read_text() if self.stderr_path.exists() else ""


class Executor(Protocol):
    kind: str

    def env_digest(self, env_name: str) -> str | None:
        """The environment digest for `env_name`, or None when it cannot be reported."""
        ...

    def command_line(self, job: Job) -> list[str]:
        """The argv this executor would run for `job`, so a ticket can print it verbatim."""
        ...

    def limits_for(self, job: Job) -> str:
        """Whether the job's CPUs and memory are enforced as cgroup limits (L130): `applied`,
        `unavailable` (asked for and the host cannot), or `not_used` (the executor sets none,
        or the job has no CPUs or memory)."""
        ...

    def run(self, job: Job) -> ExecResult: ...
