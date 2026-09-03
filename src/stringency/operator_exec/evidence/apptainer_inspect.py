"""`apptainer inspect` output, JSON (`--json`) or `key: value` text. Recovers labels and any
sha256 digest among them."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from stringency.operator_exec.evidence import Observed

SHA = re.compile(r"sha256:([0-9a-f]{64})|\b([0-9a-f]{64})\b")


def _labels_from_json(data: Any) -> dict[str, str]:
    try:
        labels = data["data"]["attributes"]["labels"]
    except (KeyError, TypeError):
        labels = data if isinstance(data, dict) else {}
    return {str(k): str(v) for k, v in labels.items()} if isinstance(labels, dict) else {}


def parse(text: str) -> Observed:
    from stringency.operator_exec.evidence import Observed

    obs = Observed()
    labels: dict[str, str] = {}
    try:
        labels = _labels_from_json(json.loads(text))
    except json.JSONDecodeError:
        for line in text.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                labels[k.strip()] = v.strip()
    for k, v in labels.items():
        m = SHA.search(v)
        if m and not obs.container_digest:
            obs.container_digest = m.group(1) or m.group(2)
        if k.lower().endswith(("ref.name", "image", "name")) or "container" in k.lower():
            obs.containers.append(v)
    obs.notes.append(f"apptainer inspect: {len(labels)} labels")
    obs.processes.append({"labels": labels})
    return obs
