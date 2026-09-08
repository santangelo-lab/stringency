"""`apptainer inspect` output, JSON (`--json`) or `key: value` text, optionally followed by a
`sha256sum <image>` line as the ticket's evidence command produces. Recovers labels, any sha256
digest among them, and the digest and path from the checksum line. A pulled image's labels carry
no digest of the SIF itself, which is why the checksum line is there."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from stringency.operator_exec.evidence import Observed

SHA = re.compile(r"sha256:([0-9a-f]{64})|\b([0-9a-f]{64})\b")
CHECKSUM_LINE = re.compile(r"^\s*([0-9a-f]{64})\s+\*?(\S.*?)\s*$", re.MULTILINE)


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
    rest = text
    start = text.find("{")
    if start >= 0:
        try:
            data, end = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            data, end = None, 0
        if data is not None:
            labels = _labels_from_json(data)
            rest = text[:start] + text[start + end :]
    if not labels:
        for line in rest.splitlines():
            if ":" in line and not CHECKSUM_LINE.match(line):
                k, _, v = line.partition(":")
                labels[k.strip()] = v.strip()
    for cm in CHECKSUM_LINE.finditer(rest):
        if not obs.container_digest:
            obs.container_digest = cm.group(1)
        obs.containers.append(cm.group(2))
    for k, v in labels.items():
        m = SHA.search(v)
        if m and not obs.container_digest:
            obs.container_digest = m.group(1) or m.group(2)
        if k.lower().endswith(("ref.name", "image", "name")) or "container" in k.lower():
            obs.containers.append(v)
    obs.notes.append(f"apptainer inspect: {len(labels)} labels")
    obs.processes.append({"labels": labels})
    return obs
