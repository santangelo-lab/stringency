"""Data egress: what a project's setup sends off the machine, by class (backlog L1;
`spec/plans/egress-and-remeasurement.md` part 1).

The assessment reads the bound configuration, the pipeline's steps, and each module's
manifest and script files. It writes nothing; the report it renders is saved by init and by
run open (`prov/egress.md`, `prov/egress.json`), and its fingerprint binds the project-level
`egress` hold. Classes run from 0 (nothing leaves) to 4 (project data sent whole). The
assessed class is the highest of any component; it exceeds the ceiling the person set at init
when it is greater than `max_class`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from stringency import hashing

if TYPE_CHECKING:
    from stringency.modules import Module, ModuleManifest
    from stringency.pipelines import StepDecl

OperatorModel = Literal["hosted", "local", "none"]

CLASS_NAMES: dict[int, str] = {0: "none", 1: "reference", 2: "terms", 3: "derived", 4: "data"}

CLASS_SENTENCES: dict[int, str] = {
    0: "nothing leaves this machine",
    1: "public reference data is downloaded; nothing from the project is sent",
    2: "names or identifiers from the project are sent as queries",
    3: "values computed from the project's data are sent",
    4: "the project's data, or whatever the operator reads, may be sent whole",
}

NOT_ASSESSED = (
    "not assessed: what the operator reads into its session beyond tickets, hold packets and "
    "present output; network use the script scan cannot see (a library that connects on its "
    "own, a host named at run time); anything not listed above"
)

HARNESS_CLASS: dict[str, tuple[int, str, str]] = {
    # kind -> (class, where to, what is sent)
    "mock": (0, "nowhere (recorded fixtures)", "nothing"),
    "api": (
        3,
        "Anthropic's API",
        "the rendered judgment prompt: evidence tables, vocabulary, objective and design",
    ),
    "subagent": (
        3,
        "the operator's model, through its session (as reported)",
        "the rendered judgment prompt: evidence tables, vocabulary, objective and design",
    ),
    "openai-compatible": (
        3,
        "the endpoint the adapter names (no endpoint is declared; assessed as hosted)",
        "the rendered judgment prompt: evidence tables, vocabulary, objective and design",
    ),
}

SCRIPT_SUFFIXES = {".py", ".r", ".sh", ".bash", ".nf", ".jl"}

# Conservative on purpose: a false positive costs one declaration line in module.yml.
NETWORK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(rx))
    for name, rx in (
        ("requests", r"\bimport\s+requests\b|\bfrom\s+requests\b|\brequests\.(get|post|put)\("),
        ("urllib", r"\burllib\.request\b|\burlopen\s*\(|\burlretrieve\s*\("),
        ("httpx", r"\bhttpx\b"),
        ("http.client", r"\bhttp\.client\b"),
        ("socket", r"\bimport\s+socket\b|\bsocket\.socket\s*\("),
        ("ftplib", r"\bftplib\b"),
        ("boto3", r"\bboto3\b"),
        ("model hub", r"\bfrom_pretrained\s*\(|\bhf_hub_download\b|\bsnapshot_download\b"),
        ("LLM client", r"\bimport\s+(anthropic|openai|ollama)\b|\bfrom\s+(anthropic|openai)\b"),
        ("httr", r"\bhttr2?::|\blibrary\(\s*httr2?\s*\)"),
        ("download.file", r"\bdownload\.file\s*\("),
        ("R curl", r"\bcurl::|\bRCurl\b|\blibrary\(\s*curl\s*\)"),
        ("curl", r"(^|[\s;|&(`])curl\s"),
        ("wget", r"(^|[\s;|&(`])wget\s"),
        ("nextflow run", r"\bnextflow\s+run\b"),
        ("cloud copy", r"\baws\s+s3\b|\bgsutil\b|\bazcopy\b"),
        ("remote shell", r"(^|[\s;|&(`])(scp|ssh|sftp)\s"),
        # an XML namespace (xmlns="http://www.w3.org/2000/svg") is a name, not a connection
        ("URL", r"\b(https?|ftp)://(?!www\.w3\.org/)"),
    )
)


@dataclass(frozen=True)
class ScanHit:
    path: str  # relative to the module directory
    line: int
    pattern: str

    def describe(self) -> str:
        return f"{self.path}:{self.line} {self.pattern}"


@dataclass(frozen=True)
class Component:
    """One thing that may send data off the machine, with its class and what it sends."""

    key: str
    label: str
    cls: int
    basis: str  # by construction | as reported | declared | scanned, undeclared
    set_by: str  # project setting | method
    to: str
    sends: str
    steps: tuple[str, ...] = ()
    conditional: tuple[str, ...] = ()  # steps with `when:`, which may not run
    evidence: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "class": self.cls,
            "class_name": CLASS_NAMES[self.cls],
            "basis": self.basis,
            "set_by": self.set_by,
            "to": self.to,
            "sends": self.sends,
            "steps": list(self.steps),
            "conditional": list(self.conditional),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class EgressAssessment:
    components: tuple[Component, ...]
    max_class: int | None
    operator: str
    harness: str
    execution: str
    previous_max_class: int | None = None  # the ceiling on the last acknowledged report
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def assessed_class(self) -> int:
        return max((c.cls for c in self.components), default=0)

    @property
    def over(self) -> tuple[Component, ...]:
        if self.max_class is None:
            return ()
        return tuple(c for c in self.components if c.cls > self.max_class)

    @property
    def within(self) -> bool | None:
        """None when no ceiling was declared."""
        if self.max_class is None:
            return None
        return self.assessed_class <= self.max_class

    @property
    def fingerprint(self) -> str:
        """blake3 over the components and the ceiling; no timestamps, no previous ceiling."""
        return hashing.hash_json(
            {
                "max_class": self.max_class,
                "operator": self.operator,
                "components": [c.to_json() for c in self.components],
            }
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "egress": 1,
            "fingerprint": hashing.prefixed(self.fingerprint),
            "max_class": self.max_class,
            "previous_max_class": self.previous_max_class,
            "operator": self.operator,
            "harness": self.harness,
            "execution": self.execution,
            "assessed_class": self.assessed_class,
            "assessed_class_name": CLASS_NAMES[self.assessed_class],
            "within": self.within,
            "over": [c.key for c in self.over],
            "components": [c.to_json() for c in self.components],
        }

    def summary_line(self) -> str:
        """One line: the assessed class against the ceiling."""
        a = self.assessed_class
        if self.max_class is None:
            return f"data egress: class {a} {CLASS_NAMES[a]}; no ceiling declared"
        word = "within" if self.within else "exceeds"
        m = self.max_class
        return f"data egress: class {a} {CLASS_NAMES[a]}, {word} the ceiling class {m} {CLASS_NAMES[m]}"


# -- scanning ---------------------------------------------------------------------------


def _is_comment(line: str, suffix: str) -> bool:
    s = line.lstrip()
    if suffix in {".py", ".r", ".sh", ".bash", ".jl"}:
        return s.startswith("#")
    if suffix == ".nf":
        return s.startswith("//")
    return False


def scan_text(text: str, suffix: str, rel: str) -> list[ScanHit]:
    """Network-call patterns in one script's text, comment lines skipped. One hit per line."""
    hits: list[ScanHit] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or _is_comment(line, suffix):
            continue
        for name, rx in NETWORK_PATTERNS:
            if rx.search(line):
                hits.append(ScanHit(rel, n, name))
                break
    return hits


def module_scripts(module_dir: Path) -> list[Path]:
    """Every script-like file under the module directory, controls fixtures excluded."""
    out: list[Path] = []
    for p in sorted(module_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SCRIPT_SUFFIXES:
            continue
        if "controls" in p.relative_to(module_dir).parts[:-1]:
            continue
        out.append(p)
    return out


def scan_module(module_dir: Path) -> list[ScanHit]:
    """Reads, read-only: the module's script files. Returns the network-call hits."""
    hits: list[ScanHit] = []
    for p in module_scripts(module_dir):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        hits += scan_text(text, p.suffix.lower(), str(p.relative_to(module_dir)))
    return hits


# -- assessment -------------------------------------------------------------------------


def step_runner(step: StepDecl, manifest: ModuleManifest, execution: str) -> str:
    """Who runs a step: judgment modules are engine-run (design 3.5); otherwise the step's
    `runner:`, the module's, then the project's `execution`. Same rule as `steps.runner_for`."""
    if manifest.kind == "judgment":
        return "engine"
    return step.runner or manifest.runner or execution


def _label(step: StepDecl) -> str:
    return f"{step.id} ({step.title})" if step.title else step.id


def assess(
    *,
    steps: Sequence[StepDecl],
    modules: Mapping[str, Module],
    harness: str,
    execution: str,
    max_class: int | None,
    operator: OperatorModel | str = "hosted",
    previous_max_class: int | None = None,
    scans: Mapping[str, Sequence[ScanHit]] | None = None,
    exec_allowed: bool = False,
    executor: str = "apptainer",
) -> EgressAssessment:
    """Assess what this setup sends off the machine.

    Reads, read-only: each step's module manifest and, unless `scans` is given, the module's
    script files. Writes nothing. Components, in order: the judgment harness (only when a
    judgment step is bound), the operator session, the operator-run steps, then one row per
    module whose scripts reach the network."""
    hosted = operator == "hosted"
    comps: list[Component] = []
    judgment_steps: list[StepDecl] = []
    operator_steps: list[tuple[StepDecl, bool]] = []  # (step, set by the method)
    by_module: dict[str, list[StepDecl]] = {}
    for step in steps:
        mod = modules.get(step.module)
        if mod is None:
            continue
        m = mod.manifest
        by_module.setdefault(m.ref, []).append(step)
        if m.kind == "judgment":
            judgment_steps.append(step)
        elif step_runner(step, m, execution) == "operator":
            operator_steps.append((step, bool(step.runner or m.runner)))

    def _cond(ss: Iterable[StepDecl]) -> tuple[str, ...]:
        return tuple(s.id for s in ss if s.when is not None)

    if judgment_steps:
        cls, to, sends = HARNESS_CLASS.get(harness, (3, f"unknown harness {harness}", "the prompt"))
        comps.append(
            Component(
                key="harness",
                label=f"judgment harness {harness}",
                cls=cls,
                basis="by construction",
                set_by="project setting",
                to=to,
                sends=sends if cls else "nothing",
                steps=tuple(s.id for s in judgment_steps),
                conditional=_cond(judgment_steps),
            )
        )

    comps.append(
        Component(
            key="operator.session",
            label=f"operator session ({operator})",
            cls=3 if hosted else 0,
            basis="as reported",
            set_by="project setting",
            to="the operator's model, through its session" if hosted else "nowhere",
            sends=(
                "hold packets (evidence lines, replicate calls), present output and delivery "
                "summaries the operator reads to relay them"
                if hosted
                else "nothing; the project is operated without a hosted model"
            ),
        )
    )

    if operator_steps:
        ss = [s for s, _ in operator_steps]
        comps.append(
            Component(
                key="operator.steps",
                label="operator-run steps",
                cls=4 if hosted else 0,
                basis="as reported",
                set_by="method" if all(by for _, by in operator_steps) else "project setting",
                to="the operator's model, through its session" if hosted else "nowhere",
                sends=(
                    "whatever the operator reads while running the ticket: commands, logs, "
                    "and any input or output it opens"
                    if hosted
                    else "nothing; the steps are run without a hosted model"
                ),
                steps=tuple(_label(s) for s in ss),
                conditional=_cond(ss),
            )
        )

    for ref, ss in by_module.items():
        mod = modules[ss[0].module]
        hits = list(scans[ref]) if scans is not None and ref in scans else scan_module(mod.path)
        if not hits:
            continue
        comps.append(
            Component(
                key=f"module:{ref}",
                label=f"module {ref}",
                cls=4,
                basis="scanned, undeclared",
                set_by="method",
                to="not declared",
                sends="not declared; the module's scripts reach the network and module.yml "
                "declares no egress, so it is counted as class 4",
                steps=tuple(_label(s) for s in ss),
                conditional=_cond(ss),
                evidence=tuple(h.describe() for h in hits),
            )
        )

    if exec_allowed:
        # open mode (backlog L40): a script the operator writes in the session runs under the
        # executor; the container runs it with no network, the local executor with the host's
        iso = executor == "apptainer"
        comps.append(
            Component(
                key="exec",
                label="session scripts (exec)",
                cls=0 if iso else 4,
                basis="by enforcement" if iso else "as reported",
                set_by="project setting",
                to="nowhere; the container runs with no network"
                if iso
                else "anywhere the script reaches; the local executor enforces no isolation",
                sends="nothing"
                if iso
                else "whatever the script reads, which may be the data whole",
            )
        )
    return EgressAssessment(
        components=tuple(comps),
        max_class=max_class,
        operator=str(operator),
        harness=harness,
        execution=execution,
        previous_max_class=previous_max_class,
    )


# -- report -----------------------------------------------------------------------------


def _ceiling_line(a: EgressAssessment) -> str:
    if a.max_class is None:
        line = "ceiling: none declared at init"
    else:
        line = f"ceiling: class {a.max_class} {CLASS_NAMES[a.max_class]}, set in stringency.yml"
    if a.previous_max_class is not None and a.previous_max_class != a.max_class:
        p = a.previous_max_class
        line += f" (the last acknowledged report had class {p} {CLASS_NAMES[p]})"
    return line


def render_markdown(a: EgressAssessment, *, project_id: str, assessed_at: str) -> str:
    """The saved report: facts only. It names what leaves and where; it does not advise."""
    lines = [
        f"# Data egress, project {project_id}",
        "",
        f"assessed {assessed_at}; fingerprint {hashing.prefixed(a.fingerprint)}",
        "",
        _ceiling_line(a),
        f"assessed: class {a.assessed_class} {CLASS_NAMES[a.assessed_class]}: "
        f"{CLASS_SENTENCES[a.assessed_class]}",
    ]
    if a.within is True:
        lines.append("within the ceiling")
    elif a.within is False:
        lines.append("exceeds the ceiling: " + ", ".join(c.label for c in a.over))
    lines += ["", "## What leaves the machine", ""]
    for c in a.components:
        lines.append(f"- {c.label}: class {c.cls} {CLASS_NAMES[c.cls]} ({c.basis}; {c.set_by})")
        lines.append(f"  to: {c.to}")
        lines.append(f"  sends: {c.sends}")
        if c.steps:
            lines.append(f"  steps: {', '.join(c.steps)}")
        if c.conditional:
            lines.append(f"  if it runs: {', '.join(c.conditional)}")
        for e in c.evidence:
            lines.append(f"  found: {e}")
    lines += ["", "## Classes", ""]
    lines += [f"- {k} {CLASS_NAMES[k]}: {v}" for k, v in CLASS_SENTENCES.items()]
    lines += ["", NOT_ASSESSED, ""]
    return "\n".join(lines)


def exceeds_reason(a: EgressAssessment) -> str:
    """The block reason for the two predicates: the class, the ceiling, the components over."""
    assert a.max_class is not None
    parts = [f"{c.label} class {c.cls}" for c in a.over]
    return (
        f"data egress class {a.assessed_class} {CLASS_NAMES[a.assessed_class]} exceeds the "
        f"project ceiling class {a.max_class} {CLASS_NAMES[a.max_class]}: " + "; ".join(parts)
    )
