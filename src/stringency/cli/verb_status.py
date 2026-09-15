"""`stringency status [--run] [--overrides [--module]] [--json]` (design 14.1, 7.6)."""

from __future__ import annotations

from typing import Any

import typer

from stringency.cli.common import emit, handle_errors
from stringency.holds import open_holds
from stringency.plain import plain_next, progress_sentence
from stringency.project import Project
from stringency.runloop import next_step
from stringency.runs import latest_run, load_run


def override_rates(project: Project, module: str | None = None) -> list[dict[str, Any]]:
    """Reads: reviews, holds, steps. Override and rejection rate per module version."""
    sql = (
        "SELECT s.module || '@' || s.module_version AS module, r.verdict, COUNT(*) AS n "
        "FROM reviews r JOIN holds h ON h.hold_id = r.hold_id "
        "JOIN steps s ON s.run_id = h.run_id AND s.step_id = h.step_id "
        "WHERE h.item_id IS NOT NULL "
    )
    params: tuple[Any, ...] = ()
    if module:
        sql += "AND s.module = ? "
        params = (module,)
    sql += "GROUP BY 1, 2 ORDER BY 1, 2"
    rows = project.store.all(sql, params)
    by: dict[str, dict[str, int]] = {}
    for r in rows:
        by.setdefault(r["module"], {})[r["verdict"]] = r["n"]
    out = []
    for mod, counts in by.items():
        total = sum(counts.values())
        out.append(
            {
                "module": mod,
                "reviews": total,
                "accept": counts.get("accept", 0),
                "override": counts.get("override", 0),
                "reject": counts.get("reject", 0),
                "override_rate": (counts.get("override", 0) / total) if total else 0.0,
                "rejection_rate": (counts.get("reject", 0) / total) if total else 0.0,
            }
        )
    return out


def status_payload(project: Project, run_id: str | None) -> dict[str, Any]:
    row = load_run(project, run_id).run if run_id else latest_run(project.store)
    confirm = project.confirm_status()
    payload: dict[str, Any] = {
        "schema": "stringency.status/1",
        "project_id": project.config.project_id,
        "profile": project.config.profile,
        "confirm": confirm,
        "run": None,
        "steps": [],
        "holds": [],
        "completed_steps": [],
        "plain": "",
    }
    ch = project.confirm_hold()
    if ch is not None and ch["resolved_by_review"] is None:
        payload["holds"].append(_hold_entry(project, ch))
    if row is None:
        payload["plain"] = _plain_no_run(project, ch)
        return payload
    rc = load_run(project, row["run_id"])
    payload["run"] = {
        "run_id": rc.run_id,
        "status": rc.status(),
        "started": row["started"],
        "ended": row["ended"],
        "git_sha": row["git_sha"],
        "policy_digest": row["policy_digest"],
        "parent_run_id": row["parent_run_id"],
    }
    payload["steps"] = [
        dict(s)
        for s in project.store.all(
            "SELECT step_id, module, module_version, status, attempt FROM steps WHERE run_id=? ORDER BY rowid",
            (rc.run_id,),
        )
    ]
    payload["holds"] += [_hold_entry(project, h) for h in open_holds(project.store, rc.run_id)]
    statuses = rc.step_status()
    payload["completed_steps"] = [
        s for s in project.pipeline.order() if statuses.get(s) == "completed"
    ]
    payload["plain"] = _plain_run(rc, statuses)
    return payload


def _plain_no_run(project: Project, confirm_hold: Any) -> str:
    if confirm_hold is not None and confirm_hold["resolved_by_review"] is None:
        return (
            "No run has started. The plan for this project waits for the owner "
            f"({project.config.roles.owner}) to confirm it."
        )
    return "No run has started."


def _plain_run(rc: Any, statuses: dict[str, str]) -> str:
    """`plain` for `status --json`: the same sentences `run --json` carries, from the same
    `next` reading; an abandoned run says so instead. Reads: steps, holds, actions."""
    if rc.run["status"] == "abandoned":
        return progress_sentence(rc.project.pipeline, statuses) + " The run was abandoned."
    nx = next_step(rc)
    return plain_next(
        rc.project.pipeline, rc.project.config.roles, nx.kind, nx.step_id, nx.detail, statuses
    )


def _hold_entry(project: Project, h: Any) -> dict[str, Any]:
    """One open hold as `status --json` lists it (improvement B2): id, kind, step, item, who."""
    return {
        "hold_id": h["hold_id"],
        "step_id": h["step_id"],
        "item_id": h["item_id"],
        "kind": h["kind"],
        "reason": h["reason"],
        "waits_on": h["waits_on_role"],
        "who": project.config.roles.reviewer
        if h["waits_on_role"] == "reviewer"
        else project.config.roles.owner,
    }


@handle_errors
def status(
    run_id: str | None = typer.Option(None, "--run"),
    overrides: bool = typer.Option(False, "--overrides"),
    module: str | None = typer.Option(None, "--module"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    project = Project.find()
    if overrides:
        rates = override_rates(project, module)
        lines = [
            f"{r['module']}: {r['reviews']} reviews, override {r['override']} ({r['override_rate']:.0%}), reject {r['reject']} ({r['rejection_rate']:.0%})"
            for r in rates
        ] or ["no item reviews yet"]
        emit({"schema": "stringency.overrides/1", "modules": rates}, as_json, "\n".join(lines))
        return
    payload = status_payload(project, run_id)
    lines = [
        f"project {payload['project_id']}  profile {payload['profile']}  confirm {payload['confirm']}"
    ]
    if payload["run"]:
        r = payload["run"]
        lines.append(f"run {r['run_id']}  status {r['status']}  method {r['git_sha'][:12]}")
        for s in payload["steps"]:
            lines.append(
                f"  {s['step_id']:<16} {s['status']:<20} {s['module']}@{s['module_version']} attempt {s['attempt']}"
            )
    else:
        lines.append("no runs yet")
    lines.append(payload["plain"])
    for h in payload["holds"]:
        item = f" item {h['item_id']}" if h["item_id"] else ""
        where = f" on {h['step_id']}{item}" if h["step_id"] else ""
        lines.append(
            f"  hold {h['hold_id']} ({h['kind']}{where}) waits on {h['waits_on']} {h['who']}; "
            f"run `stringency review --hold {h['hold_id']}`"
        )
    emit(payload, as_json, "\n".join(lines))
