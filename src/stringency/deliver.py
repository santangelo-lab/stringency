"""Deliver (design 12.1): harvest finals with sidecars, verify deliverables, write the
coverage report, the methods paragraph, the plain summary, and index.json, and record the
delivery. An open run's delivery is `report.py` (2026-10-19):
every admissible answer is written into `deliver/<run>/` as it is filed, and `deliver` here
only regenerates it (`--answer` is refused; findings are marked with `stringency finding`).

Reads: artifacts, steps, answers, questions, and everything coverage reads. Writes:
artifacts.is_final, predicate_results (the deliver gate), deliveries, run_events.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import __version__, hashing
from stringency.actions import Action
from stringency.artifacts import read_sidecar, sidecar_path
from stringency.clock import now_iso
from stringency.config import deliverable_ref
from stringency.coverage import coverage_data, render_coverage
from stringency.exit_codes import ConfigError, HeldError, RefusedError
from stringency.gate import evaluate
from stringency.ids import new_id
from stringency.methods import methods_paragraph
from stringency.predicates import registry
from stringency.predicates.context import OutputBundle
from stringency.provenance import block_for
from stringency.runs import RunContext, captured_plugins
from stringency.summary import render_summary


@dataclass
class Delivery:
    delivery_id: str
    path: Path
    files: list[dict[str, Any]]
    coverage: str
    methods: str
    summary: str = ""  # the report text of an open run
    answers: list[dict[str, Any]] = field(default_factory=list)
    changed: bool = True  # open mode: whether this regeneration wrote a `deliveries` row


def answer_file_name(seq: int, question: str, nth: int = 1) -> str:
    """`q<NN>-<the question's first words>.md`: the answer's file in an open delivery; a
    question's second admissible answer is `-2`, by filing order, so a name never changes."""
    words = re.findall(r"[a-z0-9]+", question.lower())[:8]
    slug = "-".join(words)[:48].rstrip("-") or "answer"
    return f"q{seq:02d}-{slug}{'' if nth == 1 else f'-{nth}'}.md"


def answer_artifacts(rc: RunContext, answers: list[dict[str, Any]]) -> list[Any]:
    """The produced artifacts the chosen answers cite, then the figures each attaches (L143,
    `provenance.figures`), each once, in citation order. Reads: artifacts."""
    rows: list[Any] = []
    seen: set[str] = set()
    for a in answers:
        figures = (a.get("provenance") or {}).get("figures") or []
        for c in [*a["cited"], *figures]:
            aid = str(c["artifact_id"])
            if aid in seen:
                continue
            seen.add(aid)
            row = rc.store.one(
                "SELECT * FROM artifacts WHERE run_id=? AND artifact_id=? AND status='produced'",
                (rc.run_id, aid),
            )
            if row is not None:
                rows.append(row)
    return rows


def rerun_counts(rc: RunContext) -> dict[str, dict[str, Any]]:
    """The forking-paths disclosure (open_mode_plan.md 2.7): per module and input digest, how
    many runs there were (N), how many distinct parameter sets (K), and which steps, from
    `actions` of this run's completed steps. Reads: actions, steps."""
    rows = rc.store.all(
        "SELECT a.step_id, a.module, a.input_digest, a.params_hash FROM actions a "
        "JOIN steps s ON s.run_id=a.run_id AND s.step_id=a.step_id "
        "WHERE a.run_id=? AND s.status='completed' AND a.attempt = s.attempt ORDER BY a.rowid",
        (rc.run_id,),
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = f"{r['module']}|{r['input_digest']}"
        e = out.setdefault(
            key,
            {
                "module": r["module"],
                "input_digest": r["input_digest"],
                "steps": [],
                "params": set(),
            },
        )
        e["steps"].append(r["step_id"])
        e["params"].add(r["params_hash"])
    return {
        k: {
            "module": e["module"],
            "input_digest": e["input_digest"],
            "steps": e["steps"],
            "runs": len(e["steps"]),
            "distinct_params": len(e["params"]),
        }
        for k, e in out.items()
    }


def answer_rerun_line(
    rc: RunContext, answer: dict[str, Any], counts: dict[str, dict[str, Any]]
) -> str:
    """One line per delivered answer: one of N runs of the tool on these inputs; how many
    results on the same inputs existed when the question was asked; the other steps."""
    prov = answer.get("provenance") or {}
    steps = [f["step_id"] for f in prov.get("lineage", []) if f.get("kind") in ("tool", "exec")]
    if not steps:
        return "no step of this run is on the answer's path"
    first = steps[0]
    row = rc.store.one(
        "SELECT module, input_digest FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, first),
    )
    if row is None:
        return f"step {first}: no action recorded"
    e = counts.get(f"{row['module']}|{row['input_digest']}")
    if e is None:
        return f"step {first}: not counted"
    asked = rc.store.scalar(
        "SELECT ts FROM questions WHERE question_id=?", (answer["question_id"],)
    )
    earlier = rc.store.scalar(
        "SELECT COUNT(*) FROM actions a JOIN steps s ON s.run_id=a.run_id AND s.step_id=a.step_id "
        "WHERE a.run_id=? AND a.module=? AND a.input_digest=? AND s.status='completed' AND s.ended < ?",
        (rc.run_id, row["module"], row["input_digest"], asked or ""),
    )
    others = [s for s in e["steps"] if s != first]
    return (
        f"one of {e['runs']} run(s) of {row['module']} on these inputs ({e['distinct_params']} "
        f"distinct parameter set(s)); asked after {int(earlier or 0)} result(s) on the same inputs "
        f"existed" + (f"; the others are steps {', '.join(others)}" if others else "")
    )


def deliver_gate(rc: RunContext, finals: list[Any]) -> None:
    """The deliver gate: `prov.orphan_artifact` (every final must carry a sidecar that matches
    its hash), its verdicts recorded. Refused (exit 16) when it blocks. Writes: predicate_results."""
    store = rc.store
    orphans = [a["path"] for a in finals if not _sidecar_ok(Path(a["path"]), a["hash"])]
    action = Action(
        action_id=f"deliver:{new_id()}",
        run_id=rc.run_id,
        step_id="deliver",
        attempt=0,
        operation="deliver",
        module="deliver",
        parameters={},
        param_source={},
        inputs={},
        input_digest="blake3:" + hashing.hash_json({}),
        params_hash="blake3:" + hashing.hash_json({}),
        proposed_by="pipeline",
    )
    bundle = OutputBundle(outputs={}, observed={"missing_sidecars": orphans})
    # the gate's verdicts are recorded (before 2026-10-16 `store=None` dropped them)
    gate = evaluate(
        rc.gate_context("deliver", action, rc.current_state(), bundle),
        registry=registry,
        store=store,
        policy_digest=rc.policy_digest,
        module=None,
        runner=None,
    )
    if gate.blocked:
        raise RefusedError("deliver refused: " + "; ".join(r.line() for r in gate.blocked))


def final_artifacts(rc: RunContext, include: list[str]) -> list[Any]:
    """Report-module outputs by default, plus `--include <step>.<output>`; also every output
    the objective names as a deliverable: a bare name from every step that produces it, a
    `<step>.<output>` from that step only (L135). Reads: artifacts."""
    store, project = rc.store, rc.project
    wanted: set[tuple[str, str]] = set()
    bare: set[str] = set()
    for d in project.objective.deliverables:
        sid, out = deliverable_ref(d)
        if sid is None:
            bare.add(out)
        else:
            wanted.add((sid, out))
    for step in project.pipeline.steps:
        m = project.modules.require(step.module).manifest
        for name in m.outputs:
            if m.kind == "report" or name in bare:
                wanted.add((step.id, name))
    for inc in include:
        if "." not in inc:
            raise ConfigError(f"--include expects <step>.<output>, got {inc!r}")
        sid, name = inc.split(".", 1)
        wanted.add((sid, name))
    rows = []
    for sid, name in sorted(wanted):
        row = store.one(
            "SELECT * FROM artifacts WHERE run_id=? AND step_id=? AND name=? AND status='produced' ORDER BY rowid DESC LIMIT 1",
            (rc.run_id, sid, name),
        )
        if row is not None:
            rows.append(row)
    return rows


def deliver(
    rc: RunContext, include: list[str] | None = None, answer_ids: list[str] | None = None
) -> Delivery:
    store, project = rc.store, rc.project
    status = rc.status()
    if status == "held":
        raise HeldError(
            f"held: run {rc.run_id} has open holds; run `stringency review` in {project.root}"
        )
    if rc.open_ended:
        from stringency.report import write_open_delivery

        if answer_ids:
            raise RefusedError(
                "open mode writes every answer into deliver/<run>/ as it is filed; mark the "
                "findings the report leads with using `stringency finding <answer id>`"
            )
        return write_open_delivery(rc)
    if answer_ids:
        raise RefusedError("--answer belongs to open mode; this run has a declared topology")
    if status != "completed":
        raise RefusedError(f"run {rc.run_id} is {status}; deliver needs a completed run")
    finals = final_artifacts(rc, include or [])
    deliver_gate(rc, finals)
    produced_names = {a["name"] for a in finals} | {f"{a['step_id']}.{a['name']}" for a in finals}
    missing = [d for d in project.objective.deliverables if d not in produced_names]
    if missing:
        raise ConfigError(
            f"deliverable(s) declared in the objective are not present: {', '.join(missing)}"
        )

    did = new_id()
    dest = project.root / "deliver" / rc.run_id
    dest.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for a in finals:
        if a["artifact_id"] in seen_ids:
            continue
        seen_ids.add(a["artifact_id"])
        src = Path(a["path"])
        target = dest / f"{a['step_id']}.{src.name}"
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, target)
        shutil.copyfile(sidecar_path(src), sidecar_path(target))
        store.set_artifact_flag(a["artifact_id"], "is_final", True)
        files.append(
            {
                "file": target.name,
                "step_id": a["step_id"],
                "output": a["name"],
                "action_id": a["action_id"],
                "artifact_id": a["artifact_id"],
                "blake3": a["hash"],
                "kind": a["kind"],
                "sidecar": sidecar_path(target).name,
                "provenance": block_for(rc, a["artifact_id"]),  # backlog L35, both modes
            }
        )
    cov = coverage_data(rc)
    coverage_text = render_coverage(cov)
    methods_text = methods_paragraph(rc, cov)
    summary_text = render_summary(rc, cov, files)
    (dest / "coverage.md").write_text(coverage_text)
    (dest / "methods.md").write_text(methods_text)
    (dest / "summary.md").write_text(summary_text)
    (dest / "coverage.json").write_text(
        json.dumps(cov, indent=2, sort_keys=True, default=str) + "\n"
    )
    index = {
        "stringency": 1,
        "run_id": rc.run_id,
        "project_id": project.config.project_id,
        "mode": project.config.mode,
        "engine_version": __version__,
        "plugins": captured_plugins(store, rc.run_id),
        "delivered": now_iso(),
        "files": files,
        "coverage": {"file": "coverage.md", "blake3": hashing.hash_text(coverage_text)},
        "methods": {"file": "methods.md", "blake3": hashing.hash_text(methods_text)},
        "summary": {"file": "summary.md", "blake3": hashing.hash_text(summary_text)},
        "egress": (
            None
            if cov.get("egress") is None
            else {
                k: cov["egress"][k]
                for k in ("fingerprint", "report", "max_class", "highest_reached")
            }
        ),
    }
    index_text = json.dumps(index, indent=2, sort_keys=True) + "\n"
    (dest / "index.json").write_text(index_text)
    store.insert(
        "deliveries",
        {
            "delivery_id": did,
            "run_id": rc.run_id,
            "path": str(dest),
            "coverage_hash": hashing.hash_text(coverage_text),
            "methods_hash": hashing.hash_text(methods_text),
            "index_hash": hashing.hash_text(index_text),
            "ts": now_iso(),
        },
    )
    store.run_event(
        rc.run_id,
        "delivered",
        {
            "delivery_id": did,
            "path": str(dest),
            "files": len(files),
        },
    )
    return Delivery(did, dest, files, coverage_text, methods_text, summary_text)


def _sidecar_ok(path: Path, digest: str) -> bool:
    sc = read_sidecar(path)
    return sc is not None and sc.get("blake3") == digest
