"""Judgment module execution (design 3.5).

1. Inputs resolved, Action constructed, pre-gate (done by `steps.propose`).
2. `pre.*` runs engine-side if present and produces evidence tables.
3. Prompt assembly from declared variables only; rendered prompt stored content-addressed.
4. The harness answers `replicates` times: direct adapters in-process; the dispatch adapter
   writes request files and the step stops as `dispatching` (exit 20) until responses exist.
5. `post.*` if present.  6. Consensus and item holds.  7. Post-gate.  8. Settle.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stringency import git, hashing
from stringency.artifacts import record_output, step_outputs
from stringency.db.store import Store
from stringency.executor.base import Job
from stringency.executor.local import interpreter_for
from stringency.exit_codes import ConfigError, RefusedError
from stringency.gate import evaluate
from stringency.harness.api import ApiHarness
from stringency.harness.base import Harness, Request, Sampling
from stringency.harness.mock import MockHarness, fixture_path
from stringency.harness.subagent import SubagentHarness, request_path, write_requests
from stringency.machine import StepStatus, step_status, transition
from stringency.predicates import registry
from stringency.predicates.context import EvidenceTable, OutputBundle, OutputInfo
from stringency.prompting import (
    DISPATCH_SUFFIX,
    evidence_suffix,
    render,
    store_prompt,
    table_to_tsv,
)
from stringency.repeat import (
    Replicate,
    collect_dispatch,
    judgments_jsonl,
    record_invocations,
    run_direct,
    wrap_schema,
)
from stringency.runs import RunContext
from stringency.state import latest_state
from stringency.steps import (
    ExecInfo,
    Proposal,
    StepOutcome,
    StepPlan,
    action_from_row,
    finish,
    plan_step,
    settle_post,
    validate_output,
)
from stringency.tables import load_table


def harness_for(rc: RunContext, model: str | None = None) -> Harness:
    kind = rc.project.config.judgment_harness
    if kind == "mock":
        return MockHarness(fixture_path(rc.project.root))
    if kind == "subagent":
        return SubagentHarness()
    if kind == "api":
        return ApiHarness(model)
    raise ConfigError(f"judgment harness {kind} is deferred (design 17)")


@dataclass
class Evidence:
    tables: dict[str, EvidenceTable]
    texts: dict[str, str]  # table name -> TSV text as shown
    items: list[str]
    context: dict[str, Any]
    digests: dict[str, str]


def prepare_evidence(rc: RunContext, plan: StepPlan) -> Evidence:
    """Evidence tables from the declared `judgment.evidence` inputs, after running `pre.*`
    engine-side when the module has one (design 3.5 step 2)."""
    m = plan.module.manifest
    assert m.judgment is not None
    paths: dict[str, Path] = {k: v.path for k, v in plan.inputs.items() if not v.many}
    script = plan.module.entry_script
    if script is not None:
        ev_dir = plan.step_dir / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        job = Job(
            command=interpreter_for(script),
            env_name=m.env,
            cwd=plan.step_dir,
            stdin_json={
                "inputs": {k: str(v) for k, v in paths.items()},
                "params": {},
                "evidence_dir": str(ev_dir),
                "outputs": {n: str(ev_dir / f"{n}.tsv") for n in m.judgment.evidence},
                "design": plan.design,
                "objective": plan.objective,
            },
            stdout_path=plan.step_dir / "pre.stdout",
            stderr_path=plan.step_dir / "pre.stderr",
        )
        res = rc.executor.run(job)
        if res.exit_code != 0:
            raise ConfigError(
                f"judgment pre-script failed with exit {res.exit_code}: {res.stderr()[-400:]}"
            )
        for n in m.judgment.evidence:
            cand = ev_dir / f"{n}.tsv"
            if cand.exists():
                paths[n] = cand
    tables: dict[str, EvidenceTable] = {}
    texts: dict[str, str] = {}
    digests: dict[str, str] = {}
    context: dict[str, Any] = {}
    for n in m.judgment.evidence:
        p = paths.get(n)
        if p is None:
            raise ConfigError(f"evidence {n} is neither an input nor produced by pre.*")
        spec = m.inputs.get(n)
        if spec is not None and spec.type == "json":
            context[n] = json.loads(p.read_text())
        else:
            # the items table is keyed by item_key; any other evidence table (a guide, a reference
            # summary) by its first column, which need not be the item key
            tables[n] = load_table(
                p, n, m.judgment.item_key if n == m.judgment.items_from else None
            )
            texts[n] = p.read_text()
        digests[n] = hashing.prefixed(hashing.hash_file(p))
    items_table = tables.get(m.judgment.items_from)
    if items_table is None:
        raise ConfigError(f"items_from {m.judgment.items_from} is not a table")
    return Evidence(tables, texts, list(items_table.rows), context, digests)


def prompt_values(rc: RunContext, plan: StepPlan, ev: Evidence) -> dict[str, Any]:
    m = plan.module.manifest
    assert m.judgment is not None and m.prompt is not None
    vocab = list(rc.project.plugin.vocabulary(m.vocabulary) or ()) if m.vocabulary else []
    main = ev.tables[m.judgment.items_from]
    available: dict[str, Any] = {
        "evidence_table": table_to_tsv(list(main.columns), list(main.rows.values())),
        "evidence_tables": {
            k: table_to_tsv(list(t.columns), list(t.rows.values())) for k, t in ev.tables.items()
        },
        "vocabulary": vocab,
        "items": ev.items,
        "context": ev.context,
        "objective": rc.project.objective.model_dump(),
        "design": rc.project.design.model_dump(),
    }
    return {k: available[k] for k in m.prompt.vars if k in available}


def build_requests(
    action_id: str,
    prompt: str,
    schema: dict[str, Any],
    ev: Evidence,
    plan: StepPlan,
    template_ref: str,
) -> list[Request]:
    m = plan.module.manifest
    assert m.judgment is not None
    evidence = {n: {r: dict(v) for r, v in t.rows.items()} for n, t in ev.tables.items()}
    reqs: list[Request] = []
    n = 0
    for rep in range(1, m.judgment.replicates + 1):
        if m.judgment.batching == "per_item":
            for idx, _ in enumerate(ev.items):
                n += 1
                reqs.append(
                    Request(
                        n,
                        f"{action_id}-{n}",
                        prompt,
                        schema,
                        tuple(ev.items),
                        plan.module.ref,
                        template_ref,
                        evidence,
                        idx,
                    )
                )
        else:
            reqs.append(
                Request(
                    rep,
                    f"{action_id}-{rep}",
                    prompt,
                    schema,
                    tuple(ev.items),
                    plan.module.ref,
                    template_ref,
                    evidence,
                )
            )
    return reqs


def execute_judgment(rc: RunContext, proposal: Proposal) -> StepOutcome:
    """Run or resume a judgment step (design 3.5). Writes: messages, invocations, judgments,
    consensus, holds, artifacts, executions, state_snapshots, predicate_results, steps."""
    plan, action = proposal.plan, proposal.action
    m = plan.module.manifest
    if m.judgment is None or m.prompt is None:
        raise ConfigError(f"module {plan.module.ref} is not a judgment module")
    store = rc.store
    status = step_status(store, rc.run_id, action.step_id)
    if status not in (StepStatus.ADMISSIBLE, StepStatus.DISPATCHING):
        raise RefusedError(
            f"step {action.step_id} is {status}; a judgment step runs from admissible or dispatching"
        )
    plan.step_dir.mkdir(parents=True, exist_ok=True)

    ev = prepare_evidence(rc, plan)
    template_text = plan.module.prompt_template or ""
    template_rel = str((plan.module.path / m.prompt.template).relative_to(rc.project.method_root))
    template_blob = git.blob_hash(rc.project.method_root, template_rel)
    prompt = render(template_text, m.prompt.vars, prompt_values(rc, plan, ev)) + evidence_suffix(
        rc.project.policy.confidence_criteria
    )
    prompt_hash = store_prompt(store, prompt)
    for text in ev.texts.values():
        store.store_message(hashing.hash_text(text), text)  # exactly what the model saw
    item_schema = plan.module.output_schema or {}
    schema = wrap_schema(item_schema, m.judgment.batching)
    requests = build_requests(action.action_id, prompt, schema, ev, plan, template_rel)
    harness = harness_for(rc, m.model)
    sampling = Sampling(model=m.model)
    dispatch_dir = plan.step_dir / "dispatch"

    if status == StepStatus.ADMISSIBLE:
        if harness.family == "dispatch":
            write_requests(
                requests,
                dispatch_dir,
                step_id=action.step_id,
                action_id=action.action_id,
                schema_name="schema.json",
            )
            transition(
                store,
                rc.run_id,
                action.step_id,
                StepStatus.DISPATCHING,
                payload={"requests": len(requests), "dir": str(dispatch_dir)},
            )
            rc.refresh_status()
            return StepOutcome(
                action.step_id,
                StepStatus.DISPATCHING,
                action,
                message=f"dispatching: {len(requests)} request(s) in {dispatch_dir}; have one fresh subagent answer each, then run again",
            )
        transition(store, rc.run_id, action.step_id, StepStatus.RUNNING)
        replicates = run_direct(harness, requests, schema, sampling)
    else:
        if not request_path(dispatch_dir, requests[0].replicate).exists():
            raise ConfigError(
                f"step {action.step_id} is dispatching but {dispatch_dir} has no request files"
            )
        replicates = collect_dispatch(harness, requests, schema, dispatch_dir)
        transition(store, rc.run_id, action.step_id, StepStatus.RUNNING)

    record_invocations(
        store,
        run_id=rc.run_id,
        step_id=action.step_id,
        action_id=action.action_id,
        replicates=replicates,
        requests=requests,
        prompt_hash=prompt_hash,
        template_path=template_rel,
        template_blob=template_blob,
        sampling=sampling,
        attempt=action.attempt,
    )
    replicates = run_post(rc, plan, replicates)

    rule = rc.project.policy.agreement_rule(rc.project.config.profile)
    from stringency.consensus import consensus_json, settle_items
    from stringency.holds import HoldOutcome, HoldRequest, open_hold

    # invalid replicates open ONE hold for the step, not one per item (42 on the first real
    # judgment, 2026-09-18); the items note them and are decided from the valid replicates
    invalid = [r.index for r in replicates if not r.valid]
    step_holds: list[HoldOutcome] = []
    if invalid and "any_invalid" in set(rule.hold_on):
        step_holds.append(
            open_hold(
                store,
                HoldRequest(
                    run_id=rc.run_id,
                    step_id=action.step_id,
                    kind="run_disagreement",
                    reason=f"{len(invalid)} invalid replicate(s): {invalid}",
                    waits_on_role="reviewer",
                    bound_module_version=plan.module.ref,
                    bound_input_digest=action.input_digest,
                    bound_params_hash=action.params_hash,
                    context={
                        "phase": "post",
                        "invalid_replicates": invalid,
                        "errors": {
                            str(r.index): (r.invocations[-1].error if r.invocations else None)
                            for r in replicates
                            if not r.valid
                        },
                    },
                ),
            )
        )
    items, item_holds = settle_items(
        store,
        run_id=rc.run_id,
        step_id=action.step_id,
        module_ref=plan.module.ref,
        input_digest=action.input_digest,
        params_hash=action.params_hash,
        items=ev.items,
        replicates=replicates,
        rule=rule,
        tables=ev.tables,
        invalid_held=bool(step_holds),
    )
    item_holds = step_holds + item_holds
    considered = considered_set_record(m.judgment, ev.items, ev.digests)
    produced: dict[str, Path] = {}
    for name, spec in m.outputs.items():
        p = plan.output_paths[name]
        if spec.type == "judgments":
            p.write_text(judgments_jsonl(replicates))
        elif spec.type == "consensus":
            p.write_text(consensus_json(items, considered))
        else:
            continue
        produced[name] = p
    info = ExecInfo(
        runner="engine",
        env_status="verified" if rc.env_digests.get(m.env) else "as_reported",
        command=f"harness:{harness.kind}",
        exit_code=0,
        observed={
            "replicates": len(replicates),
            "valid": sum(1 for r in replicates if r.valid),
            "via": requests and harness.family,
        },
    )
    bundle_extra: dict[str, Any] = {
        "replicates": tuple(r.structured or {} for r in replicates),
        "replicate_valid": tuple(r.valid for r in replicates),
        "items": tuple(ev.items),
        "consensus": tuple(i.to_json() for i in items),
        "evidence_tables": ev.tables,
        "considered_set": considered,
    }
    return finish(
        rc, action, plan, produced, info, bundle_extra=bundle_extra, extra_holds=item_holds
    )


def run_post(rc: RunContext, plan: StepPlan, replicates: list[Replicate]) -> list[Replicate]:
    """`post.*` restructures replicate outputs; its input and output hashes are both recorded."""
    script = plan.module.post_script
    if script is None:
        return replicates
    payload = {
        "replicates": [
            {"replicate": r.index, "valid": r.valid, "structured": r.structured} for r in replicates
        ]
    }
    res = rc.executor.run(
        Job(
            command=interpreter_for(script),
            env_name=plan.module.manifest.env,
            cwd=plan.step_dir,
            stdin_json=payload,
            stdout_path=plan.step_dir / "post.stdout",
            stderr_path=plan.step_dir / "post.stderr",
        )
    )
    if res.exit_code != 0:
        raise ConfigError(f"post-script failed with exit {res.exit_code}")
    out = json.loads(res.stdout())
    rc.store.store_message(hashing.hash_json(payload), json.dumps(payload, sort_keys=True))
    rc.store.store_message(hashing.hash_json(out), json.dumps(out, sort_keys=True))
    by = {int(r["replicate"]): r for r in out.get("replicates", [])}
    for r in replicates:
        if r.index in by and r.valid:
            r.structured = by[r.index].get("structured")
    return replicates


__all__ = ["DISPATCH_SUFFIX", "execute_judgment", "harness_for"]


def considered_set_record(
    judgment: Any, items: list[str], digests: Mapping[str, str]
) -> dict[str, Any] | None:
    """The denominator a salience-type module's output must carry (design 3.5, `considered_set:
    true`; E2): the items table the reviewers judged, its row count and its digest, taken by the
    engine from the evidence rather than asked of the model. None when the module does not
    declare it."""
    if not judgment.considered_set:
        return None
    return {
        "items_from": judgment.items_from,
        "n_items": len(items),
        "digest": digests.get(judgment.items_from),
    }


# -- after the item holds settle -----------------------------------------------------------


def evidence_tables_from_disk(
    plan: StepPlan,
) -> tuple[dict[str, EvidenceTable], dict[str, str]]:
    """The evidence tables as the reviewers saw them, with their digests: what `pre.*` wrote
    under the step's `evidence/` when the module has a pre-script, else the declared inputs.
    Runs nothing."""
    m = plan.module.manifest
    assert m.judgment is not None
    ev_dir = plan.step_dir / "evidence"
    out: dict[str, EvidenceTable] = {}
    digests: dict[str, str] = {}
    for n in m.judgment.evidence:
        spec = m.inputs.get(n)
        if spec is not None and spec.type == "json":
            continue
        cand = ev_dir / f"{n}.tsv"
        ri = plan.inputs.get(n)
        p = cand if cand.exists() else (ri.path if ri is not None and not ri.many else None)
        if p is None:
            raise ConfigError(f"evidence {n} is neither an input nor under {ev_dir}")
        out[n] = load_table(p, n, m.judgment.item_key if n == m.judgment.items_from else None)
        digests[n] = hashing.prefixed(hashing.hash_file(p))
    return out, digests


def replicates_from_trace(
    store: Store, run_id: str, step_id: str, plan: StepPlan, attempt: int
) -> list[Replicate]:
    """Rebuild the replicates of an attempt from the step's `judgments` output (every item with
    its rationale, as written at judgment time) and the judgments table (which replicates were
    invalid). Reads: judgments. The invocations are not rebuilt; nothing here is re-recorded."""
    m = plan.module.manifest
    assert m.judgment is not None
    by_rep: dict[int, list[dict[str, Any]]] = {}
    jpath = next(
        (plan.output_paths[n] for n, s in m.outputs.items() if s.type == "judgments"), None
    )
    if jpath is not None and jpath.exists():
        for line in jpath.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                idx = int(d.pop("replicate"))
                by_rep.setdefault(idx, []).append(d)
    invalid = {
        int(r["replicate"])
        for r in store.all(
            "SELECT replicate FROM judgments WHERE run_id = ? AND step_id = ? AND attempt = ? "
            "AND schema_valid = 0",
            (run_id, step_id, attempt),
        )
    }
    indices = sorted(set(by_rep) | invalid) or list(range(1, m.judgment.replicates + 1))
    out: list[Replicate] = []
    for idx in indices:
        items = by_rep.get(idx, [])
        if idx in invalid or not items:
            out.append(Replicate(idx, None, False, []))
            continue
        structured = items[0] if m.judgment.batching == "per_item" else {"items": items}
        out.append(Replicate(idx, structured, True, []))
    return out


def resettle_after_item_holds(rc: RunContext, step_id: str) -> StepOutcome:
    """The last item hold of a held judgment step was accepted or overridden (design 7.1, 8.4).
    Rewrite the consensus output from the decided consensus in the store and record it as a new
    artifact (the judgment-time file becomes `superseded`), then evaluate the post-phase gates
    against the decided consensus, opening the flag holds that were deferred while the item
    holds were open. Reads: actions, judgments, consensus, holds, artifacts, state_snapshots.
    Writes: artifacts, step_events, predicate_results, holds, steps."""
    from stringency.consensus import consensus_from_store, consensus_json

    store = rc.store
    row = store.one(
        "SELECT * FROM actions WHERE run_id = ? AND step_id = ? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    if row is None:
        raise ConfigError(f"no action for {step_id}")
    action = action_from_row(row)
    plan = plan_step(rc, step_id, action.attempt)
    m = plan.module.manifest
    if m.judgment is None:
        raise ConfigError(f"module {plan.module.ref} is not a judgment module")
    tables, digests = evidence_tables_from_disk(plan)
    items_table = tables.get(m.judgment.items_from)
    items = list(items_table.rows) if items_table is not None else []
    replicates = replicates_from_trace(store, rc.run_id, step_id, plan, action.attempt)
    decided = consensus_from_store(store, rc.run_id, step_id, items)
    considered = considered_set_record(m.judgment, items, digests)

    previous = step_outputs(store, rc.run_id, step_id)
    outputs: dict[str, OutputInfo] = {}
    schema_errors: dict[str, str] = {}
    artifact_ids: list[str] = []
    for name, spec in m.outputs.items():
        path = plan.output_paths[name]
        old = previous.get(name)
        if spec.type == "consensus":
            path.write_text(consensus_json(decided, considered))
            digest = hashing.hash_path(path)
            if old is not None and old["hash"] == digest:
                aid = str(old["artifact_id"])
            else:
                aid, digest = record_output(
                    store,
                    run_id=rc.run_id,
                    step_id=step_id,
                    action_id=action.action_id,
                    name=name,
                    path=path,
                    kind=spec.type,
                )
                if old is not None:
                    store.set_artifact_flag(old["artifact_id"], "status", "superseded")
        elif old is not None:
            aid, digest = str(old["artifact_id"]), str(old["hash"])
        else:
            continue
        artifact_ids.append(aid)
        err = validate_output(plan, name, path) if path.exists() else None
        if err:
            schema_errors[name] = err
        outputs[name] = OutputInfo(
            name, spec.type, str(path), hashing.prefixed(digest), None if err is None else False
        )

    state = latest_state(store, rc.run_id, step_id) or rc.current_state()
    bundle = OutputBundle(
        outputs=outputs,
        replicates=tuple(r.structured or {} for r in replicates),
        replicate_valid=tuple(r.valid for r in replicates),
        consensus=tuple(i.to_json() for i in decided),
        evidence_tables=tables,
        items=tuple(items),
        considered_set=considered,
        observed={
            "replicates": len(replicates),
            "valid": sum(1 for r in replicates if r.valid),
            "resettled_after_item_holds": True,
        },
        env_status="verified" if rc.env_digests.get(m.env) else "as_reported",
        schema_errors=schema_errors,
    )
    ctx = rc.gate_context("post", action, state, bundle)
    gate = evaluate(
        ctx,
        registry=registry,
        store=store,
        policy_digest=rc.policy_digest,
        module=m,
        runner="engine",
    )
    return settle_post(rc, action, plan, gate, artifact_ids, extra_holds=[])
