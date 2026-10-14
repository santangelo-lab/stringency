"""`fork` (design 2.6): a child run that inherits inputs and every completed step before
`--at`, applies declared parameter changes, and leaves the parent untouched. A step the parent
skipped before `--at` is inherited as skipped (L13). A step the child re-runs starts from the
parameters its nearest ancestor admitted for it (`inherited_params`), `--set` overriding only
what it names (L27: the Lyons v2 spleen fork of 2026-10-12 ran at the pipeline defaults).

Reads: runs, steps, artifacts, state_snapshots, actions. Writes: runs, steps (inherited ones
as completed), artifacts (rows pointing at the parent's files), state_snapshots (history
entries marked inherited), run_events (the `fork` event carries what each re-run step will run
with, as `params`).
"""

from __future__ import annotations

import json
from typing import Any

from stringency.actions import build_action, coerce_value
from stringency.db.store import Store
from stringency.exit_codes import ConfigError
from stringency.project import Project
from stringency.runs import RunContext, load_run, open_run
from stringency.state import State, StepRecord, store_snapshot

ParamTable = dict[str, dict[str, dict[str, Any]]]  # step -> param -> {value, source}


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


def ancestor_params(store: Store, run_id: str, step_id: str) -> dict[str, tuple[Any, str]] | None:
    """What the nearest run in the chain starting at `run_id` (itself, then its parent, and so
    on) admitted for `step_id`, as name -> (value, label for the child): `default` where that
    run took the default, else `inherited`. None when no run in the chain completed the step.
    Reads: runs, steps, actions."""
    rid: str | None = run_id
    while rid:
        status = store.scalar(
            "SELECT status FROM steps WHERE run_id = ? AND step_id = ?", (rid, step_id)
        )
        if status == "completed":
            row = store.one(
                "SELECT params_json, param_source_json FROM actions WHERE run_id = ? AND step_id = ? "
                "ORDER BY attempt DESC, rowid DESC LIMIT 1",
                (rid, step_id),
            )
            if row is not None:  # a step inherited as completed has no action; walk on
                params = json.loads(row["params_json"])
                src = json.loads(row["param_source_json"] or "{}")
                return {
                    k: (v, "default" if src.get(k, "default") == "default" else "inherited")
                    for k, v in params.items()
                }
        rid = store.scalar("SELECT parent_run_id FROM runs WHERE run_id = ?", (rid,))
    return None


def inherited_for(rc: RunContext, step_id: str) -> dict[str, tuple[Any, str]] | None:
    """The parameters a forked run's step starts from (design 2.6), or None when the run is not a
    fork or no ancestor completed the step. Reads: runs, steps, actions."""
    parent = rc.run["parent_run_id"]
    if not parent:
        return None
    return ancestor_params(rc.store, parent, step_id)


def resolved_params(
    project: Project, from_run: str, at: str, delta: dict[str, dict[str, Any]]
) -> ParamTable:
    """What every step from `at` on will run with in a fork of `from_run`: the same merge
    `build_action` makes when the step is proposed (the ancestor's admitted values, the delta over
    them, defaults for the rest), without writing anything. Reads: runs, steps, actions."""
    order = project.pipeline.order()
    out: ParamTable = {}
    for sid in order[order.index(at) :]:
        step = project.pipeline.step(sid)
        module = project.modules.require(step.module)
        action = build_action(
            run_id="preview",
            step=step,
            module=module,
            attempt=0,
            input_digests={},
            proposed=delta.get(sid) or None,
            source_label="fork",
            inherited=ancestor_params(project.store, from_run, sid),
        )
        out[sid] = {
            k: {"value": v, "source": action.param_source.get(k, "default")}
            for k, v in action.parameters.items()
        }
    return out


def render_params(table: ParamTable) -> str:
    lines = []
    for sid, params in table.items():
        if not params:
            lines.append(f"  {sid}: no parameters")
        for k, d in params.items():
            lines.append(f"  {sid}.{k} = {d['value']!r}  [{d['source']}]")
    return "\n".join(lines)


def check(project: Project, *, from_run: str, at: str, sets: list[str]) -> ParamTable:
    """`fork --check`: the validation `fork` does and the parameter table it would record, with
    no run opened. Reads only."""
    _, _, delta = _prepare(project, from_run, at, sets)
    return resolved_params(project, from_run, at, delta)


def _prepare(
    project: Project, from_run: str, at: str, sets: list[str]
) -> tuple[RunContext, list[str], dict[str, dict[str, Any]]]:
    parent = load_run(project, from_run)
    order = project.pipeline.order()
    if at not in order:
        raise ConfigError(f"no step {at} in pipeline {project.pipeline.name}")
    delta = parse_delta(sets, order, at)
    statuses = parent.step_status()
    for s in order[: order.index(at)]:
        if statuses.get(s) not in ("completed", "skipped"):
            raise ConfigError(
                f"cannot fork at {at}: step {s} is {statuses.get(s)} in run {from_run}, not completed"
            )
    return parent, order, delta


def fork(project: Project, *, from_run: str, at: str, sets: list[str], reason: str) -> RunContext:
    parent, order, delta = _prepare(project, from_run, at, sets)
    statuses = parent.step_status()
    inherit = [s for s in order[: order.index(at)]]
    params = resolved_params(project, from_run, at, delta)
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
            if row["status"] == "skipped":
                # the parent's evaluation, so the child names the same reason (L13)
                ev = store.one(
                    "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? "
                    "AND event='status:skipped' ORDER BY seq DESC LIMIT 1",
                    (from_run, sid),
                )
                skipped = json.loads(ev["payload_json"]) if ev else {}
                store.set_step_status(
                    child.run_id,
                    sid,
                    "skipped",
                    {
                        **{k: skipped[k] for k in ("when", "actual", "reason") if k in skipped},
                        "inherited_from": from_run,
                    },
                    ended=True,
                )
                continue
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
        ran = [s for s in inherit if statuses.get(s) == "completed"]  # a skipped step has no state
        parent_state = _state_after(parent, ran[-1]) if ran else None
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
            {
                "from": from_run,
                "at": at,
                "inherited": inherit,
                "delta": delta,
                "params": params,
                "reason": reason,
            },
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
