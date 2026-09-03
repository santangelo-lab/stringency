"""`.nextflow.log`: the Nextflow version, launch line and revision, and any container
mentions. Recorded for the trace; nothing here is trusted for verification alone."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stringency.operator_exec.evidence import Observed

VERSION = re.compile(r"version\s+(\d+\.\d+\.\d+)")
LAUNCH = re.compile(r"Launching\s+`([^`]+)`\s+\[([^\]]+)\](?:.*?revision:\s*(\S+))?")
CONTAINER = re.compile(
    r"(?:container|image)\W+(\S+\.sif|docker://\S+|\S+@sha256:[0-9a-f]{64})", re.IGNORECASE
)
SHA = re.compile(r"sha256:([0-9a-f]{64})")
CMDLINE = re.compile(r"\$>\s*nextflow\s+run\s+(.*)$", re.MULTILINE)
CLI_PARAM = re.compile(r"--([A-Za-z_][A-Za-z0-9_.-]*)(?:[=\s]+(?!--)(\S+))?")


def parse(text: str) -> Observed:
    from stringency.operator_exec.evidence import Observed

    obs = Observed()
    m = VERSION.search(text)
    if m:
        obs.notes.append(f"nextflow {m.group(1)}")
    m = CMDLINE.search(text)
    if m:
        from stringency.operator_exec.evidence.job_log import coerce

        for k, v in CLI_PARAM.findall(m.group(1)):
            obs.params[k] = coerce(v) if v else True
    m = LAUNCH.search(text)
    if m:
        obs.notes.append(
            f"launched {m.group(1)} run {m.group(2)}"
            + (f" revision {m.group(3)}" if m.group(3) else "")
        )
    for m in CONTAINER.finditer(text):
        c = m.group(1).rstrip("',;")
        if c not in obs.containers:
            obs.containers.append(c)
        s = SHA.search(c)
        if s and not obs.container_digest:
            obs.container_digest = s.group(1)
    return obs
