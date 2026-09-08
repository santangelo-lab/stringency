"""Runs (design 2.6, 9.1): open, resume, close, and the run-level captures.

`RunContext` is what every step operation works against: the project, the store, the run
row, the executor, the environment digests resolved at open, and the policy digest.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from typing import Any

from stringency import __version__, git, hashing
from stringency.actions import Action
from stringency.db.store import Store
from stringency.executor.base import Executor
from stringency.exit_codes import BlockedError, ConfigError, DirtyTreeError, HeldError, RefusedError
from stringency.gate import evaluate
from stringency.ids import new_id
from stringency.machine import all_step_status, derive_run_status
from stringency.predicates import registry
from stringency.predicates.context import GateContext
from stringency.project import Project
from stringency.state import ObjectState, State, latest_state, store_snapshot

OPEN_STATUSES = ("running", "held", "blocked", "failed")
CLOSED_STATUSES = ("completed", "abandoned")


@dataclass
class RunContext:
    project: Project
    run_id: str
    executor: Executor
    env_digests: dict[str, str | None]
    policy_digest: str
    input_digests_now: dict[str, str]
    git_dirty: bool = False
    allow_dirty_reason: str | None = None
    operator: dict[str, str | None] = field(default_factory=dict)

    @property
    def store(self) -> Store:
        return self.project.store

    @property
    def run(self) -> Any:
        return self.store.one("SELECT * FROM runs WHERE run_id = ?", (self.run_id,))

    def step_status(self) -> dict[str, str]:
        return all_step_status(self.store, self.run_id)

    def status(self) -> str:
        return derive_run_status(self.step_status(), self.project.pipeline.order())

    def refresh_status(self) -> str:
        """Derive the run status from its steps and record it when it changed.
        Writes: run_events, runs.status."""
        s = self.status()
        if self.run["status"] != s:
            self.store.set_run_status(self.run_id, s, ended=s == "completed")
            if s == "completed":
                write_summary(self)
        return s

    def current_state(self) -> State:
        """The state after the most recently completed step of the run (a rejected or failed
        step's snapshot is kept in the trace but is never the pre-state of anything), or the
        initial state with the input objects. Reads: state_snapshots, steps."""
        st = latest_state(self.store, self.run_id, completed_only=True)
        if st is not None:
            return st
        return self.project.initial_state(self.run_id, self.input_objects())

    def input_objects(self) -> dict[str, ObjectState]:
        summaries = self.project.input_summaries()
        out: dict[str, ObjectState] = {}
        for item in self.project.inputs.items:
            if item.type in self.project.plugin.object_types:
                out[item.name] = ObjectState(
                    type=item.type,
                    digest=hashing.prefixed(item.blake3),
                    summary=summaries.get(item.name, {}),
                )
        return out

    def delta_for(self, step_id: str) -> dict[str, Any]:
        """Parameter changes a fork declared for `step_id` (design 2.6), or {}."""
        import json

        raw = self.run["delta_json"]
        if not raw:
            return {}
        delta = json.loads(raw)
        params = delta.get("params", {}) if isinstance(delta, dict) else {}
        return dict(params.get(step_id, {}))

    def project_config(self) -> Any:
        return self.project.project_config(
            git_dirty=self.git_dirty,
            allow_dirty_reason=self.allow_dirty_reason,
            input_digests_now=self.input_digests_now,
            env_digests=self.env_digests,
            step_status=self.step_status(),
        )

    def gate_context(
        self, phase: str, action: Action, state: State, output: Any = None
    ) -> GateContext:
        return GateContext(
            phase=phase,  # type: ignore[arg-type]
            project=self.project_config(),
            objective=self.project.objective,
            design=self.project.design,
            state=state,
            action=action,
            history=state.history,
            output=output,
            policy=self.project.policy,
        )


def operator_env() -> dict[str, str | None]:
    return {
        "harness": os.environ.get("STRINGENCY_OPERATOR"),
        "version": os.environ.get("STRINGENCY_OPERATOR_VERSION"),
        "session_ref": os.environ.get("STRINGENCY_SESSION_REF"),
    }


def latest_run(store: Store) -> Any:
    """The latest analysis run (control runs are excluded)."""
    return store.one(
        "SELECT * FROM runs WHERE kind = 'run' ORDER BY started DESC, rowid DESC LIMIT 1"
    )


def require_confirmed(project: Project) -> None:
    """`run` refuses to open until the owner has accepted the echo-back (design 2.7)."""
    status = project.confirm_status()
    if status == "accepted":
        return
    hold = project.confirm_hold()
    assert hold is not None
    raise HeldError(
        f"held: hold {hold['hold_id']} (confirm); waits on owner {project.config.roles.owner}; "
        f"run `stringency review --hold {hold['hold_id']}` in {project.root}"
    )


def _context_for(project: Project, run_row: Any, *, executor_kind: str | None = None) -> RunContext:
    executor = project.executor(executor_kind)
    env_digests = {e: _digest_or_none(executor, e) for e in project.env_names()}
    return RunContext(
        project=project,
        run_id=run_row["run_id"],
        executor=executor,
        env_digests=env_digests,
        policy_digest=run_row["policy_digest"],
        input_digests_now=project.input_digests_now(),
        git_dirty=bool(run_row["git_dirty"]),
        allow_dirty_reason=run_row["allow_dirty_reason"],
        operator=operator_env(),
    )


def _digest_or_none(executor: Executor, env: str) -> str | None:
    try:
        return executor.env_digest(env)
    except ConfigError:
        return None


def open_or_resume(project: Project, *, allow_dirty: str | None = None) -> RunContext:
    """Resume the latest open run, or open a new one (design 2.6). Writes on open: runs,
    run_events, steps, step_events, policy_snapshots, predicate_results (run_open phase)."""
    require_confirmed(project)
    last = latest_run(project.store)
    if last is not None and last["status"] in OPEN_STATUSES:
        return _context_for(project, last)
    return open_run(project, allow_dirty=allow_dirty)


def open_run(
    project: Project,
    *,
    allow_dirty: str | None = None,
    parent_run_id: str | None = None,
    fork_at: str | None = None,
    delta: dict[str, Any] | None = None,
    kind: str = "run",
) -> RunContext:
    """Open a new run with every capture in design 9.1."""
    require_confirmed(project)
    store = project.store
    dirty = git.is_dirty(project.method_root)
    sha = git.head_sha(project.method_root)
    run_id = new_id()
    executor = project.executor()
    env_digests = {e: _digest_or_none(executor, e) for e in project.env_names()}
    policy_digest = project.policy_digest()
    rc = RunContext(
        project=project,
        run_id=run_id,
        executor=executor,
        env_digests=env_digests,
        policy_digest=policy_digest,
        input_digests_now=project.input_digests_now(),
        git_dirty=dirty,
        allow_dirty_reason=allow_dirty,
        operator=operator_env(),
    )
    # run-open gate: repro.dirty_tree, repro.input_digest_mismatch
    action = Action(
        action_id=run_id,
        run_id=run_id,
        step_id="run",
        attempt=0,
        operation="run_open",
        module="run",
        parameters={},
        param_source={},
        inputs={},
        input_digest="blake3:" + hashing.hash_json({}),
        params_hash="blake3:" + hashing.hash_json({}),
        proposed_by="pipeline",
    )
    ctx = rc.gate_context("run_open", action, project.initial_state(run_id, rc.input_objects()))
    result = evaluate(
        ctx, registry=registry, store=None, policy_digest=policy_digest, module=None, runner=None
    )
    if result.blocked:
        ids = [r.spec.id for r in result.blocked]
        if "repro.dirty_tree" in ids:
            raise DirtyTreeError(
                'dirty tree: the method repo has uncommitted changes; commit them, or pass --allow-dirty "<reason>"'
            )
        raise BlockedError("blocked at run open: " + "; ".join(r.line() for r in result.blocked))
    used = sorted(f"{k}={v or 'unpinned'}" for k, v in env_digests.items())
    store.record_policy_snapshot(
        policy_digest, project.policy.version, project.policy.raw, registry.refs()
    )
    with store.transaction():
        store.open_run(
            {
                "run_id": run_id,
                "project_id": project.config.project_id,
                "parent_run_id": parent_run_id,
                "fork_at_step": fork_at,
                "delta_json": delta,
                "git_sha": sha,
                "git_dirty": dirty,
                "allow_dirty_reason": allow_dirty,
                "host": socket.gethostname(),
                "user": os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown",
                "operator_harness": rc.operator.get("harness"),
                "operator_version": rc.operator.get("version"),
                "operator_session_ref": rc.operator.get("session_ref"),
                "status": "running",
                "env_digest": hashing.hash_text("\n".join(used)),
                "policy_version": project.policy.version,
                "policy_digest": policy_digest,
                "stringency_version": __version__,
                "kind": kind,
            }
        )
        store.run_event(
            run_id,
            "captures",
            {
                "inputs": rc.input_digests_now,
                "env_digests": env_digests,
                "executor": executor.kind,
                "method": {
                    "repo": project.config.method.repo,
                    "tag": project.config.method.tag,
                    "sha": sha,
                    "dirty": dirty,
                },
            },
        )
        for r in result.records:
            store.insert(
                "predicate_results",
                {
                    "run_id": run_id,
                    "action_id": run_id,
                    "phase": "run_open",
                    "predicate_id": r.spec.id,
                    "predicate_version": r.spec.version,
                    "fired": r.fired,
                    "default_disposition": str(r.default),
                    "effective_disposition": str(r.effective),
                    "reason": r.verdict.reason,
                    "evidence_json": r.verdict.evidence,
                    "severity": r.verdict.severity,
                    "policy_digest": policy_digest,
                    "ts": action.proposed_at,
                },
            )
        for step in project.pipeline.steps:
            module = project.modules.require(step.module)
            store.create_step(
                {
                    "run_id": run_id,
                    "step_id": step.id,
                    "module": module.manifest.name,
                    "module_version": module.manifest.version,
                    "operation": module.manifest.operation,
                }
            )
        initial = project.initial_state(run_id, rc.input_objects())
        store_snapshot(store, run_id, "run", "post", initial, "init", "0")
    return rc


def load_run(project: Project, run_id: str) -> RunContext:
    row = project.store.one("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    if row is None:
        raise ConfigError(f"no run {run_id}")
    return _context_for(project, row)


def close_run(rc: RunContext, status: str, reason: str | None = None) -> None:
    """Writes: run_events, runs.status and ended; runs/<id>/summary.md."""
    rc.store.set_run_status(rc.run_id, status, {"reason": reason}, ended=True)
    write_summary(rc)


def abandon(project: Project, run_id: str, reason: str) -> None:
    rc = load_run(project, run_id)
    if rc.run["status"] in CLOSED_STATUSES:
        raise RefusedError(f"run {run_id} is already {rc.run['status']}")
    close_run(rc, "abandoned", reason)


def write_summary(rc: RunContext) -> None:
    """runs/<run_id>/summary.md at run close (design 2.1)."""
    run = rc.run
    lines = [
        f"# run {rc.run_id}",
        "",
        f"status: {run['status']}",
        f"project: {rc.project.config.project_id}",
        f"pipeline: {rc.project.pipeline.name}@{rc.project.pipeline.version}",
        f"method: {run['git_sha']} ({'dirty' if run['git_dirty'] else 'clean'})",
        f"policy: {run['policy_version']} ({run['policy_digest'][:12]})",
        f"started: {run['started']}  ended: {run['ended']}",
        "",
        "## steps",
        "",
    ]
    for r in rc.store.all(
        "SELECT step_id, status, attempt FROM steps WHERE run_id = ? ORDER BY rowid", (rc.run_id,)
    ):
        lines.append(f"- {r['step_id']}: {r['status']} (attempt {r['attempt']})")
    d = rc.project.run_dir(rc.run_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "summary.md").write_text("\n".join(lines) + "\n")
