"""Match reported container evidence to the environment manifest (design 10.3).

`envs/manifest.yml`: `environments: {<env>: {lock, image, sha256}}`. A reported container is
verified when its digest equals the manifest's sha256 for the module's env, or, when no digest
was reported, its image path or name equals the manifest's image. A reported digest that
disagrees is `as_reported` whatever the name says. Anything else is `as_reported`."""

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
    want_sha = str(entry.get("sha256") or "").removeprefix("sha256:") or None
    want_image = entry.get("image")
    if want_sha and observed.container_digest:
        # a reported digest settles it either way; a matching image name cannot outvote it
        return "verified" if observed.container_digest == want_sha else "as_reported"
    if want_image:
        for c in observed.containers:
            if c == want_image or Path(c).name == Path(str(want_image)).name:
                return "verified"
    return "as_reported"
