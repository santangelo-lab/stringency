"""`propose` for the operator runner (design 3.4 step 1): the ticket and the job specification."""

from __future__ import annotations

import shlex
from typing import Any

from stringency.executor.base import Executor
from stringency.steps import JOB_FILE, Proposal, exec_line, job_log_path


def job_spec(
    proposal: Proposal, env_digest: str | None, executor: Executor | None = None
) -> dict[str, Any]:
    """The ticket as the operator sees it. With an executor, `exec` is the exact line to run
    and `submit` the exact line to call afterwards, `--command` carrying `exec` verbatim."""
    plan, action = proposal.plan, proposal.action
    m = plan.module.manifest
    seed = action.parameters.get(m.seed_param) if m.stochastic and m.seed_param else None
    run_line = exec_line(executor, action, plan) if executor is not None else None
    log = job_log_path(plan)
    ev_cmds = [
        evidence_command(e.kind, plan.step_dir / e.path, executor, m.env) for e in m.evidence
    ]
    producible = [
        plan.step_dir / e.path
        for e, c in zip(m.evidence, ev_cmds, strict=True)
        if e.kind == "job_log" or c["command"] is not None
    ]
    submit = (
        f"stringency submit {action.ticket} "
        + " ".join(f"--outputs {k}={shlex.quote(str(plan.output_paths[k]))}" for k in m.outputs)
        + "".join(f" --evidence {shlex.quote(str(p))}" for p in producible)
    )
    if run_line is not None:
        submit += f" --command {shlex.quote(run_line)}"
    return {
        "schema": "stringency.job_spec/1",
        "ticket": action.ticket,
        "run_id": action.run_id,
        "step_id": action.step_id,
        "attempt": action.attempt,
        "module": plan.module.ref,
        "operation": m.operation,
        "kind": m.kind,
        "script": str(plan.module.entry_script) if plan.module.entry_script else None,
        "inputs": {
            k: {"path": str(v.path), "blake3": v.digest, "type": v.type}
            for k, v in plan.inputs.items()
        },
        "params": action.parameters,
        "param_source": action.param_source,
        "seed": seed,
        "env": {"name": m.env, "expected_digest": env_digest},
        "outputs": {
            k: {"type": v.type, "format": v.format, "suggested_path": str(plan.output_paths[k])}
            for k, v in m.outputs.items()
        },
        "evidence": [{"kind": e.kind, "path": e.path} for e in m.evidence],
        "evidence_commands": ev_cmds,
        "step_dir": str(plan.step_dir),
        "job_json": str(plan.step_dir / JOB_FILE),
        "log": str(log),
        "exec": run_line,
        "submit": submit,
    }


def evidence_command(
    kind: str, path: Any, executor: Executor | None, env_name: str
) -> dict[str, Any]:
    """How the operator produces one declared evidence file. `job_log` is the exec line's own
    output. `apptainer_inspect` is `inspect --json` of the image followed by its `sha256sum`,
    which is what lets `env_status` verify the reported container against the manifest; it is
    producible only when the executor knows the image. Other kinds come from the workflow
    engine itself."""
    entry: dict[str, Any] = {"kind": kind, "path": str(path), "command": None, "note": None}
    if kind == "job_log":
        entry["note"] = "written by the exec line"
        return entry
    if kind == "apptainer_inspect":
        image_for = getattr(executor, "image_for", None)
        image = image_for(env_name) if callable(image_for) else None
        if image is None:
            entry["note"] = (
                f"not producible: the {getattr(executor, 'kind', 'configured')} executor names no image"
            )
            return entry
        binary = getattr(executor, "binary", "apptainer")
        q = shlex.quote(str(image))
        entry["command"] = (
            f"{{ {shlex.quote(str(binary))} inspect --json {q}; sha256sum {q}; }} > {shlex.quote(str(path))}"
        )
        return entry
    entry["note"] = "produced by the workflow engine; copy it to this path"
    return entry


def render_job_spec(spec: dict[str, Any]) -> str:
    lines = [
        f"ticket {spec['ticket']}  step {spec['step_id']}  attempt {spec['attempt']}  module {spec['module']}",
        f"operation: {spec['operation']} ({spec['kind']})",
        f"script: {spec['script']}",
        "inputs:",
    ]
    for k, v in spec["inputs"].items():
        lines.append(f"  {k}: {v['path']}  blake3:{v['blake3'][:16]}  ({v['type']})")
    lines.append("params (admitted):")
    for k, v in spec["params"].items():
        lines.append(f"  {k} = {v!r}  [{spec['param_source'].get(k, 'default')}]")
    if spec["seed"] is not None:
        lines.append(f"seed: {spec['seed']}")
    lines.append(
        f"env: {spec['env']['name']}  expected digest: {spec['env']['expected_digest'] or 'unpinned'}"
    )
    lines.append("outputs to produce:")
    for k, v in spec["outputs"].items():
        lines.append(f"  {k}: {v['type']}/{v['format']}  suggested {v['suggested_path']}")
    if spec["evidence"]:
        lines.append(
            "evidence expected: "
            + ", ".join(f"{e['kind']} ({e['path']})" for e in spec["evidence"])
        )
    lines.append(f"job.json written: {spec['job_json']}")
    if spec.get("exec"):
        lines.append(f"run: {spec['exec']}")
    for e in spec.get("evidence_commands", []):
        if e["command"]:
            lines.append(f"evidence {e['kind']}: {e['command']}")
        elif e["kind"] != "job_log":
            lines.append(f"evidence {e['kind']}: {e['note']}")
    lines.append(f"then: {spec['submit']}")
    return "\n".join(lines)
