"""Deliver (design 12.1): harvest finals with sidecars, verify deliverables, write the
coverage report, the methods paragraph, the plain summary, and index.json, and record the
delivery. An open run (open_mode_plan.md 2.7) delivers the answers the person chose
(`--answer`), with their cited artifacts, into `deliver/<run>/<delivery_id>/`; it never stops
for a sign-off (owner's decision 5) and may deliver several times.

Reads: artifacts, steps, answers, questions, and everything coverage reads. Writes:
artifacts.is_final, predicate_results (the deliver gate), deliveries, run_events.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import __version__, hashing
from stringency.actions import Action
from stringency.artifacts import read_sidecar, sidecar_path
from stringency.clock import now_iso
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
    summary: str = ""
    answers: list[dict[str, Any]] = field(default_factory=list)


def chosen_answers(rc: RunContext, answer_ids: list[str]) -> list[dict[str, Any]]:
    """The answers an open run delivers: each id an admissible answer of this run (a blocked
    one, or another run's, is refused with exit 15). Reads: answers, questions, messages."""
    from stringency.answers import answer_row

    if not answer_ids:
        raise ConfigError(
            "an open run delivers the answers the person chose: --answer <id> (repeatable); "
            "`stringency present --answers` lists them"
        )
    out: list[dict[str, Any]] = []
    for aid in dict.fromkeys(answer_ids):
        row = answer_row(rc, aid)
        if row["status"] != "admissible":
            raise ConfigError(
                f"answer {aid} is {row['status']}; only an admissible answer is delivered"
            )
        out.append(row)
    return out


def answer_artifacts(rc: RunContext, answers: list[dict[str, Any]]) -> list[Any]:
    """The produced artifacts the chosen answers cite, each once, in citation order."""
    rows: list[Any] = []
    seen: set[str] = set()
    for a in answers:
        for c in a["cited"]:
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


def final_artifacts(rc: RunContext, include: list[str]) -> list[Any]:
    """Report-module outputs by default, plus `--include <step>.<output>`; also any output
    named as a deliverable in the objective."""
    store, project = rc.store, rc.project
    wanted: set[tuple[str, str]] = set()
    for step in project.pipeline.steps:
        m = project.modules.require(step.module).manifest
        for name in m.outputs:
            if m.kind == "report" or name in project.objective.deliverables:
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
    answers: list[dict[str, Any]] = []
    if rc.open_ended:
        if rc.run["status"] in ("abandoned",):
            raise RefusedError(f"run {rc.run_id} is abandoned; nothing to deliver")
        answers = chosen_answers(rc, list(answer_ids or []))
        finals = answer_artifacts(rc, answers) + final_artifacts(rc, include or [])
    else:
        if answer_ids:
            raise RefusedError(
                "--answer delivers an open run's answers; this run has a declared topology"
            )
        if status != "completed":
            raise RefusedError(f"run {rc.run_id} is {status}; deliver needs a completed run")
        finals = final_artifacts(rc, include or [])
    # prov.orphan_artifact: every final must carry a sidecar that matches its hash
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
    produced_names = {a["name"] for a in finals}
    missing = [d for d in project.objective.deliverables if d not in produced_names]
    if missing:
        raise ConfigError(
            f"deliverable(s) declared in the objective are not present: {', '.join(missing)}"
        )

    did = new_id()
    # an open run delivers several times, each into its own directory (`present` reads the latest)
    dest = project.root / "deliver" / rc.run_id / (did if rc.open_ended else "")
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
    counts = rerun_counts(rc)
    delivered_answers: list[dict[str, Any]] = []
    by_artifact = {f["artifact_id"]: f["file"] for f in files}
    for ans in answers:
        prov = ans["provenance"]
        fname = f"{ans['answer_id']}.answer.md"
        cited_files = sorted(
            {by_artifact[c["artifact_id"]] for c in ans["cited"] if c["artifact_id"] in by_artifact}
        )
        rerun = answer_rerun_line(rc, ans, counts)
        (dest / fname).write_text(
            f"# Answer {ans['answer_id']}\n\n"
            f"Question ({ans['origin']}): {ans['question']}\n\n"
            f"{prov.get('label_sentence', '')}\n{prov.get('qualifier_line', '')}\n\n"
            f"{ans['text'].rstrip()}\n\n"
            "Cited files: " + (", ".join(cited_files) or "none") + "\n"
            f"Runs: {rerun}\n"
        )
        delivered_answers.append(
            {
                "answer_id": ans["answer_id"],
                "question_id": ans["question_id"],
                "question": ans["question"],
                "origin": ans["origin"],
                "file": fname,
                "label": ans["label"],
                "label_sentence": prov.get("label_sentence"),
                "qualifier": prov.get("qualifier_line"),
                "cites": ans["cited"],
                "files": cited_files,
                "runs": rerun,
            }
        )
    cov = coverage_data(rc)
    cov["explored"] = {
        "rerun_counts": [
            {**e, "delivered": sum(1 for f in files if f["step_id"] in e["steps"])}
            for e in counts.values()
        ],
        "questions": {
            "person": store.scalar(
                "SELECT COUNT(*) FROM questions WHERE run_id=? AND origin='person'", (rc.run_id,)
            )
            or 0,
            "suggested": store.scalar(
                "SELECT COUNT(*) FROM questions WHERE run_id=? AND origin='suggested'", (rc.run_id,)
            )
            or 0,
        },
        "answers": delivered_answers,
    }
    coverage_text = render_coverage(cov)
    methods_text = methods_paragraph(rc, cov)
    summary_text = render_summary(rc, cov, files, delivered_answers)
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
        "answers": delivered_answers,
        "engine_version": __version__,
        "plugins": captured_plugins(store, rc.run_id),
        "delivered": now_iso(),
        "files": files,
        "coverage": {"file": "coverage.md", "blake3": hashing.hash_text(coverage_text)},
        "methods": {"file": "methods.md", "blake3": hashing.hash_text(methods_text)},
        "summary": {"file": "summary.md", "blake3": hashing.hash_text(summary_text)},
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
            "answers": [a["answer_id"] for a in delivered_answers],
        },
    )
    return Delivery(did, dest, files, coverage_text, methods_text, summary_text, delivered_answers)


def _sidecar_ok(path: Path, digest: str) -> bool:
    sc = read_sidecar(path)
    return sc is not None and sc.get("blake3") == digest
