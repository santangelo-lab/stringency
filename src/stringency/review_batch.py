"""`stringency review --holds A,B,C --projects <dir>`: one echo-back over sibling projects'
confirm holds, one acceptance that covers the set (roadmap Lane A 5c; design 7.3).

Eight Lyons CLP QC projects differed only in the bundle they bound; the owner accepted eight
echo-backs that restated one design. Here the declarations of every project in the batch are
compared field by field: what they share is shown once, what differs is shown per project, and
the verdict is recorded on every hold as its own `reviews` row (`reason_code: batch`), so each
project's trace stands alone.

Reads: the projects' `stringency.yml`, `design.yml`, `objective.yml`, `inputs.yml`, `echo.md`
and each store's holds. Writes: through `record_review` only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.config import load_yaml
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.review import ReviewResult, record_review
from stringency.review_serve import discover

DECLARATIONS = ("design.yml", "objective.yml", "inputs.yml")


@dataclass
class BatchMember:
    project: Project
    hold: Any


@dataclass
class BatchView:
    members: list[BatchMember]
    shared: dict[
        str, Any
    ]  # declaration file -> the value every member shares (whole file or fields)
    differing: dict[str, dict[str, dict[str, Any]]]  # field path -> project name -> value
    text: str
    verdicts: list[dict[str, str]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "stringency.review_batch/1",
            "holds": [
                {
                    "hold_id": m.hold["hold_id"],
                    "project": str(m.project.root),
                    "kind": m.hold["kind"],
                }
                for m in self.members
            ],
            "differing": self.differing,
            "verdicts": self.verdicts,
        }


def locate_holds(
    hold_ids: list[str], projects: list[Path], projects_dir: Path | None
) -> list[BatchMember]:
    """Find each hold among the projects named or discovered. Refuses when a hold is missing,
    resolved, or not a project-level confirm hold: only siblings' echo-backs batch."""
    roots = discover(projects, projects_dir)
    wanted = list(dict.fromkeys(hold_ids))
    found: dict[str, BatchMember] = {}
    for root in roots:
        project = Project.load(root)
        for hid in wanted:
            if hid in found:
                continue
            h = project.store.one("SELECT * FROM holds WHERE hold_id = ?", (hid,))
            if h is not None:
                found[hid] = BatchMember(project, h)
    missing = [h for h in wanted if h not in found]
    if missing:
        raise ConfigError(f"hold(s) not found under the projects given: {', '.join(missing)}")
    members = [found[h] for h in wanted]
    for m in members:
        if m.hold["kind"] != "confirm" or m.hold["run_id"] is not None:
            raise ConfigError(
                f"hold {m.hold['hold_id']} is a {m.hold['kind']} hold; --holds batches project "
                "confirm holds only"
            )
        if m.hold["resolved_by_review"] is not None:
            raise ConfigError(f"hold {m.hold['hold_id']} is already resolved")
    return members


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, Mapping):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    elif (
        isinstance(value, list)
        and value
        and all(isinstance(v, Mapping) and "name" in v for v in value)
    ):
        for v in value:
            _flatten(f"{prefix}[{v['name']}]", v, out)
    else:
        out[prefix] = value


def compare_declarations(
    members: list[BatchMember],
) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Any]]]]:
    """Field-by-field comparison of the three declaration files across the batch. Returns what
    every member shares (by file: the whole file when identical, else the shared fields) and the
    differing fields with each project's value."""
    flat: dict[str, dict[str, Any]] = {}  # project name -> field path -> value
    raw: dict[str, dict[str, Any]] = {}
    for m in members:
        name = m.project.root.name
        flat[name] = {}
        raw[name] = {}
        for decl in DECLARATIONS:
            doc = load_yaml(m.project.root / decl)
            raw[name][decl] = doc
            _flatten(decl.removesuffix(".yml"), doc, flat[name])
    names = list(flat)
    fields = sorted({f for per in flat.values() for f in per})
    shared: dict[str, Any] = {}
    differing: dict[str, dict[str, dict[str, Any]]] = {}
    for decl in DECLARATIONS:
        docs = [raw[n][decl] for n in names]
        if all(d == docs[0] for d in docs):
            shared[decl] = docs[0]
    for f in fields:
        values = {n: flat[n].get(f, "<absent>") for n in names}
        first = next(iter(values.values()))
        if all(v == first for v in values.values()):
            continue
        differing[f] = {n: {"value": v} for n, v in values.items()}
    return shared, differing


def _short(v: Any) -> str:
    s = str(v)
    if isinstance(v, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s):
        return s[:12] + "…"
    if isinstance(v, str) and "/" in s and len(s) > 48:
        return "…/" + "/".join(s.rstrip("/").split("/")[-2:])
    return s


def batch_view(members: list[BatchMember]) -> BatchView:
    shared, differing = compare_declarations(members)
    n = len(members)
    lines = [
        f"batch review: {n} confirm hold(s) on {n} project(s), same verdict for all",
        "",
        "question: does the engine's reading of these declarations match the experiment, for every project listed",
        "",
    ]
    owners = {m.project.config.roles.owner for m in members}
    pipelines = {f"{m.project.pipeline.name} {m.project.pipeline.version}" for m in members}
    lines.append(
        f"owner(s): {', '.join(sorted(owners))}    pipeline(s): {', '.join(sorted(pipelines))}"
    )
    same = [d for d in DECLARATIONS if d in shared]
    lines.append(
        "identical across the batch: " + (", ".join(same) if same else "nothing at file level")
    )
    if differing:
        lines += ["", "differs per project:"]
        header = ["project"] + list(differing)
        rows = [
            [m.project.root.name]
            + [_short(differing[f][m.project.root.name]["value"]) for f in differing]
            for m in members
        ]
        widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
        lines.append("  " + "  ".join(str(h).ljust(w) for h, w in zip(header, widths, strict=True)))
        for r in rows:
            lines.append("  " + "  ".join(str(c).ljust(w) for c, w in zip(r, widths, strict=True)))
    else:
        lines += ["", "the declarations are identical in every field"]
    first = members[0].project
    echo = first.echo_path()
    lines += [
        "",
        f"echo-back of {first.root.name} (the shared reading; the table above is what changes):",
        "",
    ]
    if echo.exists():
        lines.append(echo.read_text().rstrip())
    for m in members:
        lines.append("")
        lines.append(
            f"  hold {m.hold['hold_id']}  project {m.project.root}  created {m.hold['created']}"
        )
    verdicts = [
        {
            "verdict": "accept",
            "effect": f"every one of the {n} readings matches its experiment; each hold clears and each project may run",
            "command": f'stringency review --holds {",".join(m.hold["hold_id"] for m in members)} --projects <dir> --verdict accept --reason "<why>"',
        },
        {
            "verdict": "reject",
            "effect": "every reading is wrong; no project runs until its declarations change and a new echo-back is accepted",
            "command": f'stringency review --holds {",".join(m.hold["hold_id"] for m in members)} --projects <dir> --verdict reject --reason "<why>"',
        },
    ]
    lines += [
        "",
        "verdicts (one for the whole batch; a project that needs a different answer is reviewed alone):",
    ]
    for v in verdicts:
        lines.append(f"  {v['verdict']}: {v['effect']}")
    return BatchView(members, shared, differing, "\n".join(lines), verdicts)


def record_batch(
    members: list[BatchMember], verdict: str, *, reason: str | None, attest: bool
) -> list[ReviewResult]:
    """One `reviews` row per hold, each with `reason_code: batch`, recorded in order; stops at
    the first refusal so the caller can report which holds were reached."""
    if verdict not in ("accept", "reject"):
        raise ConfigError("a batch verdict is accept or reject")
    if not reason:
        raise ConfigError(f"{verdict} needs --reason")
    out: list[ReviewResult] = []
    for m in members:
        out.append(
            record_review(
                m.project,
                m.hold["hold_id"],
                verdict,
                reason=reason,
                attest=attest,
                reason_code="batch",
            )
        )
    return out
