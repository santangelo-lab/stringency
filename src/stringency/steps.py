"""Run one step end to end (design 3.4, 3.5, 7.1).

`propose` constructs the Action, writes it, and runs the pre-gate. `execute_engine` runs an
admissible deterministic or report step through the executor. `finish` is the shared
post-execution path for both runners: hash and record outputs, validate schemas, extract
state, snapshot, write the execution row, run the post-gate, and settle the step.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.actions import Action, build_action, write_action
from stringency.artifacts import record_output, step_outputs
from stringency.clock import now_iso
from stringency.executor.base import Executor, Job
from stringency.executor.local import interpreter_for
from stringency.exit_codes import ConfigError, RefusedError
from stringency.extract import extract_object
from stringency.gate import GateResult, evaluate
from stringency.holds import HoldOutcome, HoldRequest, open_hold
from stringency.machine import RETRYABLE, StepStatus, step_status, transition
from stringency.modules import Module
from stringency.pipelines import StepDecl
from stringency.predicates import registry
from stringency.predicates.context import EvidenceTable, OutputBundle, OutputInfo
from stringency.runs import RunContext
from stringency.schemas import validate
from stringency.state import ObjectState, State, store_snapshot
from stringency.tables import load_table

EXT = {"csv": "csv", "tsv": "tsv", "json": "json", "jsonl": "jsonl", "md": "md", "txt": "txt"}


@dataclass(frozen=True)
class ResolvedInput:
    name: str
    path: Path
    digest: str  # bare hex
    type: str


@dataclass(frozen=True)
class StepPlan:
    step: StepDecl
    module: Module
    runner: str
    attempt: int
    inputs: dict[str, ResolvedInput]
    output_paths: dict[str, Path]
    step_dir: Path
    design: dict[str, Any] = field(default_factory=dict)  # the bound design, as the job sees it
    objective: dict[str, Any] = field(default_factory=dict)  # the bound objective (E1)


@dataclass
class Proposal:
    action: Action
    plan: StepPlan
    gate: GateResult
    status: StepStatus
    holds: list[HoldOutcome] = field(default_factory=list)

    @property
    def ticket(self) -> str | None:
        return self.action.ticket


@dataclass
class ExecInfo:
    runner: str
    env_status: str
    command: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    evidence_paths: list[str] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)
    script_blob: str | None = None  # hash of the entry script as it was when it ran


@dataclass
class StepOutcome:
    step_id: str
    status: StepStatus
    action: Action
    gate: GateResult | None = None
    holds: list[HoldOutcome] = field(default_factory=list)
    message: str = ""


# -- planning ----------------------------------------------------------------------


def runner_for(rc: RunContext, step: StepDecl, module: Module) -> str:
    """Judgment modules are always engine-run (design 3.5): the evidence the judge sees and the
    harness calls are made by the engine, never by the party being gated."""
    if module.manifest.kind == "judgment":
        return "engine"
    return step.runner or module.manifest.runner or rc.project.config.execution


def resolve_inputs(rc: RunContext, step: StepDecl, module: Module) -> dict[str, ResolvedInput]:
    """`$inputs.<name>` from the manifest; `$steps.<id>.<out>` from that step's produced artifacts."""
    out: dict[str, ResolvedInput] = {}
    inputs_by_name = rc.project.inputs.by_name()
    for name, ref in step.refs().items():
        spec = module.manifest.inputs.get(name)
        if ref.kind == "inputs":
            item = inputs_by_name.get(ref.name)
            if item is None:
                raise ConfigError(f"step {step.id}: no input named {ref.name} in inputs.yml")
            out[name] = ResolvedInput(name, Path(item.path), item.blake3, item.type)
        else:
            produced = step_outputs(rc.store, rc.run_id, ref.name)
            row = produced.get(ref.output or "")
            if row is None:
                raise ConfigError(f"step {step.id}: {ref} has not been produced in run {rc.run_id}")
            out[name] = ResolvedInput(
                name, Path(row["path"]), row["hash"], spec.type if spec else row["kind"]
            )
    return out


def plan_step(rc: RunContext, step_id: str, attempt: int) -> StepPlan:
    step = rc.project.pipeline.step(step_id)
    module = rc.project.modules.require(step.module)
    step_dir = rc.project.step_dir(rc.run_id, step_id)
    output_paths = {
        name: step_dir / f"{name}.{EXT.get(spec.format or '', spec.format or 'out')}"
        for name, spec in module.manifest.outputs.items()
    }
    return StepPlan(
        step=step,
        module=module,
        runner=runner_for(rc, step, module),
        attempt=attempt,
        inputs=resolve_inputs(rc, step, module),
        output_paths=output_paths,
        step_dir=step_dir,
        design=rc.project.design.model_dump(),
        objective=rc.project.objective.model_dump(),
    )


# -- propose: action + pre-gate ----------------------------------------------------------


def propose(
    rc: RunContext,
    step_id: str,
    proposed: dict[str, Any] | None = None,
    rationale: str | None = None,
    source: str = "agent",
) -> Proposal:
    """Construct the Action, write it, run the pre-gate, and settle the step as admissible,
    held, or blocked (design 3.4 step 1, 7.1). For operator-run steps an admissible action
    becomes a ticket and the step awaits execution.

    Writes: actions, messages (rationale), predicate_results, steps, step_events, holds.
    """
    store = rc.store
    if not rc.project.pipeline.has_step(step_id):
        raise ConfigError(f"no step {step_id} in pipeline {rc.project.pipeline.name}")
    current = step_status(store, rc.run_id, step_id)
    if current not in RETRYABLE:
        raise RefusedError(f"step {step_id} is {current}; it cannot be proposed now")
    prev_attempt = (
        store.scalar(
            "SELECT attempt FROM steps WHERE run_id = ? AND step_id = ?", (rc.run_id, step_id)
        )
        or 0
    )
    attempt = int(prev_attempt) + 1
    plan = plan_step(rc, step_id, attempt)
    rationale_ref = None
    if rationale:
        rationale_ref = hashing.hash_text(rationale)
        store.store_message(rationale_ref, rationale)
    action = build_action(
        run_id=rc.run_id,
        step=plan.step,
        module=plan.module,
        attempt=attempt,
        input_digests={k: v.digest for k, v in plan.inputs.items()},
        proposed=proposed,
        rationale_ref=rationale_ref,
        source_label=source,
    )
    if plan.runner == "operator":
        action = action.with_ticket(action.action_id)
    with store.transaction():
        write_action(store, action)
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.PROPOSED,
            attempt=attempt,
            payload={"action_id": action.action_id},
        )
    state = rc.current_state()
    ctx = rc.gate_context("pre", action, state)
    gate = evaluate(
        ctx,
        registry=registry,
        store=store,
        policy_digest=rc.policy_digest,
        module=plan.module.manifest,
        runner=plan.runner,
    )
    holds: list[HoldOutcome] = []
    if gate.blocked:
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.BLOCKED,
            payload={"predicates": [r.spec.id for r in gate.blocked]},
        )
        rc.refresh_status()
        return Proposal(action, plan, gate, StepStatus.BLOCKED)
    if gate.flagged:
        for r in gate.flagged:
            holds.append(
                open_hold(
                    store,
                    HoldRequest(
                        run_id=rc.run_id,
                        step_id=step_id,
                        kind="flag",
                        reason=f"{r.spec.id}: {r.verdict.reason}",
                        waits_on_role="reviewer",
                        bound_module_version=plan.module.ref,
                        bound_input_digest=action.input_digest,
                        bound_params_hash=action.params_hash,
                        context={
                            "predicate": r.spec.ref,
                            "phase": "pre",
                            "evidence": r.verdict.evidence,
                        },
                    ),
                )
            )
        if any(not h.rebound for h in holds):
            transition(
                store,
                rc.run_id,
                step_id,
                StepStatus.HELD,
                payload={"holds": [h.hold_id for h in holds if not h.rebound]},
            )
            rc.refresh_status()
            _write_packets(rc, step_id)
            return Proposal(action, plan, gate, StepStatus.HELD, holds)
    transition(store, rc.run_id, step_id, StepStatus.ADMISSIBLE)
    status = StepStatus.ADMISSIBLE
    if plan.runner == "operator":
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.AWAITING_EXECUTION,
            payload={"ticket": action.ticket},
        )
        write_job_file(action, plan)
        status = StepStatus.AWAITING_EXECUTION
    rc.refresh_status()
    return Proposal(action, plan, gate, status, holds)


def resume_after_hold(rc: RunContext, step_id: str) -> Proposal:
    """A pre-phase hold was accepted: rebuild the proposal view for the admissible step."""
    store = rc.store
    row = store.one(
        "SELECT * FROM actions WHERE run_id = ? AND step_id = ? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    if row is None:
        raise ConfigError(f"no action for {step_id}")
    action = action_from_row(row)
    plan = plan_step(rc, step_id, action.attempt)
    if (
        plan.runner == "operator"
        and step_status(store, rc.run_id, step_id) == StepStatus.ADMISSIBLE
    ):
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.AWAITING_EXECUTION,
            payload={"ticket": action.ticket},
        )
        write_job_file(action, plan)
    return Proposal(action, plan, GateResult("pre", ()), step_status(store, rc.run_id, step_id))


def action_from_row(row: Any) -> Action:
    return Action(
        action_id=row["action_id"],
        run_id=row["run_id"],
        step_id=row["step_id"],
        attempt=row["attempt"],
        operation=row["operation"],
        module=row["module"],
        parameters=json.loads(row["params_json"]),
        param_source=json.loads(row["param_source_json"] or "{}"),
        inputs=json.loads(row["inputs_json"]),
        input_digest=row["input_digest"],
        params_hash=row["params_hash"],
        proposed_by=row["proposed_by"],
        rationale_ref=row["rationale_ref"],
        ticket=row["ticket"],
        proposed_at=row["proposed_at"],
    )


# -- engine runner -------------------------------------------------------------------------


def job_for(action: Action, plan: StepPlan, script: Path) -> Job:
    m = plan.module.manifest
    seed = action.parameters.get(m.seed_param) if m.stochastic and m.seed_param else None
    return Job(
        command=interpreter_for(script),
        env_name=m.env,
        cwd=plan.step_dir,
        bind_paths=[p.path.parent for p in plan.inputs.values()] + [plan.step_dir],
        stdin_json={
            "inputs": {k: str(v.path) for k, v in plan.inputs.items()},
            "params": action.parameters,
            "outputs": {k: str(v) for k, v in plan.output_paths.items()},
            "output_dir": str(plan.step_dir),
            "seed": seed,
            "design": plan.design,
            "objective": plan.objective,
        },
        timeout=None,
        stdout_path=plan.step_dir / "stdout.txt",
        stderr_path=plan.step_dir / "stderr.txt",
    )


JOB_FILE = "job.json"


def script_blob(module: Module) -> str | None:
    """blake3 of the module's entry script as it is on disk now, or None without a script.
    Hashed at run open for every module (runs.py), before an engine run, and at `submit`."""
    script = module.entry_script
    if script is None or not script.exists():
        return None
    return hashing.hash_file(script)


def script_relpath(rc: RunContext, module: Module) -> str | None:
    script = module.entry_script
    if script is None:
        return None
    try:
        return str(script.relative_to(rc.project.method_root))
    except ValueError:
        return str(script)


def job_log_path(plan: StepPlan) -> Path:
    """Where the ticket tells the operator to send the script's output: the declared
    `job_log` evidence path under the step directory, else `run.log` there."""
    for e in plan.module.manifest.evidence:
        if e.kind == "job_log":
            return plan.step_dir / e.path
    return plan.step_dir / "run.log"


def write_job_file(action: Action, plan: StepPlan) -> Path | None:
    """Create the step directory and write `job.json`, the stdin the engine itself would feed
    the module script (design 3.4 step 1). Writes: `runs/<run>/<step>/job.json` only; the
    file is a ticket artifact like a dispatch request and carries no sidecar."""
    script = plan.module.entry_script
    if script is None:
        return None
    job = job_for(action, plan, script)
    plan.step_dir.mkdir(parents=True, exist_ok=True)
    path = plan.step_dir / JOB_FILE
    path.write_text(json.dumps(dict(job.stdin_json or {}), indent=2, sort_keys=True) + "\n")
    return path


def exec_line(executor: Executor, action: Action, plan: StepPlan) -> str | None:
    """The exact shell line an operator runs for the ticket: the executor's argv for the job,
    stdin from `job.json`, both streams to the job log."""
    script = plan.module.entry_script
    if script is None:
        return None
    argv = executor.command_line(job_for(action, plan, script))
    return (
        shlex.join(argv)
        + f" < {shlex.quote(str(plan.step_dir / JOB_FILE))}"
        + f" > {shlex.quote(str(job_log_path(plan)))} 2>&1"
    )


def execute_engine(rc: RunContext, proposal: Proposal) -> StepOutcome:
    """Run an admissible deterministic or report step through the executor (design 3.4)."""
    plan, action = proposal.plan, proposal.action
    kind = plan.module.manifest.kind
    if kind == "judgment":
        from stringency.judgment import execute_judgment

        return execute_judgment(rc, proposal)
    store = rc.store
    if step_status(store, rc.run_id, action.step_id) != StepStatus.ADMISSIBLE:
        raise RefusedError(f"step {action.step_id} is not admissible")
    script = plan.module.entry_script
    if script is None:
        raise ConfigError(f"module {plan.module.ref} has no entry script")
    transition(store, rc.run_id, action.step_id, StepStatus.RUNNING)
    plan.step_dir.mkdir(parents=True, exist_ok=True)
    blob = script_blob(plan.module)  # hashed before it runs; exec.script_drift compares
    res = rc.executor.run(job_for(action, plan, script))
    info = ExecInfo(
        runner="engine",
        env_status="verified" if res.env_digest else "as_reported",
        command=res.command,
        exit_code=res.exit_code,
        duration_ms=res.duration_ms,
        stdout_path=str(res.stdout_path),
        stderr_path=str(res.stderr_path),
        script_blob=blob,
    )
    if res.exit_code != 0:
        write_execution(rc, action, plan, info)
        transition(
            store,
            rc.run_id,
            action.step_id,
            StepStatus.FAILED,
            payload={"exit_code": res.exit_code, "timed_out": res.timed_out},
        )
        rc.refresh_status()
        tail = res.stderr().strip()[-400:]
        return StepOutcome(
            action.step_id,
            StepStatus.FAILED,
            action,
            message=f"step {action.step_id} failed: exit {res.exit_code}\n{tail}",
        )
    produced = {k: p for k, p in plan.output_paths.items() if p.exists()}
    return finish(rc, action, plan, produced, info)


# -- shared post-execution path ------------------------------------------------------------


def write_execution(rc: RunContext, action: Action, plan: StepPlan, info: ExecInfo) -> None:
    """Writes: executions. `env_digest` is set only when the environment was verified
    (`env_status = verified`); the digest the manifest expected always goes in
    `expected_env_digest`, so an as-reported execution never reads as verified."""
    expected = rc.env_digests.get(plan.module.manifest.env)
    rc.store.insert(
        "executions",
        {
            "action_id": action.action_id,
            "runner": info.runner,
            "ticket": action.ticket,
            "env_name": plan.module.manifest.env,
            "env_digest": expected if info.env_status == "verified" else None,
            "expected_env_digest": expected,
            "env_status": info.env_status,
            "command": info.command,
            "script_blob": info.script_blob,
            "exit_code": info.exit_code,
            "duration_ms": info.duration_ms,
            "stdout_path": info.stdout_path,
            "stderr_path": info.stderr_path,
            "evidence_paths_json": info.evidence_paths,
            "observed_params_json": info.observed,
            "ts": now_iso(),
        },
    )


def validate_output(plan: StepPlan, name: str, path: Path) -> str | None:
    schema = plan.module.output_schema_for(name)
    if schema is None:
        return None
    spec = plan.module.manifest.outputs[name]
    try:
        if spec.format == "jsonl":
            errors: list[str] = []
            for i, line in enumerate(path.read_text().splitlines(), start=1):
                if line.strip():
                    errors += [f"line {i}: {e}" for e in validate(json.loads(line), schema)]
        else:
            errors = validate(json.loads(path.read_text()), schema)
    except json.JSONDecodeError as e:
        return f"invalid JSON: {e}"
    return "; ".join(errors) if errors else None


def evidence_tables_for(plan: StepPlan) -> dict[str, EvidenceTable]:
    """Table inputs of the step as evidence tables (judgment: the declared evidence; report: every table input)."""
    m = plan.module.manifest
    names = (
        m.judgment.evidence if m.judgment else [n for n, s in m.inputs.items() if s.type == "table"]
    )
    key = m.judgment.item_key if m.judgment else None
    out: dict[str, EvidenceTable] = {}
    for n in names:
        ri = plan.inputs.get(n)
        if ri is not None and ri.type == "table":
            out[n] = load_table(ri.path, n, key)
    return out


def finish(
    rc: RunContext,
    action: Action,
    plan: StepPlan,
    produced: dict[str, Path],
    info: ExecInfo,
    *,
    bundle_extra: dict[str, Any] | None = None,
    extra_holds: list[HoldOutcome] | None = None,
) -> StepOutcome:
    """Design 3.4 steps 3 through 6 for either runner.

    Writes: artifacts (with sidecars), state_snapshots, executions, predicate_results, holds,
    steps, step_events. Marks outputs `rejected` on a post-gate block.
    """
    store = rc.store
    m = plan.module.manifest
    step_id = action.step_id
    missing = [n for n in m.outputs if n not in produced]
    if missing:
        write_execution(rc, action, plan, info)
        transition(
            store, rc.run_id, step_id, StepStatus.FAILED, payload={"missing_outputs": missing}
        )
        rc.refresh_status()
        return StepOutcome(
            step_id,
            StepStatus.FAILED,
            action,
            message=f"step {step_id} produced no {', '.join(missing)}",
        )

    outputs: dict[str, OutputInfo] = {}
    schema_errors: dict[str, str] = {}
    artifact_ids: list[str] = []
    digests: dict[str, str] = {}
    for name, path in produced.items():
        aid, digest = record_output(
            store,
            run_id=rc.run_id,
            step_id=step_id,
            action_id=action.action_id,
            name=name,
            path=path,
            kind=m.outputs[name].type,
        )
        artifact_ids.append(aid)
        digests[name] = hashing.prefixed(digest)
        err = validate_output(plan, name, path)
        if err:
            schema_errors[name] = err
        outputs[name] = OutputInfo(
            name,
            m.outputs[name].type,
            str(path),
            hashing.prefixed(digest),
            None if err is None else False,
        )

    # state extraction on object outputs (the engine runs the extractor, never the agent)
    prev = rc.current_state()
    objects: dict[str, ObjectState] = {}
    ext_name, ext_version = "none", "0"
    for name, spec in m.outputs.items():
        if spec.type in rc.project.plugin.object_types:
            ext = extract_object(
                rc.project.plugin,
                rc.executor,
                object_type=spec.type,
                object_path=produced[name],
                design=rc.project.design.model_dump(),
                env_name=m.env,
                workdir=plan.step_dir / f"extract-{name}",
            )
            objects[name] = ObjectState(type=spec.type, digest=digests[name], summary=ext.summary)
            ext_name, ext_version = ext.extractor, ext.version
            (plan.step_dir / f"state-{name}.json").write_text(
                json.dumps(ext.summary, indent=2, sort_keys=True)
            )
    state: State = prev.advanced(step_id, m.operation, action.parameters, objects, digests)
    store_snapshot(store, rc.run_id, step_id, "post", state, ext_name, ext_version)
    write_execution(rc, action, plan, info)
    transition(store, rc.run_id, step_id, StepStatus.PRODUCED)

    prose = None
    for name, spec in m.outputs.items():
        if spec.type == "prose":
            prose = produced[name].read_text()
    extra = dict(bundle_extra or {})
    observed = dict(info.observed)
    if info.script_blob:
        observed["script"] = {"path": script_relpath(rc, plan.module), "blob": info.script_blob}
    bundle = OutputBundle(
        outputs=outputs,
        prose=prose,
        evidence_tables=extra.pop("evidence_tables", evidence_tables_for(plan)),
        observed=observed,
        env_status=info.env_status,
        schema_errors=schema_errors,
        **extra,
    )
    ctx = rc.gate_context("post", action, state, bundle)
    gate = evaluate(
        ctx,
        registry=registry,
        store=store,
        policy_digest=rc.policy_digest,
        module=m,
        runner=info.runner,
    )
    return settle_post(rc, action, plan, gate, artifact_ids, extra_holds=list(extra_holds or []))


def _write_packets(rc: RunContext, step_id: str) -> None:
    """Review packets for the step's open holds (review-ux layer 2). Writes files under
    `runs/<run>/<step>/review/`; the trace is untouched."""
    from stringency.review_render import write_step_packets

    write_step_packets(rc.project, rc.run_id, step_id)


def settle_post(
    rc: RunContext,
    action: Action,
    plan: StepPlan,
    gate: GateResult,
    artifact_ids: list[str],
    *,
    extra_holds: list[HoldOutcome],
) -> StepOutcome:
    """Post-gate verdicts and item holds to a step status (design 7.1)."""
    store = rc.store
    step_id = action.step_id
    if gate.blocked:
        for aid in artifact_ids:
            store.set_artifact_flag(aid, "status", "rejected")
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.REJECTED,
            payload={"predicates": [r.spec.id for r in gate.blocked]},
        )
        rc.refresh_status()
        return StepOutcome(
            step_id,
            StepStatus.REJECTED,
            action,
            gate,
            message="rejected: " + "; ".join(r.line() for r in gate.blocked),
        )
    holds = list(extra_holds)
    # A flag that fires while item holds are open is deferred: the post-phase predicates are
    # evaluated again on the decided consensus when the last item hold settles
    # (`judgment.resettle_after_item_holds`), and the flag holds open then (design 7.1, 8.4).
    item_pending = [h for h in holds if not h.rebound]
    deferred: list[str] = []
    for r in gate.flagged:
        if item_pending:
            deferred.append(r.spec.ref)
            continue
        holds.append(
            open_hold(
                store,
                HoldRequest(
                    run_id=rc.run_id,
                    step_id=step_id,
                    kind="flag",
                    reason=f"{r.spec.id}: {r.verdict.reason}",
                    waits_on_role="reviewer",
                    bound_module_version=plan.module.ref,
                    bound_input_digest=action.input_digest,
                    bound_params_hash=action.params_hash,
                    context={
                        "predicate": r.spec.ref,
                        "phase": "post",
                        "evidence": r.verdict.evidence,
                    },
                ),
            )
        )
    pending = [h for h in holds if not h.rebound]
    if pending:
        payload: dict[str, Any] = {"holds": [h.hold_id for h in pending]}
        if deferred:
            payload["deferred_flags"] = deferred
        if step_status(store, rc.run_id, step_id) == StepStatus.HELD:
            # re-evaluated after the item holds settled: the step stays held on the new holds
            store.step_event(rc.run_id, step_id, "holds", payload)
        else:
            transition(store, rc.run_id, step_id, StepStatus.HELD, payload=payload)
        rc.refresh_status()
        _write_packets(rc, step_id)
        message = f"held: {len(pending)} hold(s) on {step_id}"
        if deferred:
            message += f"; {len(deferred)} flag(s) deferred until the item holds settle"
        return StepOutcome(step_id, StepStatus.HELD, action, gate, holds, message=message)
    transition(store, rc.run_id, step_id, StepStatus.COMPLETED)
    rc.refresh_status()
    return StepOutcome(
        step_id, StepStatus.COMPLETED, action, gate, holds, message=f"completed {step_id}"
    )
