"""Deliver (design 12.1): harvest finals with sidecars, verify deliverables, write the
coverage report, the methods paragraph, and index.json, and record the delivery.

Reads: artifacts, steps, and everything coverage reads. Writes: artifacts.is_final, deliveries.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
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
from stringency.runs import RunContext


@dataclass
class Delivery:
    delivery_id: str
    path: Path
    files: list[dict[str, Any]]
    coverage: str
    methods: str


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


def deliver(rc: RunContext, include: list[str] | None = None) -> Delivery:
    store, project = rc.store, rc.project
    status = rc.status()
    if status == "held":
        raise HeldError(
            f"held: run {rc.run_id} has open holds; run `stringency review` in {project.root}"
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
    gate = evaluate(
        rc.gate_context("deliver", action, rc.current_state(), bundle),
        registry=registry,
        store=None,
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

    dest = project.root / "deliver" / rc.run_id
    dest.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for a in finals:
        src = Path(a["path"])
        target = dest / f"{a['step_id']}.{src.name}"
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
            }
        )
    cov = coverage_data(rc)
    coverage_text = render_coverage(cov)
    methods_text = methods_paragraph(rc, cov)
    (dest / "coverage.md").write_text(coverage_text)
    (dest / "methods.md").write_text(methods_text)
    (dest / "coverage.json").write_text(
        json.dumps(cov, indent=2, sort_keys=True, default=str) + "\n"
    )
    index = {
        "stringency": 1,
        "run_id": rc.run_id,
        "project_id": project.config.project_id,
        "engine_version": __version__,
        "delivered": now_iso(),
        "files": files,
        "coverage": {"file": "coverage.md", "blake3": hashing.hash_text(coverage_text)},
        "methods": {"file": "methods.md", "blake3": hashing.hash_text(methods_text)},
    }
    index_text = json.dumps(index, indent=2, sort_keys=True) + "\n"
    (dest / "index.json").write_text(index_text)
    did = new_id()
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
        rc.run_id, "delivered", {"delivery_id": did, "path": str(dest), "files": len(files)}
    )
    return Delivery(did, dest, files, coverage_text, methods_text)


def _sidecar_ok(path: Path, digest: str) -> bool:
    sc = read_sidecar(path)
    return sc is not None and sc.get("blake3") == digest
