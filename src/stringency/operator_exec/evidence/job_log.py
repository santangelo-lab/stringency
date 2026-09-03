"""Free-text job log. Recovers `params: k=v ...`, `seed: N`, `container: <ref>`, and
`exit code: N` lines where a script printed them; records nothing else."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from stringency.operator_exec.evidence import Observed

PARAMS = re.compile(r"^\s*params:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
KV = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)=(\S+)")
SEED = re.compile(r"^\s*seed:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
CONTAINER = re.compile(r"^\s*(?:container|image):\s*(\S+)", re.IGNORECASE | re.MULTILINE)
EXIT = re.compile(r"^\s*exit(?:\s*code)?:\s*(\d+)", re.IGNORECASE | re.MULTILINE)
SHA = re.compile(r"sha256:([0-9a-f]{64})")


def coerce(v: str) -> Any:
    low = v.lower()
    if low in {"true", "false"}:
        return low == "true"
    if low in {"none", "null"}:
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def parse(text: str) -> Observed:
    from stringency.operator_exec.evidence import Observed

    obs = Observed()
    for m in PARAMS.finditer(text):
        for k, v in KV.findall(m.group(1)):
            obs.params[k] = coerce(v)
    seed = SEED.search(text)
    if seed:
        obs.seed = coerce(seed.group(1))
    for c in CONTAINER.finditer(text):
        obs.containers.append(c.group(1))
        sha = SHA.search(c.group(1))
        if sha and not obs.container_digest:
            obs.container_digest = sha.group(1)
    for e in EXIT.finditer(text):
        obs.exit_codes.append(int(e.group(1)))
    return obs
