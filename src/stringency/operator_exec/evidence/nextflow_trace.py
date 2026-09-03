"""Nextflow trace file (`-with-trace`): TSV with a header. Recovers per-process name, status,
exit code, and container when the `container` field was enabled."""

from __future__ import annotations

import csv
import io
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stringency.operator_exec.evidence import Observed

SHA = re.compile(r"sha256:([0-9a-f]{64})")


def parse(text: str) -> Observed:
    from stringency.operator_exec.evidence import Observed

    obs = Observed()
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if not reader.fieldnames or "status" not in reader.fieldnames:
        obs.notes.append("not a Nextflow trace: no status column")
        return obs
    has_container = "container" in reader.fieldnames
    if not has_container:
        obs.notes.append("trace has no container column")
    for row in reader:
        proc = {
            "name": row.get("name") or row.get("process"),
            "process": row.get("process") or (row.get("name") or "").split(" (")[0],
            "status": row.get("status"),
            "exit": row.get("exit"),
            "container": row.get("container") if has_container else None,
            "hash": row.get("hash"),
        }
        obs.processes.append(proc)
        try:
            if row.get("exit") not in (None, "", "-"):
                obs.exit_codes.append(int(row["exit"]))
        except ValueError:
            pass
        c = proc["container"]
        if c and c != "-" and c not in obs.containers:
            obs.containers.append(c)
            m = SHA.search(c)
            if m and not obs.container_digest:
                obs.container_digest = m.group(1)
    return obs
