"""Evidence parsers. Each returns an `Observed` record; anything a parser cannot recover is
left None, never guessed (design 10.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.operator_exec.evidence import (
    apptainer_inspect,
    job_log,
    nextflow_log,
    nextflow_trace,
)


@dataclass
class Observed:
    params: dict[str, Any] = field(default_factory=dict)
    seed: Any = None
    containers: list[str] = field(default_factory=list)  # image names or paths seen
    container_digest: str | None = None  # sha256 digest if any evidence carried one
    exit_codes: list[int] = field(default_factory=list)
    processes: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)

    def merge(self, other: Observed) -> None:
        self.params.update(other.params)
        if other.seed is not None:
            self.seed = other.seed
        for c in other.containers:
            if c not in self.containers:
                self.containers.append(c)
        if other.container_digest and not self.container_digest:
            self.container_digest = other.container_digest
        self.exit_codes += other.exit_codes
        self.processes += other.processes
        self.notes += other.notes
        self.kinds += other.kinds

    def to_json(self) -> dict[str, Any]:
        return {
            "params": self.params,
            "seed": self.seed,
            "containers": self.containers,
            "container_digest": self.container_digest,
            "exit_codes": self.exit_codes,
            "processes": self.processes,
            "notes": self.notes,
            "kinds": self.kinds,
        }


PARSERS = {
    "job_log": job_log.parse,
    "nextflow_trace": nextflow_trace.parse,
    "nextflow_log": nextflow_log.parse,
    "apptainer_inspect": apptainer_inspect.parse,
}


def parse_evidence(kind: str, path: Path) -> Observed:
    if kind not in PARSERS:
        raise ValueError(f"no evidence parser for kind {kind}")
    text = path.read_text(errors="replace")
    result = PARSERS[kind](text)
    result.kinds.append(kind)
    return result


def guess_kind(path: Path) -> str:
    name = path.name
    if name.startswith("trace") and name.endswith(".txt"):
        return "nextflow_trace"
    if name == ".nextflow.log" or name.endswith(".nextflow.log"):
        return "nextflow_log"
    if "inspect" in name:
        return "apptainer_inspect"
    return "job_log"
