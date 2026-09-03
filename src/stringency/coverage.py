"""The coverage report (design 12.2): generated, fixed in structure, never hand-edited.

Reads: runs, steps, predicate_results, holds, reviews, invocations, judgments, consensus,
executions, actions, controls_runs. Writes nothing.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from stringency import __version__
from stringency.gate import in_scope_specs
from stringency.predicates import registry
from stringency.runs import RunContext


def decision_point_coverage(rc: RunContext) -> tuple[list[str], list[str]]:
    """(uncovered decision points as `step.param`, ungated steps). A decision point is covered
    when at least one predicate evaluated for that step declares `covers` for its operation.param
    or operation.*."""
    store = rc.store
    uncovered: list[str] = []
    ungated: list[str] = []
    for step in rc.project.pipeline.steps:
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        if st not in ("completed", "held", "rejected"):
            continue
        module = rc.project.modules.require(step.module)
        rows = store.all(
            "SELECT DISTINCT pr.predicate_id FROM predicate_results pr JOIN actions a ON a.action_id = pr.action_id "
            "WHERE a.run_id=? AND a.step_id=?",
            (rc.run_id, step.id),
        )
        evaluated = [registry.get(r["predicate_id"]) for r in rows]
        if not rows:
            ungated.append(step.id)
        for dp in module.manifest.decision_points:
            if not any(
                s is not None and s.covers_param(module.manifest.operation, dp) for s in evaluated
            ):
                uncovered.append(f"{step.id}.{dp}")
    return uncovered, ungated


def in_scope_for_pipeline(rc: RunContext) -> set[str]:
    ids: set[str] = set()
    for step in rc.project.pipeline.steps:
        m = rc.project.modules.require(step.module).manifest
        runner = step.runner or m.runner or rc.project.config.execution
        for phase in ("pre", "post"):
            for s in in_scope_specs(
                registry, phase, operation=m.operation, module=m, runner=runner
            ):
                ids.add(s.id)
    return ids


def coverage_data(rc: RunContext) -> dict[str, Any]:
    store, run = rc.store, rc.run
    project = rc.project
    steps = store.all(
        "SELECT step_id, status FROM steps WHERE run_id=? ORDER BY rowid", (rc.run_id,)
    )
    status_counts = Counter(s["status"] for s in steps)
    results = store.all(
        "SELECT pr.*, a.step_id FROM predicate_results pr JOIN actions a ON a.action_id = pr.action_id WHERE a.run_id=?",
        (rc.run_id,),
    )
    fired = Counter(r["effective_disposition"] for r in results if r["fired"])
    evaluated_ids = {r["predicate_id"] for r in results}
    flags = []
    for h in store.all(
        "SELECT * FROM holds WHERE run_id=? AND kind='flag' ORDER BY created", (rc.run_id,)
    ):
        rev = (
            store.one("SELECT * FROM reviews WHERE review_id=?", (h["resolved_by_review"],))
            if h["resolved_by_review"]
            else None
        )
        flags.append(
            {
                "predicate": json.loads(h["context_json"] or "{}").get(
                    "predicate", h["reason"].split(":")[0]
                ),
                "step": h["step_id"],
                "verdict": rev["verdict"] if rev else "open",
                "reviewer": rev["reviewer"] if rev else None,
                "date": rev["ts"][:10] if rev else None,
                "via": h["resolved_via"] or (rev["via"] if rev else None),
                "reason": rev["reason"] if rev else None,
            }
        )
    uncovered, ungated = decision_point_coverage(rc)

    judgment: list[dict[str, Any]] = []
    for step in project.pipeline.steps:
        m = project.modules.require(step.module).manifest
        if m.kind != "judgment":
            continue
        cons = store.all(
            "SELECT * FROM consensus WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        if not cons:
            continue
        n_items = len(cons)
        n_rep = (
            store.scalar(
                "SELECT MAX(replicate) FROM judgments WHERE run_id=? AND step_id=?",
                (rc.run_id, step.id),
            )
            or 0
        )
        kinds = Counter(
            h["kind"]
            for h in store.all(
                "SELECT kind FROM holds WHERE run_id=? AND step_id=? AND item_id IS NOT NULL",
                (rc.run_id, step.id),
            )
        )
        sources = Counter(c["source"] for c in cons)
        cum = store.all(
            "SELECT r.verdict, COUNT(*) n FROM reviews r JOIN holds h ON h.hold_id=r.hold_id JOIN steps s ON s.run_id=h.run_id AND s.step_id=h.step_id "
            "WHERE h.item_id IS NOT NULL AND s.module=? AND s.module_version=? GROUP BY r.verdict",
            (m.name, m.version),
        )
        cum_counts = {r["verdict"]: r["n"] for r in cum}
        cum_items = (
            store.scalar(
                "SELECT COUNT(*) FROM consensus c JOIN steps s ON s.run_id=c.run_id AND s.step_id=c.step_id WHERE s.module=? AND s.module_version=?",
                (m.name, m.version),
            )
            or 0
        )
        judgment.append(
            {
                "module": m.ref,
                "step": step.id,
                "items": n_items,
                "replicates": n_rep,
                "agreed": sources.get("agreed", 0),
                "self_uncertain": kinds.get("self_uncertain", 0),
                "run_disagreement": kinds.get("run_disagreement", 0),
                "accepted": sources.get("accepted", 0),
                "override": sources.get("override", 0),
                "unresolved": sources.get("unresolved", 0),
                "cumulative_overrides": cum_counts.get("override", 0),
                "cumulative_items": cum_items,
            }
        )

    controls = store.all(
        "SELECT module, module_version, control_name, kind, passed, metrics_json, MAX(ts) ts FROM controls_runs WHERE passed=1 "
        "GROUP BY module, module_version, control_name ORDER BY module, control_name"
    )
    execs = store.all(
        "SELECT a.step_id, e.runner, e.env_status FROM executions e JOIN actions a ON a.action_id=e.action_id "
        "JOIN steps s ON s.run_id=a.run_id AND s.step_id=a.step_id WHERE a.run_id=? AND s.status='completed' "
        "AND e.rowid IN (SELECT MAX(rowid) FROM executions GROUP BY action_id)",
        (rc.run_id,),
    )
    operator = [e for e in execs if e["runner"] == "operator"]
    drift = sum(1 for r in results if r["fired"] and r["predicate_id"] == "exec.plan_drift")
    stochastic = [
        s.id
        for s in project.pipeline.steps
        if project.modules.require(s.module).manifest.stochastic
    ]
    seeded = 0
    for sid in stochastic:
        a = store.one(
            "SELECT params_json FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC LIMIT 1",
            (rc.run_id, sid),
        )
        m = project.modules.require(project.pipeline.step(sid).module).manifest
        if a and json.loads(a["params_json"]).get(m.seed_param) is not None:
            seeded += 1
    invs = store.all(
        "SELECT via, isolation, model_resolved, harness_kind FROM invocations WHERE run_id=?",
        (rc.run_id,),
    )
    inv_summary = None
    if invs:
        inv_summary = {
            "count": len(invs),
            "via": sorted({i["via"] for i in invs}),
            "isolation": sorted({i["isolation"] for i in invs}),
            "models": sorted({i["model_resolved"] for i in invs}),
            "harness": sorted({i["harness_kind"] for i in invs}),
        }
    return {
        "run_id": rc.run_id,
        "project_id": project.config.project_id,
        "pipeline": f"{project.pipeline.name}@{project.pipeline.version}",
        "mode": project.config.mode,
        "profile": project.config.profile,
        "policy_version": run["policy_version"],
        "policy_digest": run["policy_digest"],
        "stringency_version": __version__,
        "method_sha": run["git_sha"],
        "method_dirty": bool(run["git_dirty"]),
        "steps": {
            "declared": len(steps),
            **{
                k: status_counts.get(k, 0)
                for k in ("completed", "held", "blocked", "rejected", "failed")
            },
        },
        "gate": {
            "registered": len(registry.all()),
            "in_scope": len(in_scope_for_pipeline(rc)),
            "evaluated": len(evaluated_ids),
            "fired": {k: fired.get(k, 0) for k in ("block", "flag", "log")},
            "flags": flags,
            "uncovered_decision_points": uncovered,
            "ungated_steps": ungated,
        },
        "judgment": judgment,
        "controls": [
            {
                "module": f"{c['module']}@{c['module_version']}",
                "date": c["ts"][:10],
                "control": c["control_name"],
                "kind": c["kind"],
                "metrics": json.loads(c["metrics_json"]),
            }
            for c in controls
        ],
        "execution": {
            "operator_run": len(operator),
            "env_verified": sum(1 for e in operator if e["env_status"] == "verified"),
            "as_reported": [e["step_id"] for e in operator if e["env_status"] == "as_reported"],
            "engine_run": len(execs) - len(operator),
            "plan_drift": drift,
        },
        "reproducibility": {
            "stochastic_steps": len(stochastic),
            "seeded": seeded,
            "env_digest": run["env_digest"],
            "invocations": inv_summary,
        },
    }


def render_coverage(d: dict[str, Any]) -> str:
    g, s, e, r = d["gate"], d["steps"], d["execution"], d["reproducibility"]
    lines = [
        "stringency coverage report",
        f"run {d['run_id']} | project {d['project_id']} | pipeline {d['pipeline']} | mode {d['mode']} | profile {d['profile']}",
        f"policy {d['policy_version']} (blake3:{d['policy_digest'][:12]}) | stringency {d['stringency_version']} | method {d['method_sha'][:12]} ({'dirty' if d['method_dirty'] else 'clean'})",
        "",
        f"steps: {s['declared']} declared, {s['completed']} completed, {s['held']} held, {s['blocked']} blocked, {s['rejected']} rejected, {s['failed']} failed",
        "",
        f"gate: {g['registered']} predicates registered; {g['in_scope']} in scope for this pipeline; {g['evaluated']} evaluated over {s['declared']} steps, both phases",
        f"  fired: {g['fired']['block']} block, {g['fired']['flag']} flag, {g['fired']['log']} log",
    ]
    if g["flags"]:
        lines.append("  flags:")
        for f in g["flags"]:
            lines.append(
                f'    {f["predicate"]:<28} {f["step"]:<14} {f["verdict"]:<9} {f["reviewer"] or "-":<10} {f["date"] or "-":<11} {f["via"] or "-":<8} "{f["reason"] or ""}"'
            )
    lines.append("  decision points without predicate coverage:")
    lines.append(
        "    "
        + (", ".join(g["uncovered_decision_points"]) if g["uncovered_decision_points"] else "none")
    )
    lines.append(
        "  ungated steps: " + (", ".join(g["ungated_steps"]) if g["ungated_steps"] else "none")
    )
    lines.append("")
    lines.append("judgment:")
    if d["judgment"]:
        for j in d["judgment"]:
            lines.append(
                f"  {j['module']}: {j['items']} items x {j['replicates']} replicates; {j['agreed']} agreed, {j['self_uncertain']} self_uncertain, {j['run_disagreement']} run_disagreement"
            )
            lines.append(
                f"    reviews: {j['accepted']} accepted, {j['override']} override, {j['unresolved']} unresolved; override rate this run {j['override']}/{j['items']}; cumulative for this module version {j['cumulative_overrides']}/{j['cumulative_items']}"
            )
    else:
        lines.append("  none")
    lines.append("")
    lines.append("controls (last passing run per module version):")
    if d["controls"]:
        for c in d["controls"]:
            metrics = ", ".join(f"{k} {v}" for k, v in sorted(c["metrics"].items()))
            lines.append(f"  {c['module']}  {c['date']}  {c['control']}: {metrics}")
    else:
        lines.append("  none recorded")
    lines.append("")
    as_rep = (
        f" (env verified {e['env_verified']}, as reported {len(e['as_reported'])}: {', '.join(e['as_reported'])})"
        if e["operator_run"]
        else ""
    )
    lines.append("execution:")
    lines.append(
        f"  {e['operator_run']} steps operator-run{as_rep}, {e['engine_run']} engine-run; {e['plan_drift']} plan drift"
    )
    lines.append("")
    lines.append("reproducibility:")
    lines.append(
        f"  seeds set on {r['seeded']}/{r['stochastic_steps']} stochastic steps; env digest {r['env_digest']}"
    )
    inv = r["invocations"]
    if inv:
        lines.append(
            f"  judgment invocations stored ({inv['count']}), not bit-reproducible; via {', '.join(inv['via'])}, isolation {', '.join(inv['isolation'])}; model as reported: {', '.join(inv['models'])}"
        )
    else:
        lines.append("  no judgment invocations")
    lines.append("")
    lines.append("not checked: anything not listed above")
    return "\n".join(lines) + "\n"
