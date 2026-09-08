"""`next` and the `run` loop (design 7.1, 14.1, 14.2).

`next_step` returns the first pending step whose inputs are complete, or the current hold,
block, failure, ticket, or dispatch with its reason. `run` loops on it until something other
than a runnable step comes back, then exits with the matching code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from stringency.exit_codes import Exit
from stringency.gate import GateResult
from stringency.holds import open_holds
from stringency.machine import StepStatus
from stringency.operator_exec.tickets import job_spec, render_job_spec
from stringency.runs import RunContext, close_run, write_summary
from stringency.steps import (
    Proposal,
    StepOutcome,
    action_from_row,
    execute_engine,
    plan_step,
    propose,
    resume_after_hold,
)


@dataclass
class Next:
    kind: str  # runnable | held | blocked | rejected | failed | awaiting_execution | dispatching | completed
    step_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 0
    message: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "stringency.next/1",
            "kind": self.kind,
            "step_id": self.step_id,
            "exit_code": self.exit_code,
            "message": self.message,
            **self.detail,
        }


def hold_message(rc: RunContext, holds: list[Any]) -> str:
    """Terse by design (design 14.2): what is held, who it waits on, the one command."""
    h = holds[0]
    what = f"{h['step_id']}" + (f" item {h['item_id']}" if h["item_id"] else "")
    more = f" (+{len(holds) - 1} more)" if len(holds) > 1 else ""
    roles = rc.project.config.roles
    who = roles.owner if h["waits_on_role"] == "owner" else roles.reviewer
    return (
        f"held: hold {h['hold_id']} ({h['kind']} on {what}){more}; "
        f"waits on {h['waits_on_role']} {who}; "
        f"run `stringency review --hold {h['hold_id']}` in {rc.project.root}"
    )


def plan_template(rc: RunContext, step_id: str) -> dict[str, Any]:
    """What the coming step is (design 14.1 `next --json`)."""
    step = rc.project.pipeline.step(step_id)
    module = rc.project.modules.require(step.module)
    m = module.manifest
    params: dict[str, Any] = {}
    for name, schema in module.declared_params.items():
        decl = step.params.get(name)
        params[name] = {
            "schema": schema,
            "default": decl.default
            if decl
            else schema.get("default")
            if isinstance(schema, dict)
            else None,
            "range": decl.range if decl else None,
            "options": decl.options if decl else None,
            "fixed": decl.fixed if decl else True,
            "decision_point": name in m.decision_points,
        }
    vocab = list(rc.project.plugin.vocabulary(m.vocabulary) or ()) if m.vocabulary else None
    return {
        "step_id": step_id,
        "module": module.ref,
        "kind": m.kind,
        "operation": m.operation,
        "runner": step.runner or m.runner or rc.project.config.execution,
        "inputs": {k: str(v) for k, v in step.refs().items()},
        "parameters": params,
        "vocabulary": vocab,
        "outputs": {k: {"type": v.type, "format": v.format} for k, v in m.outputs.items()},
        "evidence": [{"kind": e.kind, "path": e.path} for e in m.evidence],
        "decision_points": list(m.decision_points),
        "gates": list(m.gates),
        "profile": rc.project.config.profile,
        "params_policy": rc.project.policy.profile(rc.project.config.profile).params,
    }


def next_step(rc: RunContext) -> Next:
    """Reads: steps, holds, actions, predicate_results."""
    statuses = rc.step_status()
    order = rc.project.pipeline.order()
    holds = open_holds(rc.store, rc.run_id)
    if holds:
        return Next(
            "held",
            holds[0]["step_id"],
            {"holds": [dict(h) for h in holds]},
            int(Exit.HELD),
            hold_message(rc, holds),
        )
    for sid in order:
        st = StepStatus(statuses[sid])
        if st == StepStatus.COMPLETED:
            continue
        if st == StepStatus.AWAITING_EXECUTION:
            row = rc.store.one(
                "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
                (rc.run_id, sid),
            )
            assert row is not None
            action = action_from_row(row)
            plan = plan_step(rc, sid, action.attempt)
            spec = job_spec(
                Proposal(action, plan, GateResult("pre", ()), st),
                rc.env_digests.get(plan.module.manifest.env),
            )
            return Next(
                "awaiting_execution",
                sid,
                {"job_spec": spec},
                int(Exit.AWAITING_EXECUTION),
                f"awaiting execution: ticket {action.ticket} for {sid}\n" + render_job_spec(spec),
            )
        if st == StepStatus.DISPATCHING:
            ddir = rc.project.step_dir(rc.run_id, sid) / "dispatch"
            n = len(list(ddir.glob("req_*.json")))
            return Next(
                "dispatching",
                sid,
                {"dispatch_dir": str(ddir), "requests": n},
                int(Exit.DISPATCHING),
                f"dispatching: {n} request(s) in {ddir}; have one fresh subagent answer each, then run again",
            )
        if st in (StepStatus.BLOCKED, StepStatus.REJECTED):
            row = rc.store.one(
                "SELECT action_id FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
                (rc.run_id, sid),
            )
            fired = (
                rc.store.all(
                    "SELECT predicate_id, phase, reason, evidence_json FROM predicate_results WHERE action_id=? AND fired=1 AND effective_disposition='block'",
                    (row["action_id"],),
                )
                if row
                else []
            )
            blocked_preds = [dict(f) for f in fired]
            names = (
                ", ".join(f"{p['predicate_id']} ({p['reason']})" for p in blocked_preds)
                or "unknown"
            )
            code = Exit.BLOCKED if st == StepStatus.BLOCKED else Exit.REJECTED
            word = "blocked" if st == StepStatus.BLOCKED else "rejected"
            return Next(
                word, sid, {"predicates": blocked_preds}, int(code), f"{word}: {sid} by {names}"
            )
        if st == StepStatus.FAILED:
            ev = rc.store.one(
                "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? AND event='status:failed' ORDER BY seq DESC LIMIT 1",
                (rc.run_id, sid),
            )
            return Next(
                "failed",
                sid,
                {"event": ev["payload_json"] if ev else None},
                int(Exit.FAILED),
                f"failed: {sid}",
            )
        if st in (
            StepStatus.PENDING,
            StepStatus.ADMISSIBLE,
            StepStatus.HELD,
            StepStatus.PROPOSED,
            StepStatus.RUNNING,
            StepStatus.PRODUCED,
        ):
            preds = rc.project.pipeline.step(sid).predecessors()
            if all(statuses.get(p) == "completed" for p in preds):
                return Next(
                    "runnable",
                    sid,
                    {"plan": plan_template(rc, sid), "status": str(st)},
                    0,
                    f"next: {sid}",
                )
            return Next(
                "runnable",
                sid,
                {
                    "plan": plan_template(rc, sid),
                    "status": str(st),
                    "waiting_on": [p for p in preds if statuses.get(p) != "completed"],
                },
                0,
                f"next: {sid} (waiting on predecessors)",
            )
    return Next("completed", None, {}, 0, f"run {rc.run_id} completed")


def outcome_to_next(rc: RunContext, out: StepOutcome) -> Next:
    return next_step(rc)


def run_loop(rc: RunContext, *, until: str | None = None) -> Next:
    """Loop on `next` until it returns something other than a runnable step (design 7.1)."""
    collected: set[str] = set()
    dispatched_now: set[str] = set()
    while True:
        nx = next_step(rc)
        if (
            nx.kind == "dispatching"
            and nx.step_id not in collected
            and nx.step_id not in dispatched_now
        ):
            # a step dispatched by an earlier `run`: collect if the responses are there
            collected.add(nx.step_id or "")
            ddir = rc.project.step_dir(rc.run_id, nx.step_id or "") / "dispatch"
            if any(ddir.glob("resp_*.json")) or _mock_dispatch(rc):
                resume_dispatching(rc, nx.step_id or "")
                continue
        if nx.kind != "runnable":
            if nx.kind == "completed":
                if rc.run["status"] != "completed":
                    close_run(rc, "completed")
                else:
                    write_summary(rc)
            elif nx.kind in ("blocked", "rejected", "failed"):
                rc.refresh_status()
            return nx
        sid = nx.step_id
        assert sid is not None
        if until is not None and rc.project.pipeline.order().index(
            sid
        ) > rc.project.pipeline.order().index(until):
            return Next("completed", None, {"until": until}, 0, f"stopped after {until}")
        st = StepStatus(rc.step_status()[sid])
        if st == StepStatus.PENDING:
            proposal = propose(rc, sid, rc.delta_for(sid) or None)
        elif st == StepStatus.ADMISSIBLE:
            proposal = resume_after_hold(rc, sid)
        else:
            return Next(
                str(st), sid, {}, int(Exit.INTERNAL), f"step {sid} is {st}; cannot continue"
            )
        if proposal.status in (StepStatus.BLOCKED, StepStatus.HELD, StepStatus.AWAITING_EXECUTION):
            continue  # next_step reports it
        out = execute_engine(rc, proposal)
        if out.status == StepStatus.DISPATCHING:
            dispatched_now.add(sid)  # this `run` stops here with exit 20; the next one collects
            continue
        if until is not None and sid == until:
            rc.refresh_status()
            return Next("completed", sid, {"until": until}, 0, f"stopped after {until}")


def resume_dispatching(rc: RunContext, step_id: str) -> StepOutcome:
    """Collect dispatch responses for a step (called by `run` when a step is dispatching)."""
    row = rc.store.one(
        "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    assert row is not None
    action = action_from_row(row)
    plan = plan_step(rc, step_id, action.attempt)
    from stringency.judgment import execute_judgment

    return execute_judgment(
        rc, Proposal(action, plan, GateResult("pre", ()), StepStatus.DISPATCHING)
    )


def _mock_dispatch(rc: RunContext) -> bool:
    """The mock in dispatch mode writes its own responses on collect, so collecting is safe."""
    import os

    return (
        rc.project.config.judgment_harness == "mock"
        and os.environ.get("STRINGENCY_MOCK_FAMILY") == "dispatch"
    )
