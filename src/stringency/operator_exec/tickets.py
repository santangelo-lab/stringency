"""`propose` for the operator runner (design 3.4 step 1): the ticket and the job specification."""

from __future__ import annotations

from typing import Any

from stringency.steps import Proposal


def job_spec(proposal: Proposal, env_digest: str | None) -> dict[str, Any]:
    plan, action = proposal.plan, proposal.action
    m = plan.module.manifest
    seed = action.parameters.get(m.seed_param) if m.stochastic and m.seed_param else None
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
        "step_dir": str(plan.step_dir),
        "submit": "stringency submit "
        + str(action.ticket)
        + " "
        + " ".join(f"--outputs {k}=<path>" for k in m.outputs)
        + "".join(f" --evidence <{e.path}>" for e in m.evidence),
    }


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
    lines.append(f"then: {spec['submit']}")
    return "\n".join(lines)
