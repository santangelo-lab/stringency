"""`fork` (design 2.6): a child run that inherits inputs and every completed step before
`--at`, applies declared parameter changes, and leaves the parent untouched.

Reads: runs, steps, artifacts, state_snapshots, actions. Writes: runs, steps (inherited ones
as completed), artifacts (rows pointing at the parent's files), state_snapshots (history
entries marked inherited), run_events.
"""

from __future__ import annotations

import json
from typing import Any

from stringency.actions import coerce_value
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.runs import RunContext, load_run, open_run
from stringency.state import State, StepRecord, store_snapshot


def parse_delta(sets: list[str], pipeline_order: list[str], at: str) -> dict[str, dict[str, Any]]:
    """`--set <step>.<param>=<value>` entries; every step named must be at or after `--at`."""
    out: dict[str, dict[str, Any]] = {}
    for s in sets:
        if "=" not in s or "." not in s.split("=", 1)[0]:
            raise ConfigError(f"--set expects <step>.<param>=<value>, got {s!r}")
        key, _, value = s.partition("=")
        step, _, param = key.partition(".")
        if step not in pipeline_order:
            raise ConfigError(f"--set names unknown step {step}")
        if pipeline_order.index(step) < pipeline_order.index(at):
            raise ConfigError(
                f"--set {key}: step {step} is before --at {at}; forks change steps from --at onward"
            )
        out.setdefault(step, {})[param] = coerce_value(value)
    return out


def fork(project: Project, *, from_run: str, at: str, sets: list[str], reason: str) -> RunContext:
    parent = load_run(project, from_run)
    order = project.pipeline.order()
    if at not in order:
        raise ConfigError(f"no step {at} in pipeline {project.pipeline.name}")
    delta = parse_delta(sets, order, at)
    statuses = parent.step_status()
    inherit = [s for s in order[: order.index(at)]]
    for s in inherit:
        if statuses.get(s) != "completed":
            raise ConfigError(
                f"cannot fork at {at}: step {s} is {statuses.get(s)} in run {from_run}, not completed"
            )
    child = open_run(
        project,
        parent_run_id=from_run,
        fork_at=at,
        delta={"params": delta, "reason": reason, "from": from_run, "at": at},
        allow_dirty=parent.run["allow_dirty_reason"],
    )
    store = project.store
    with store.transaction():
        for sid in inherit:
            row = store.one("SELECT * FROM steps WHERE run_id=? AND step_id=?", (from_run, sid))
            assert row is not None
            store.set_step_status(
                child.run_id,
                sid,
                "completed",
                {"inherited_from": from_run, "attempt": row["attempt"]},
                attempt=row["attempt"],
                ended=True,
            )
            for a in store.all(
                "SELECT * FROM artifacts WHERE run_id=? AND step_id=? AND status='produced'",
                (from_run, sid),
            ):
                store.add_artifact(
                    {
                        "run_id": child.run_id,
                        "step_id": sid,
                        "action_id": a["action_id"],
                        "path": a["path"],
                        "hash": a["hash"],
                        "size": a["size"],
                        "kind": a["kind"],
                        "is_final": False,
                        "provisional": False,
                        "sidecar_path": a["sidecar_path"],
                        "name": a["name"],
                    }
                )
        # the inherited state: the parent's snapshot after the last inherited step, history marked inherited
        parent_state = _state_after(parent, inherit[-1]) if inherit else None
        if parent_state is not None:
            inherited_state = State(
                run_id=child.run_id,
                after_step=parent_state.after_step,
                objects=parent_state.objects,
                design=parent_state.design,
                objective=parent_state.objective,
                history=tuple(
                    StepRecord(h.step, h.operation, h.params, h.output_digests, inherited=True)
                    for h in parent_state.history
                ),
                env=parent_state.env,
                mode=parent_state.mode,
                profile=parent_state.profile,
            )
            store_snapshot(store, child.run_id, "run", "post", inherited_state, "inherited", "0")
        store.run_event(
            child.run_id,
            "fork",
            {"from": from_run, "at": at, "inherited": inherit, "delta": delta, "reason": reason},
        )
    return child


def _state_after(rc: RunContext, step_id: str) -> State | None:
    from stringency.state import latest_state

    return latest_state(rc.store, rc.run_id, step_id)


def describe_delta(run_row: Any) -> str:
    raw = run_row["delta_json"]
    if not raw:
        return ""
    d = json.loads(raw)
    parts = [f"{s}.{k}={v}" for s, ps in d.get("params", {}).items() for k, v in ps.items()]
    return f"fork of {d.get('from')} at {d.get('at')}: {', '.join(parts) or 'no parameter changes'}; {d.get('reason')}"
