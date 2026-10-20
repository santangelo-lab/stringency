"""The coverage report (design 12.2): generated, fixed in structure, never hand-edited.

Reads: runs, steps, predicate_results, holds, reviews, invocations, judgments, consensus,
executions, actions, controls_runs. Writes nothing.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from stringency import __version__
from stringency.egress import CLASS_NAMES
from stringency.gate import in_scope_specs
from stringency.predicates import registry
from stringency.runs import RunContext, captured_egress, captured_plugins, captured_upstream_lineage
from stringency.when import skip_reason


def decision_point_coverage(rc: RunContext) -> tuple[list[str], list[str]]:
    """(uncovered decision points as `step.param`, ungated steps). A decision point is covered
    when at least one predicate evaluated for that step declares `covers` for its operation.param
    or operation.*."""
    store = rc.store
    uncovered: list[str] = []
    ungated: list[str] = []
    for step in rc.pipeline.steps:
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        if st not in ("completed", "held", "rejected"):
            continue
        module = rc.module_for(step.id)
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
    """The predicates in scope for the run's topology; in open mode for every tool the method
    ships (the topology is whatever was asked) plus the steps run so far."""
    ids: set[str] = set()
    manifests = [(rc.module_for(s.id).manifest, s.runner) for s in rc.pipeline.steps]
    if rc.open_ended:
        manifests += [(m.manifest, "engine") for m in rc.project.tools()]
    for m, step_runner in manifests:
        runner = step_runner or m.runner or rc.project.config.execution
        for phase in ("pre", "post"):
            for s in in_scope_specs(
                registry, phase, operation=m.operation, module=m, runner=runner
            ):
                ids.add(s.id)
    return ids


def egress_coverage(
    captured: dict[str, Any] | None,
    completed: set[str],
    operator_steps: set[str],
    invocations: int,
) -> dict[str, Any] | None:
    """What left the machine on this run (backlog L1): each component recorded at run open,
    whether it was used (the harness when it was invoked, the hosted operator session always,
    operator-run steps and network-reaching modules when one of their steps completed), and
    the highest class reached. None when the run recorded no assessment."""
    if captured is None:
        return None
    rows: list[dict[str, Any]] = []
    for c in captured.get("components", []):
        ids = {str(s).split(" ")[0] for s in c.get("steps", [])}
        key = c.get("key", "")
        if key == "harness":
            used, detail = invocations > 0, f"{invocations} invocations"
        elif key == "operator.session":
            used, detail = c.get("class", 0) > 0, "as reported"
        elif key == "exec":
            ran = sorted(i for i in ids if i.endswith("_exec") or i == "exec")
            used, detail = bool(ran), "ran " + (", ".join(ran) or "none") + "; by enforcement"
        elif key == "operator.steps":
            ran = sorted(ids & operator_steps)
            used, detail = bool(ran), "ran " + (", ".join(ran) or "none") + "; as reported"
        else:
            ran = sorted(ids & completed)
            used, detail = bool(ran), "ran " + (", ".join(ran) or "none")
        rows.append(
            {
                "label": c.get("label"),
                "class": c.get("class", 0),
                "basis": c.get("basis"),
                "to": c.get("to"),
                "used": used,
                "detail": detail,
            }
        )
    reached = max((r["class"] for r in rows if r["used"]), default=0)
    return {
        "fingerprint": captured.get("fingerprint"),
        "report": captured.get("report"),
        "max_class": captured.get("max_class"),
        "assessed_class": captured.get("assessed_class"),
        "highest_reached": reached,
        "components": rows,
    }


def egress_line(e: dict[str, Any] | None) -> str:
    """One sentence for summary.md: the highest class reached against the ceiling."""
    if e is None:
        return "Data egress was not recorded for this run."
    reached = int(e["highest_reached"])
    ceiling = e.get("max_class")
    limit = (
        "no ceiling was declared"
        if ceiling is None
        else f"the ceiling is class {ceiling} {CLASS_NAMES[int(ceiling)]}"
    )
    return (
        f"Data egress: the highest class reached was {reached} {CLASS_NAMES[reached]}; {limit} "
        f"(report {e.get('report')})."
    )


def coverage_data(rc: RunContext) -> dict[str, Any]:
    store, run = rc.store, rc.run
    from stringency.audit import audit_lines

    trace_audit = list(audit_lines(store))
    project = rc.project
    steps = store.all(
        "SELECT step_id, status FROM steps WHERE run_id=? ORDER BY rowid", (rc.run_id,)
    )
    status_counts = Counter(s["status"] for s in steps)
    rows = store.all(
        "SELECT pr.*, a.step_id FROM predicate_results pr JOIN actions a ON a.action_id = pr.action_id "
        "WHERE a.run_id=? ORDER BY pr.rowid",
        (rc.run_id,),
    )
    # a predicate evaluated twice for one action and phase (a judgment step's post gate runs
    # again on the decided consensus once its item holds settle) counts once, by its last verdict
    latest: dict[tuple[str, str, str], Any] = {}
    for r in rows:
        latest[(r["action_id"], r["phase"], r["predicate_id"])] = r
    results = list(latest.values())
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
    for step in rc.pipeline.steps:
        m = rc.module_for(step.id).manifest
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
                "sign_off": kinds.get("sign_off", 0),
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
    stochastic = [s.id for s in rc.pipeline.steps if rc.module_for(s.id).manifest.stochastic]
    seeded = 0
    for sid in stochastic:
        a = store.one(
            "SELECT params_json FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC LIMIT 1",
            (rc.run_id, sid),
        )
        m = rc.module_for(sid).manifest
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
    # open mode: tools run without a current control (their outputs are untested), and the
    # upstream delivery's lineage captured at run open
    uncontrolled: list[str] = []
    if rc.open_ended:
        cur = rc.controls_current()
        for x in rc.on_demand():
            if x.get("kind") == "tool":
                ref = str(x["decl"].get("module"))
                if cur.get(ref, {}).get("status") != "current":
                    uncontrolled.append(
                        f"{x['step_id']} ({ref}: {cur.get(ref, {}).get('status', 'none')})"
                    )
    return {
        "trace_audit": trace_audit,
        "run_id": rc.run_id,
        "project_id": project.config.project_id,
        "pipeline": f"{project.pipeline.name}@{project.pipeline.version}",
        "open": {
            "uncontrolled_tools": uncontrolled,
            "exec_steps": [x["step_id"] for x in rc.on_demand() if x.get("kind") == "exec"],
            "upstream_lineage": captured_upstream_lineage(store, rc.run_id),
        }
        if rc.open_ended
        else None,
        "mode": project.config.mode,
        "profile": project.config.profile,
        "policy_version": run["policy_version"],
        "policy_digest": run["policy_digest"],
        "stringency_version": __version__,
        "plugins": captured_plugins(store, rc.run_id),
        "method_sha": run["git_sha"],
        "method_dirty": bool(run["git_dirty"]),
        "steps": {
            "declared": len(steps),
            **{
                k: status_counts.get(k, 0)
                for k in ("completed", "held", "blocked", "rejected", "failed", "skipped")
            },
            # conditional steps whose `when` was false: no predicate was evaluated on them (L13)
            "not_evaluated": [
                {"step": s["step_id"], "reason": skip_reason(store, rc.run_id, s["step_id"])}
                for s in steps
                if s["status"] == "skipped"
            ],
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
        "egress": egress_coverage(
            captured_egress(store, rc.run_id),
            {s["step_id"] for s in steps if s["status"] == "completed"},
            {e["step_id"] for e in operator},
            len(invs),
        ),
    }


def render_coverage(d: dict[str, Any]) -> str:
    g, s, e, r = d["gate"], d["steps"], d["execution"], d["reproducibility"]
    lines = [
        "stringency coverage report",
        f"run {d['run_id']} | project {d['project_id']} | pipeline {d['pipeline']} | mode {d['mode']} | profile {d['profile']}",
        f"policy {d['policy_version']} (blake3:{d['policy_digest'][:12]}) | stringency {d['stringency_version']}"
        + (
            " with " + ", ".join(f"{k} {v}" for k, v in sorted(d["plugins"].items()))
            if d.get("plugins")
            else ""
        )
        + f" | method {d['method_sha'][:12]} ({'dirty' if d['method_dirty'] else 'clean'})",
        "",
        f"steps: {s['declared']} declared, {s['completed']} completed, {s['held']} held, {s['blocked']} blocked, {s['rejected']} rejected, {s['failed']} failed"
        + (f", {s['skipped']} skipped" if s.get("skipped") else ""),
        *[f"  not evaluated: {n['step']} ({n['reason']})" for n in s.get("not_evaluated", [])],
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
    ta = d.get("trace_audit")
    if ta is None:
        lines.append("trace audited: not recorded for this run")
    elif not ta:
        lines.append("trace audited: no disagreement between the rows and their events")
    else:
        lines.append(f"trace audited: {len(ta)} disagreement(s) between the rows and their events:")
        for t in ta[:3]:
            lines.append(f"  {t}")
        if len(ta) > 3:
            lines.append(f"  and {len(ta) - 3} more; run `stringency audit`")
    lines.append("")
    eg = d.get("egress")
    if eg is None:
        lines.append("data egress: not recorded for this run")
    else:
        ceiling = eg["max_class"]
        limit = "none declared" if ceiling is None else f"class {ceiling} {CLASS_NAMES[ceiling]}"
        lines.append(f"data egress (ceiling {limit}; report {eg['report']}):")
        for c in eg["components"]:
            if c["used"]:
                lines.append(
                    f"  {c['label']}: class {c['class']} {CLASS_NAMES[c['class']]} to {c['to']}; "
                    f"{c['detail']}"
                )
        unused = [c["label"] for c in eg["components"] if not c["used"]]
        if unused:
            lines.append(f"  assessed but not used on this run: {', '.join(unused)}")
        hr = eg["highest_reached"]
        lines.append(f"  highest class reached: {hr} {CLASS_NAMES[hr]}")
    lines.append("")
    op = d.get("open")
    if op:
        lines.append("open mode:")
        lines.append(
            "  tools run without current controls: "
            + (", ".join(op["uncontrolled_tools"]) or "none")
        )
        lines.append("  scripts written in the session: " + (", ".join(op["exec_steps"]) or "none"))
        ex = d.get("explored") or {}
        for e in ex.get("rerun_counts", []):
            lines.append(
                f"  explored: {e['module']} {e['runs']} run(s), {e['distinct_params']} distinct parameter set(s), "
                f"{e.get('findings', 0)} cited by findings (steps {', '.join(e['steps'])})"
            )
        q = ex.get("questions") or {}
        lines.append(
            f"  questions: {q.get('person', 0)} in the person's own words, {q.get('suggested', 0)} suggested by the operator"
        )
        lines.append("  upstream lineage:")
        for u in op["upstream_lineage"] or []:
            if u.get("error"):
                lines.append(
                    f"    {u['input']}: run {u['run_id']} of {u['project']}: not readable ({u['error']})"
                )
                continue
            chain = " <- ".join(c["run_id"] for c in u.get("chain", []))
            dts = ", ".join(str(t)[:10] for t in u.get("deliveries", [])) or "none"
            lines.append(
                f"    {u['input']}: run {u['run_id']} of {u['project']} ({u.get('upstream_pipeline') or 'unknown'}); "
                f"ancestors {chain}; delivered {dts}"
            )
        if not op["upstream_lineage"]:
            lines.append("    none recorded")
        lines.append("")
        from stringency.summary import NOT_CHECKED_OPEN

        lines.append(NOT_CHECKED_OPEN)
        return "\n".join(lines) + "\n"
    lines.append("not checked: anything not listed above")
    return "\n".join(lines) + "\n"
