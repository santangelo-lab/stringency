"""Apptainer executor (design 10.3). Filled in at M11.

`apptainer exec --containall --bind <paths> <image.sif> <command>`; `env_digest` is the SIF
digest from the environment manifest, verified against the file at run open.
"""

from __future__ import annotations

from pathlib import Path

from stringency.executor.base import ExecResult, Job
from stringency.exit_codes import ConfigError


class ApptainerExecutor:
    kind = "apptainer"

    def __init__(self, envs_root: Path) -> None:
        self.envs_root = envs_root

    def env_digest(self, env_name: str) -> str | None:
        raise ConfigError("apptainer executor is not implemented yet (M11)")

    def run(self, job: Job) -> ExecResult:
        raise ConfigError("apptainer executor is not implemented yet (M11)")
