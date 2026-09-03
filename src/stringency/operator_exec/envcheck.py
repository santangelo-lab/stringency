"""Match reported container evidence to the environment manifest (design 10.3).

`envs/manifest.yml`: `environments: {<env>: {lock, image, sha256}}`. A reported container is
verified when its digest equals the manifest's sha256 for the module's env, or its image path or
name equals the manifest's image. Anything else is `as_reported`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from stringency.operator_exec.evidence import Observed


def load_env_manifest(envs_root: Path) -> dict[str, dict[str, Any]]:
    p = envs_root / "manifest.yml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    envs = data.get("environments", {}) if isinstance(data, dict) else {}
    return {str(k): dict(v or {}) for k, v in envs.items()} if isinstance(envs, dict) else {}


def env_status(observed: Observed, env_name: str, envs_root: Path) -> str:
    """`verified` or `as_reported`."""
    entry = load_env_manifest(envs_root).get(env_name, {})
    want_sha = entry.get("sha256")
    want_image = entry.get("image")
    if (
        want_sha
        and observed.container_digest
        and observed.container_digest == str(want_sha).removeprefix("sha256:")
    ):
        return "verified"
    if want_image:
        for c in observed.containers:
            if c == want_image or Path(c).name == Path(str(want_image)).name:
                return "verified"
    return "as_reported"
