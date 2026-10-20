"""Runs (design 2.6, 9.1): open, resume, close, and the run-level captures.

`RunContext` is what every step operation works against: the project, the store, the run
row, the executor, the environment digests resolved at open, and the policy digest.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import __version__, git, hashing
from stringency.actions import Action
from stringency.controls import current_for
from stringency.db.store import Store
from stringency.executor.base import Executor
from stringency.exit_codes import BlockedError, ConfigError, DirtyTreeError, HeldError, RefusedError
from stringency.gate import evaluate
from stringency.ids import new_id
from stringency.machine import all_step_status, derive_run_status
from stringency.modules import Module, ModuleManifest
from stringency.operator_id import operator_env
from stringency.pipelines import Pipeline, StepDecl
from stringency.plugins import installed_plugin_versions
from stringency.predicates import registry
from stringency.predicates.context import GateContext
from stringency.project import Project
from stringency.state import ObjectState, State, latest_state, store_snapshot
from stringency.versions import check_requires

OPEN_STATUSES = ("running", "held", "blocked", "failed")
CLOSED_STATUSES = ("completed", "abandoned")


@dataclass
class RunContext:
    project: Project
    run_id: str
    executor: Executor
    env_digests: dict[str, str | None]
    policy_digest: str
    git_dirty: bool = False
    allow_dirty_reason: str | None = None
    operator: dict[str, str | None] = field(default_factory=dict)
    script_blobs: dict[str, str] = field(default_factory=dict)  # module ref -> hash at open
    # plugins whose installed version differs from the one recorded at init (L29); set at open
    plugin_changes: list[dict[str, Any]] = field(default_factory=list)
    # hashed on first read, not at load: a read-only view (a hold page, `review --hold`) never
    # reads it, and hashing every declared input took 55 s on a large project (backlog L23)
    _input_digests: dict[str, str] | None = field(default=None, repr=False)
    # -- the run's topology ----------------------------------------------------------

    @property
    def open_ended(self) -> bool:
        return self.project.open_ended

    def on_demand(self) -> list[dict[str, Any]]:
        """The run's on-demand steps in creation order (open mode): each `{step_id, kind:
        tool | exec, decl, manifest?, question_id}` from the `created` step event whose payload
        carries `on_demand`. Reads: step_events, every time: a context that outlives a `call`
        made through another must see the step it added."""
        out: list[dict[str, Any]] = []
        for r in self.store.all(
            "SELECT step_id, payload_json FROM step_events WHERE run_id = ? AND "
            "event = 'created' ORDER BY ts, rowid",
            (self.run_id,),
        ):
            payload = json.loads(r["payload_json"] or "{}")
            od = payload.get("on_demand")
            if isinstance(od, dict):
                out.append({"step_id": r["step_id"], **od})
        return out

    @property
    def pipeline(self) -> Pipeline:
        """The topology this run is gated against: the project's declared steps, then the
        on-demand steps so far in creation order (open_mode_plan.md 2.2). Every predicate, the
        planner and the run loop read this, never `project.pipeline`, so an open run's tool and
        exec steps are inside the bound topology the moment they are proposed."""
        od = self.on_demand()
        if not od:
            return self.project.pipeline
        steps = [*self.project.pipeline.steps, *(StepDecl.model_validate(x["decl"]) for x in od)]
        return self.project.pipeline.model_copy(update={"steps": steps})

    def order(self) -> list[str]:
        return self.pipeline.order()

    def decl(self, step_id: str) -> StepDecl:
        return self.pipeline.step(step_id)

    def on_demand_entry(self, step_id: str) -> dict[str, Any] | None:
        for x in self.on_demand():
            if x["step_id"] == step_id:
                return x
        return None

    def module_for(self, step_id: str) -> Module:
        """The module a step runs: from the method index for a declared step or a tool; for an
        exec step the manifest recorded at proposal over the step directory (`script.<ext>`
        is its entry)."""
        entry = self.on_demand_entry(step_id)
        if entry is not None and entry.get("kind") == "exec" and entry.get("manifest"):
            manifest = ModuleManifest.model_validate(entry["manifest"])
            return Module(self.project.step_dir(self.run_id, step_id), manifest)
        return self.project.modules.require(self.decl(step_id).module)

    def next_step_id(self, name: str) -> str:
        """`<nn>_<name>`, numbered after every step of the run so far."""
        return f"{len(self.pipeline.steps) + 1:02d}_{name}"

    def create_on_demand_step(
        self,
        decl: StepDecl,
        kind: str,
        module: Module,
        *,
        manifest: dict[str, Any] | None = None,
        question_id: str | None = None,
    ) -> None:
        """Add a step to an open run (open_mode_plan.md 2.2). Writes: steps (pending) and the
        `created` step event, whose payload carries `on_demand: {kind, decl, manifest?,
        question_id}` (no new column; the `captures` precedent)."""
        if not self.open_ended:
            raise RefusedError("steps are added on demand only in an open project")
        self.store.create_step(
            {
                "run_id": self.run_id,
                "step_id": decl.id,
                "module": module.manifest.name,
                "module_version": module.manifest.version,
                "operation": module.manifest.operation,
            },
            extra={
                "on_demand": {
                    "kind": kind,
                    "decl": decl.model_dump(mode="json", exclude_none=True),
                    "manifest": manifest,
                    "question_id": question_id,
                }
            },
        )

    def artifact_kinds(self) -> dict[str, str]:
        """The recorded kind of every declared input and produced artifact of the run, by bare
        digest (`topo.input_type_mismatch`). Reads: artifacts."""
        out = {i.blake3: i.type for i in self.project.inputs.items}
        for r in self.store.all(
            "SELECT hash, kind FROM artifacts WHERE run_id = ? AND status = 'produced'",
            (self.run_id,),
        ):
            out[str(r["hash"])] = str(r["kind"])
        return out

    @property
    def input_digests_now(self) -> dict[str, str]:
        """The declared inputs' hashes now, computed once per context on first read."""
        if self._input_digests is None:
            self._input_digests = self.project.input_digests_now()
        return self._input_digests

    @property
    def store(self) -> Store:
        return self.project.store

    @property
    def run(self) -> Any:
        return self.store.one("SELECT * FROM runs WHERE run_id = ?", (self.run_id,))

    def step_status(self) -> dict[str, str]:
        return all_step_status(self.store, self.run_id)

    def status(self) -> str:
        return derive_run_status(self.step_status(), self.order(), open_ended=self.open_ended)

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

    def delta_for_all(self) -> dict[str, dict[str, Any]]:
        """Every parameter change a fork declared, by step (design 2.6), or {}."""
        import json

        raw = self.run["delta_json"]
        if not raw:
            return {}
        delta = json.loads(raw)
        params = delta.get("params", {}) if isinstance(delta, dict) else {}
        return {k: dict(v) for k, v in params.items()}

    def delta_for(self, step_id: str) -> dict[str, Any]:
        """Parameter changes a fork declared for `step_id` (design 2.6), or {}."""
        return self.delta_for_all().get(step_id, {})

    def project_config(self) -> Any:
        """The static facts predicates read (design 6.1): the run's topology (declared and
        on-demand steps), every manifest including an exec step's synthetic one, and the
        recorded kinds of the run's inputs and artifacts."""
        modules = self.project.manifests()
        for x in self.on_demand():
            if x.get("manifest"):
                m = ModuleManifest.model_validate(x["manifest"])
                modules[m.ref] = m
        return self.project.project_config(
            pipeline=self.pipeline,
            modules=modules,
            git_dirty=self.git_dirty,
            allow_dirty_reason=self.allow_dirty_reason,
            input_digests_now=self.input_digests_now,
            env_digests=self.env_digests,
            step_status=self.step_status(),
            script_blobs=self.script_blobs,
            artifact_kinds=self.artifact_kinds(),
            controls_current=self.controls_current(),
        )

    def controls_current(self) -> dict[str, dict[str, Any]]:
        """Per tool of an open project, whether its last passing control still speaks for it
        under the environment digest of this run (`controls.current_for`). Reads: controls_runs."""
        if not self.open_ended:
            return {}
        return {
            m.ref: current_for(self.store, m, self.env_digests.get(m.manifest.env))
            for m in self.project.tools()
        }

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


def module_script_blobs(project: Project) -> dict[str, str]:
    """blake3 of every module entry script in the bound pipeline as it is on disk now.
    Captured at run open (design 9.1); `exec.script_drift` compares against it later."""
    from stringency.steps import script_blob

    out: dict[str, str] = {}
    modules = (
        project.tools()
        if project.open_ended
        else [
            project.modules.require(project.pipeline.step(sid).module)
            for sid in project.pipeline.order()
        ]
    )
    for module in modules:
        blob = script_blob(module)
        if blob is not None:
            out[module.ref] = blob
    return out


def captured_script_blobs(store: Store, run_id: str) -> dict[str, str]:
    """Reads: run_events (`captures`) for the run's script blobs; {} for runs opened before
    the capture existed, which disables the drift check for them."""
    import json

    row = store.one(
        "SELECT payload_json FROM run_events WHERE run_id = ? AND event = 'captures' "
        "ORDER BY seq LIMIT 1",
        (run_id,),
    )
    if row is None:
        return {}
    payload = json.loads(row["payload_json"] or "{}")
    blobs = payload.get("script_blobs", {})
    return {str(k): str(v) for k, v in blobs.items()} if isinstance(blobs, dict) else {}


def _context_for(project: Project, run_row: Any, *, executor_kind: str | None = None) -> RunContext:
    executor = project.executor(executor_kind)
    env_digests = {e: _digest_or_none(executor, e) for e in project.env_names()}
    return RunContext(
        project=project,
        run_id=run_row["run_id"],
        executor=executor,
        env_digests=env_digests,
        policy_digest=run_row["policy_digest"],
        git_dirty=bool(run_row["git_dirty"]),
        allow_dirty_reason=run_row["allow_dirty_reason"],
        operator=operator_env(),
        script_blobs=captured_script_blobs(project.store, run_row["run_id"]),
    )


def upstream_lineage(project: Project) -> list[dict[str, Any]]:
    """For an open project, the upstream runs its inputs came from: each run's ancestor chain
    (`parent_run_id`), its status and its deliveries' timestamps, read from the upstream
    project's `prov/run.db` read-only (open_mode_plan.md 2.7, `captures.upstream_lineage`).
    An unreadable upstream is reported as such, not raised."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in project.inputs.items:
        d = item.derived_from
        if d is None or not d.project:
            continue
        key = (d.project, d.run_id)
        if key in seen:
            continue
        seen.add(key)
        entry: dict[str, Any] = {"input": item.name, "project": d.project, "run_id": d.run_id}
        db = Path(d.project) / "prov" / "run.db"
        try:
            with Store.open(db, create=False) as up:
                chain: list[dict[str, Any]] = []
                cur: str | None = d.run_id
                while cur and len(chain) < 50:
                    row = up.one(
                        "SELECT run_id, parent_run_id, status, started, ended FROM runs WHERE run_id=?",
                        (cur,),
                    )
                    if row is None:
                        break
                    chain.append(
                        {
                            k: row[k]
                            for k in ("run_id", "parent_run_id", "status", "started", "ended")
                        }
                    )
                    cur = row["parent_run_id"]
                entry["chain"] = chain
                entry["deliveries"] = [
                    r["ts"]
                    for r in up.all(
                        "SELECT ts FROM deliveries WHERE run_id=? ORDER BY ts", (d.run_id,)
                    )
                ]
                entry["upstream_pipeline"] = up.scalar("SELECT pipeline_name FROM projects LIMIT 1")
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}: {e}"
        out.append(entry)
    return out


def captured_upstream_lineage(store: Store, run_id: str) -> list[dict[str, Any]]:
    row = store.one(
        "SELECT payload_json FROM run_events WHERE run_id = ? AND event = 'captures' ORDER BY seq LIMIT 1",
        (run_id,),
    )
    if row is None:
        return []
    payload = json.loads(row["payload_json"] or "{}")
    ul = payload.get("upstream_lineage")
    return list(ul) if isinstance(ul, list) else []


def captured_plugins(store: Store, run_id: str) -> dict[str, str]:
    """The plugins installed when the run opened, from its `captures` event (backlog L29); {}
    for a run opened by an engine before 0.2.19. Reads: run_events."""
    row = store.one(
        "SELECT payload_json FROM run_events WHERE run_id = ? AND event = 'captures' "
        "ORDER BY seq DESC LIMIT 1",
        (run_id,),
    )
    if row is None:
        return {}
    payload = json.loads(row["payload_json"] or "{}")
    plugins = payload.get("plugins")
    return {str(k): str(v) for k, v in plugins.items()} if isinstance(plugins, dict) else {}


def _digest_or_none(executor: Executor, env: str) -> str | None:
    try:
        return executor.env_digest(env)
    except ConfigError:
        return None


def open_or_resume(
    project: Project, *, allow_dirty: str | None = None, new: bool = False
) -> RunContext:
    """Resume the latest open run; open the first run; refuse (exit 16) when the latest run is
    closed unless `new` is set (design 2.6, improvement B3). Writes on open: runs, run_events,
    steps, step_events, policy_snapshots, predicate_results (run_open phase)."""
    require_confirmed(project)
    last = latest_run(project.store)
    if last is not None and last["status"] in OPEN_STATUSES:
        if new:
            raise RefusedError(
                f"run {last['run_id']} is {last['status']}; finish or abandon it before `run --new`"
            )
        return _context_for(project, last)
    if last is not None and not new:
        raise RefusedError(
            f"run {last['run_id']} is {last['status']}; `stringency run --new` opens a new run, "
            f"`stringency deliver` harvests a completed one"
        )
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
    """Open a new run with every capture in design 9.1. Refuses (exit 15) when the installed
    engine or plugins no longer satisfy the method's `requires` (backlog L28)."""
    require_confirmed(project)
    installed = installed_plugin_versions()
    if project.policy.requires is not None:
        problems = check_requires(project.policy.requires, __version__, installed)
        if problems:
            raise ConfigError(
                "the method's policy requires: "
                + "; ".join(problems)
                + "; this install cannot run it"
            )
    plugin_changes = [
        {"plugin": name, "at_init": version, "now": installed.get(name)}
        for name, version in project.config.plugins.items()
        if installed.get(name) != version
    ]
    store = project.store
    dirty = git.is_dirty(project.method_root)
    sha = git.head_sha(project.method_root)
    run_id = new_id()
    executor = project.executor()
    env_digests = {e: _digest_or_none(executor, e) for e in project.env_names()}
    policy_digest = project.policy_digest()
    script_blobs = module_script_blobs(project)
    rc = RunContext(
        project=project,
        run_id=run_id,
        executor=executor,
        env_digests=env_digests,
        policy_digest=policy_digest,
        git_dirty=dirty,
        allow_dirty_reason=allow_dirty,
        operator=operator_env(),
        script_blobs=script_blobs,
        plugin_changes=plugin_changes,
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
                "derived_from": [
                    {"input": i.name, **i.derived_from.model_dump()}
                    for i in project.inputs.items
                    if i.derived_from is not None
                ],
                "env_digests": env_digests,
                "script_blobs": script_blobs,
                "executor": executor.kind,
                "plugins": installed,
                "plugin_changes": plugin_changes,
                "tools": [m.ref for m in project.tools()] if project.open_ended else [],
                "upstream_lineage": upstream_lineage(project) if project.open_ended else [],
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
    """Close the run and every open step and hold with it (design 7.1, 2026-09-23): open steps
    become `abandoned`, open holds are withdrawn (`resolved_via: withdrawn`, no review). Writes:
    steps, step_events, holds, run_events, runs."""
    from stringency.machine import OPEN_STEP, StepStatus, step_status, transition

    rc = load_run(project, run_id)
    if rc.run["status"] in CLOSED_STATUSES:
        raise RefusedError(f"run {run_id} is already {rc.run['status']}")
    store = rc.store
    for sid in rc.order():
        st = step_status(store, run_id, sid)
        if st in OPEN_STEP:
            transition(store, run_id, sid, StepStatus.ABANDONED, payload={"reason": reason})
    open_ids = [
        r["hold_id"]
        for r in store.all(
            "SELECT hold_id FROM holds WHERE run_id = ? AND resolved_by_review IS NULL "
            "AND resolved_via IS NULL",
            (run_id,),
        )
    ]
    if open_ids:
        store.withdraw_holds(open_ids, f"run abandoned: {reason}")
    close_run(rc, "abandoned", reason)


def write_summary(rc: RunContext) -> None:
    """runs/<run_id>/summary.md at run close (design 2.1)."""
    run = rc.run
    lines = [
        f"# run {rc.run_id}",
        "",
        f"status: {run['status']}",
        f"project: {rc.project.config.project_id}",
        f"pipeline: {rc.pipeline.name}@{rc.pipeline.version}",
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
