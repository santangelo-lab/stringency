"""`review --export` (design 7.6, L37): the override corpus as cases.

One Markdown document per resolved hold of a run: YAML frontmatter with what the hold asked
and how it was answered (hold, kind, predicate, step, item, module, reviewer, `via`, verdict,
reason, the bound hashes), and below it the packet as the reviewer saw it. `review --export`
writes them into the run directory; `deliver` writes the same documents into
`deliver/<run>/reviews/` before it records the delivery and lists each in `index.json` with
its hash (the owner's ruling, 2026-11-12). A method author's
agent reads these for a module version (the method template's `stringency-revise` skill),
groups them by theme and proposes changes that cite the hold ids, as 7.6 asks of a prompt
change. `status --overrides` gives the rate; this gives the cases behind it.

A hold counts as resolved when a review resolved it (`holds.resolved_by_review`), whatever its
`via`, a rebind and an inherited verdict included. A hold withdrawn with no review (an abandoned
run, a withdrawn proposal) has no verdict and no reason, and a `defer` leaves a hold open, so
neither is exported. A project-level hold (the init confirm) is the declarations' sign-off, not
a module's, and belongs to no run directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from stringency import hashing
from stringency.exit_codes import ConfigError
from stringency.project import Project

SCHEMA = "stringency.review_export/1"
DELIVERY_DIR = "reviews"  # `deliver/<run>/reviews/`


@dataclass
class Exported:
    hold_id: str
    run_id: str
    module: str | None
    paths: list[Path]


def resolved_holds(project: Project, run_id: str | None = None) -> list[Any]:
    """Reads: holds, steps. Every hold of a run resolved by a review, oldest first, with the
    module and module version of the step it belongs to (the latest attempt's)."""
    sql = (
        "SELECT h.*, s.module AS step_module, s.module_version AS step_module_version "
        "FROM holds h LEFT JOIN steps s ON s.run_id = h.run_id AND s.step_id = h.step_id "
        "WHERE h.run_id IS NOT NULL AND h.resolved_by_review IS NOT NULL "
    )
    params: tuple[Any, ...] = ()
    if run_id is not None:
        sql += "AND h.run_id = ? "
        params = (run_id,)
    sql += "ORDER BY h.created, h.hold_id"
    return list(project.store.all(sql, params))


def _module_ref(h: Any) -> str | None:
    if h["step_module"] is None:
        return None
    return f"{h['step_module']}@{h['step_module_version']}"


def matches_module(h: Any, module: str | None) -> bool:
    """`--module` names a module (`label-groups`) or one version of it (`label-groups@0.1.1`)."""
    if module is None:
        return True
    if "@" in module:
        return _module_ref(h) == module
    return bool(h["step_module"] == module)


def frontmatter(project: Project, h: Any) -> dict[str, Any]:
    """Reads: reviews, consensus (through `review_render.resolution`). What the hold asked and
    how it was answered, every value plain YAML."""
    from stringency.review_render import resolution

    ctx = json.loads(h["context_json"] or "{}")
    res = resolution(project, h) or {}
    r = project.store.one("SELECT * FROM reviews WHERE review_id = ?", (h["resolved_by_review"],))
    return {
        "schema": SCHEMA,
        "hold": h["hold_id"],
        "kind": h["kind"],
        "predicate": ctx.get("predicate"),
        "phase": ctx.get("phase"),
        "run": h["run_id"],
        "step": h["step_id"],
        "item": h["item_id"],
        "module": _module_ref(h),
        "hold_reason": h["reason"],
        "opened": h["created"],
        "review": h["resolved_by_review"],
        "reviewer": res.get("reviewer"),
        "via": res.get("via") or h["resolved_via"],
        "verdict": res.get("verdict"),
        "reason": res.get("reason"),
        "reason_code": r["reason_code"] if r is not None else None,
        "reviewed": res.get("ts"),
        "replicate": res.get("replicate"),
        "correction": res.get("correction"),
        "label": res.get("label"),
        "bound": {
            "module_version": h["bound_module_version"],
            "input_digest": h["bound_input_digest"],
            "params_hash": h["bound_params_hash"],
            "item_evidence_digest": h["bound_item_evidence_digest"],
        },
    }


def packet_text(project: Project, h: Any) -> tuple[str, str]:
    """The packet as the reviewer saw it: the Markdown packet written when the hold opened
    (`runs/<run>/<step>/review/<hold>.md`), or, for a hold that has none, the review display
    rendered now. Returns the text and which of the two it is. Reads: what `review_render`
    reads; the packet file."""
    from stringency.review_render import packet_paths, render

    paths = packet_paths(project, h)
    if paths is not None and paths[0].is_file():
        return paths[0].read_text(), "packet written when the hold opened"
    return render(project, h).text, "review display rendered at export"


def document(project: Project, h: Any) -> str:
    head = frontmatter(project, h)
    body, source = packet_text(project, h)
    head["packet"] = source
    return (
        "---\n"
        + yaml.safe_dump(head, sort_keys=False, allow_unicode=True, default_flow_style=False)
        + "---\n\n"
        + body.rstrip()
        + "\n"
    )


@dataclass
class Document:
    hold_id: str
    run_id: str
    step_id: str | None
    module: str | None
    text: str

    @property
    def name(self) -> str:
        return f"{self.hold_id}.md"


def documents(
    project: Project, *, run_id: str | None = None, module: str | None = None
) -> list[Document]:
    """Every resolved hold's document, rendered in memory, oldest hold first. Rendering is
    where an export fails (the trace, the packet file), so a caller that must not record on
    failure renders first. Reads: what `resolved_holds`, `frontmatter` and `packet_text` read.
    Writes: nothing."""
    return [
        Document(h["hold_id"], h["run_id"], h["step_id"], _module_ref(h), document(project, h))
        for h in resolved_holds(project, run_id)
        if matches_module(h, module)
    ]


def export_reviews(
    project: Project, *, run_id: str | None = None, module: str | None = None
) -> list[Exported]:
    """Write one document per resolved hold into `runs/<run>/reviews/<hold>.md`, rewritten whole
    on every export. A `run_id` the trace does not hold is refused (exit 15). Reads: runs,
    holds, steps, reviews, consensus and what the review display reads. Writes: those files
    only; nothing in the trace."""
    if (
        run_id is not None
        and project.store.one("SELECT run_id FROM runs WHERE run_id = ?", (run_id,)) is None
    ):
        raise ConfigError(f"no run {run_id} in this project")
    out: list[Exported] = []
    for doc in documents(project, run_id=run_id, module=module):
        d = project.run_dir(doc.run_id) / "reviews"
        d.mkdir(parents=True, exist_ok=True)
        p = d / doc.name
        p.write_text(doc.text)
        out.append(Exported(doc.hold_id, doc.run_id, doc.module, [p]))
    return out


def write_into_delivery(dest: Path, docs: list[Document]) -> list[dict[str, Any]]:
    """Write the run's documents into `<dest>/reviews/<hold>.md` (the delivery directory) and
    return their `index.json` entries: the file relative to the delivery, the hold, step and
    module, and the blake3 of the text, so the index's hash covers them. The same trace gives
    the same files and entries. Writes: those files only; nothing in the trace."""
    entries: list[dict[str, Any]] = []
    if not docs:
        return entries
    d = dest / DELIVERY_DIR
    d.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        (d / doc.name).write_text(doc.text)
        entries.append(
            {
                "file": f"{DELIVERY_DIR}/{doc.name}",
                "hold": doc.hold_id,
                "step_id": doc.step_id,
                "module": doc.module,
                "blake3": hashing.hash_text(doc.text),
            }
        )
    return entries
