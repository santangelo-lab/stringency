"""`submit <ticket>` (design 3.4 steps 3 through 5): collect the declared outputs, hash and
validate them, run the extractor engine-side, parse the evidence, and run plan drift and the
post-gate."""

from __future__ import annotations

from pathlib import Path

from stringency.artifacts import place_output
from stringency.exit_codes import ConfigError, FailedError
from stringency.machine import StepStatus, step_status, transition
from stringency.operator_exec.envcheck import env_status
from stringency.operator_exec.evidence import Observed, guess_kind, parse_evidence
from stringency.runs import RunContext
from stringency.steps import (
    ExecInfo,
    StepOutcome,
    action_from_row,
    finish,
    plan_step,
    script_blob,
    write_execution,
)


def submit(
    rc: RunContext,
    ticket: str,
    outputs: dict[str, Path],
    evidence: list[Path],
    *,
    command: str | None = None,
) -> StepOutcome:
    """Reads: actions (by ticket), steps. Writes: everything `finish` writes, plus the
    evidence copies under the step directory. `command` is the operator's own account of what
    it ran; it lands in `executions.command` and, like everything else on an operator row, is
    as reported."""
    store = rc.store
    row = store.one("SELECT * FROM actions WHERE ticket = ? AND run_id = ?", (ticket, rc.run_id))
    if row is None:
        raise ConfigError(
            f"no ticket {ticket} in run {rc.run_id}; outputs without a ticket cannot be submitted"
        )
    action = action_from_row(row)
    if step_status(store, rc.run_id, action.step_id) != StepStatus.AWAITING_EXECUTION:
        raise ConfigError(
            f"ticket {ticket}: step {action.step_id} is {step_status(store, rc.run_id, action.step_id)}, not awaiting execution"
        )
    plan = plan_step(rc, action.step_id, action.attempt)
    m = plan.module.manifest
    missing = [n for n in m.outputs if n not in outputs]
    if missing:
        raise ConfigError(f"ticket {ticket}: declared output(s) not supplied: {', '.join(missing)}")
    for n, p in outputs.items():
        if n not in m.outputs:
            raise ConfigError(f"ticket {ticket}: {n} is not an output of {plan.module.ref}")
        if not Path(p).exists():
            raise ConfigError(f"ticket {ticket}: output {n} does not exist at {p}")
    transition(store, rc.run_id, action.step_id, StepStatus.RUNNING, payload={"ticket": ticket})
    plan.step_dir.mkdir(parents=True, exist_ok=True)
    produced = {n: place_output(Path(p), plan.output_paths[n]) for n, p in outputs.items()}

    observed = Observed()
    evidence_paths: list[str] = []
    ev_dir = plan.step_dir / "evidence"
    for src in evidence:
        src = Path(src)
        if not src.exists():
            raise ConfigError(f"evidence file {src} does not exist")
        kind = next((e.kind for e in m.evidence if Path(e.path).name == src.name), guess_kind(src))
        dest = place_output(src, ev_dir / src.name)
        evidence_paths.append(str(dest))
        observed.merge(parse_evidence(kind, dest))
    if not evidence and m.evidence:
        observed.notes.append(
            "no evidence supplied; manifest expects " + ", ".join(e.kind for e in m.evidence)
        )
    info = ExecInfo(
        runner="operator",
        env_status=env_status(observed, m.env, rc.project.method_root / "envs"),
        command=command,
        exit_code=max(observed.exit_codes) if observed.exit_codes else None,
        evidence_paths=evidence_paths,
        observed=observed.to_json(),
        script_blob=script_blob(plan.module),  # as on disk now; exec.script_drift compares
    )
    if any(code != 0 for code in observed.exit_codes):
        write_execution(rc, action, plan, info)
        transition(
            store,
            rc.run_id,
            action.step_id,
            StepStatus.FAILED,
            payload={"exit_codes": observed.exit_codes},
        )
        rc.refresh_status()
        raise FailedError(
            f"step {action.step_id} failed: evidence reports exit code(s) {observed.exit_codes}"
        )
    return finish(rc, action, plan, produced, info)


def submit_failed(
    rc: RunContext,
    ticket: str,
    *,
    reason: str,
    exit_code: int = 1,
    evidence: list[Path] | None = None,
    command: str | None = None,
) -> StepOutcome:
    """The operator reports that the ticket's external run failed (Lane A item 5, 2026-09-23):
    the step goes awaiting_execution -> running -> failed with the reason in the event payload,
    an executions row records the reported exit code and command, and the attempt closes so
    `propose` can open the next one on the same run. Reads: actions (by ticket), steps. Writes:
    steps, step_events, executions, evidence copies under the step directory."""
    store = rc.store
    row = store.one("SELECT * FROM actions WHERE ticket = ? AND run_id = ?", (ticket, rc.run_id))
    if row is None:
        raise ConfigError(f"no ticket {ticket} in run {rc.run_id}")
    action = action_from_row(row)
    if step_status(store, rc.run_id, action.step_id) != StepStatus.AWAITING_EXECUTION:
        raise ConfigError(
            f"ticket {ticket}: step {action.step_id} is {step_status(store, rc.run_id, action.step_id)}, not awaiting execution"
        )
    if not reason.strip():
        raise ConfigError("--failed needs --reason")
    if exit_code == 0:
        raise ConfigError("--failed reports a failure; --exit-code must be non-zero")
    plan = plan_step(rc, action.step_id, action.attempt)
    m = plan.module.manifest
    transition(store, rc.run_id, action.step_id, StepStatus.RUNNING, payload={"ticket": ticket})
    plan.step_dir.mkdir(parents=True, exist_ok=True)
    observed = Observed()
    evidence_paths: list[str] = []
    ev_dir = plan.step_dir / "evidence"
    for src in evidence or []:
        src = Path(src)
        if not src.exists():
            raise ConfigError(f"evidence file {src} does not exist")
        kind = next((e.kind for e in m.evidence if Path(e.path).name == src.name), guess_kind(src))
        dest = place_output(src, ev_dir / src.name)
        evidence_paths.append(str(dest))
        observed.merge(parse_evidence(kind, dest))
    observed.notes.append(f"operator reported failure: {reason}")
    info = ExecInfo(
        runner="operator",
        env_status=env_status(observed, m.env, rc.project.method_root / "envs"),
        command=command,
        exit_code=exit_code,
        evidence_paths=evidence_paths,
        observed=observed.to_json(),
        script_blob=script_blob(plan.module),
    )
    write_execution(rc, action, plan, info)
    transition(
        store,
        rc.run_id,
        action.step_id,
        StepStatus.FAILED,
        payload={"exit_code": exit_code, "reason": reason, "reported_by": "operator"},
    )
    rc.refresh_status()
    return StepOutcome(
        action.step_id,
        StepStatus.FAILED,
        action,
        message=f"failed: step {action.step_id} reported failed by the operator ({reason}); "
        f"`stringency propose {action.step_id}` opens the next attempt",
    )
