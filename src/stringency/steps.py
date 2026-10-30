"""Run one step end to end (design 3.4, 3.5, 7.1).

`propose` constructs the Action, writes it, and runs the pre-gate. `execute_engine` runs an
admissible deterministic or report step through the executor. `finish` is the shared
post-execution path for both runners: hash and record outputs, validate schemas, extract
state, snapshot, write the execution row, run the post-gate, and settle the step.
"""

from __future__ import annotations

import fnmatch
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.actions import Action, build_action, write_action
from stringency.active import executing
from stringency.artifacts import record_output, step_outputs
from stringency.clock import now_iso
from stringency.executor.base import Executor, Job
from stringency.executor.local import interpreter_for
from stringency.exit_codes import BlockedError, ConfigError, RefusedError
from stringency.extract import extract_object
from stringency.gate import GateResult, evaluate
from stringency.holds import HoldOutcome, HoldRequest, open_hold
from stringency.ids import new_id
from stringency.machine import RETRYABLE, StepStatus, step_status, transition
from stringency.modules import IOSpec, Module, ModuleManifest
from stringency.pipelines import Ref, StepDecl
from stringency.predicates import registry
from stringency.predicates.context import EvidenceTable, OutputBundle, OutputInfo
from stringency.resources import Allocation
from stringency.runs import RunContext
from stringency.schemas import validate
from stringency.state import ObjectState, State, store_snapshot
from stringency.tables import load_table
from stringency.when import skip_decision

EXT = {"csv": "csv", "tsv": "tsv", "json": "json", "jsonl": "jsonl", "md": "md", "txt": "txt"}


@dataclass(frozen=True)
class ResolvedInput:
    """A step input as bound: one path, or for an `arity: many` module input several
    (3.1, 2026-09-23). `digest` is bare hex: the file's for one, the hash of the parts' digests
    in order for many, so the action's input digest changes when any part or the order does."""

    name: str
    paths: tuple[Path, ...]
    digests: tuple[str, ...]  # bare hex, one per path
    type: str
    many: bool = False

    @property
    def path(self) -> Path:
        if self.many:
            raise ConfigError(f"input {self.name} has arity many; it has {len(self.paths)} paths")
        return self.paths[0]

    @property
    def digest(self) -> str:
        if self.many:
            return hashing.hash_json(list(self.digests))
        return self.digests[0]

    def job_value(self) -> str | list[str]:
        return [str(p) for p in self.paths] if self.many else str(self.paths[0])


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
    # open mode: an on-demand step's inputs are bound read-only, so a session script cannot
    # write beside the delivery it reads (open_mode_plan.md 2.4, design 10.3)
    inputs_read_only: bool = False
    timeout: float | None = None  # an exec step: the policy's open.exec_timeout_s
    network_isolation: bool = False  # an exec step asks the executor to isolate the network
    method_root: Path | None = None  # the checkout bound read-only (default: above the module)
    # what the step runs with (L130): job.json `resources`, the environment, the event
    resources: Allocation | None = None


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
    network: str | None = None  # exec steps: none | unenforced | n/a (open_mode_plan.md 2.4)


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
    """`$inputs.<name>` from the manifest; `$steps.<id>.<out>` from that step's produced
    artifacts. An `arity: many` input takes a list of references or a `$inputs.<glob>`, which
    expands to every manifest input whose name matches and whose type is the input's, in name
    order; it must resolve to at least one part unless the input is optional. A reference to a
    skipped step's output (L13) resolves to nothing, so an optional input is omitted and a
    required one raises (lint refuses that wiring)."""
    out: dict[str, ResolvedInput] = {}
    inputs_by_name = rc.project.inputs.by_name()
    for name, refs in step.refs().items():
        spec = module.manifest.inputs.get(name)
        many = spec is not None and spec.arity == "many"
        if not many and (len(refs) != 1 or refs[0].pattern):
            raise ConfigError(
                f"step {step.id}: input {name} takes one reference; a list or a glob needs "
                f"`arity: many` on the module input"
            )
        paths: list[Path] = []
        digests: list[str] = []
        types: list[str] = []
        for ref in refs:
            if ref.kind == "inputs":
                if ref.pattern:
                    matches = [
                        i
                        for n, i in sorted(inputs_by_name.items())
                        if fnmatch.fnmatchcase(n, ref.name)
                        and (spec is None or i.type == spec.type)
                    ]
                else:
                    item = inputs_by_name.get(ref.name)
                    if item is None:
                        raise ConfigError(
                            f"step {step.id}: no input named {ref.name} in inputs.yml"
                        )
                    matches = [item]
                for item in matches:
                    paths.append(Path(item.path))
                    digests.append(item.blake3)
                    types.append(item.type)
            else:
                if step_status(rc.store, rc.run_id, ref.name) == StepStatus.SKIPPED:
                    continue  # a skipped step's outputs resolve to nothing (L13)
                produced = step_outputs(rc.store, rc.run_id, ref.name)
                row = produced.get(ref.output or "")
                if row is None:
                    raise ConfigError(
                        f"step {step.id}: {ref} has not been produced in run {rc.run_id}"
                    )
                paths.append(Path(row["path"]))
                digests.append(str(row["hash"]))
                types.append(spec.type if spec else str(row["kind"]))
        if not paths:
            if spec is not None and spec.optional:
                continue
            raise ConfigError(
                f"step {step.id}: input {name} resolved to nothing ({', '.join(map(str, refs))})"
            )
        out[name] = ResolvedInput(
            name,
            tuple(paths),
            tuple(digests),
            spec.type if spec else types[0],
            many=many,
        )
    return out


def plan_step(rc: RunContext, step_id: str, attempt: int) -> StepPlan:
    step = rc.decl(step_id)
    module = rc.module_for(step_id)
    step_dir = rc.project.step_dir(rc.run_id, step_id)
    output_paths = {
        name: step_dir / f"{name}.{EXT.get(spec.format or '', spec.format or 'out')}"
        for name, spec in module.manifest.outputs.items()
    }
    entry = rc.on_demand_entry(step_id)
    is_exec = entry is not None and entry.get("kind") == "exec"
    timeout = (
        float(rc.project.policy.profile(rc.project.config.profile).open.exec_timeout_s)
        if is_exec
        else None
    )
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
        inputs_read_only=entry is not None,
        method_root=rc.project.method_root,
        timeout=timeout,
        network_isolation=is_exec,
        resources=rc.allocation(module, timeout_s=timeout),
    )


# -- on-demand steps (open mode, open_mode_plan.md 2.2) --------------------------------------


def _is_artifact_id(text: str) -> bool:
    return len(text) == 26 and text.isalnum() and text.upper() == text


def _latest_of_one_output(rc: RunContext, refs: list[str]) -> tuple[str, list[str]] | None:
    """Among delivered inputs of one type that are one output name delivered by several steps
    (`derived_from.output` equal, each named `<step>_<output>` by
    `project.declarations_from_delivery`), the one from the latest step, by step id order (a
    pipeline's step ids are numbered in run order), and the others; None when the inputs are not
    all of that shape (L135)."""
    by_name = rc.project.inputs.by_name()
    items = [by_name[r.removeprefix("$inputs.")] for r in refs]
    keyed: list[tuple[str, str]] = []
    outputs: set[str] = set()
    for item, r in zip(items, refs, strict=True):
        d = item.derived_from
        if d is None or not d.step_id or not d.output or item.name != f"{d.step_id}_{d.output}":
            return None
        outputs.add(d.output)
        keyed.append((d.step_id, r))
    if len(outputs) != 1 or len({k for k, _ in keyed}) != len(keyed):
        return None
    keyed.sort()
    return keyed[-1][1], [r for _, r in keyed[:-1]]


def bind_inputs(
    rc: RunContext,
    module: Module,
    bindings: dict[str, str],
    *,
    record: dict[str, Any] | None = None,
) -> dict[str, str]:
    """The input references of an on-demand step: `--in <name>=<$inputs.x | $steps.id.out |
    artifact id>` for what the operator named; an unbound input binds the one delivered project
    input or else the latest produced artifact of its type (an input of the upstream pipeline
    binds only when named); several delivered inputs of its type that are one output delivered
    by several steps bind the latest step's, recorded in `record` (`bound_by: latest_step`, the
    alternatives; L135); otherwise refused (exit 15) naming the `--in` forms. An optional input
    binds only what is named or an artifact of this run produced under its own name, else stays
    unbound (L49). Reads: artifacts, steps; writes nothing (the caller puts `record` in the
    step's `created` event)."""
    out: dict[str, str] = {}
    inputs_by_name = rc.project.inputs.by_name()
    for name, ref in bindings.items():
        if name not in module.manifest.inputs:
            raise ConfigError(
                f"{module.manifest.name} has no input {name}; inputs: "
                + ", ".join(module.manifest.inputs)
            )
        if _is_artifact_id(ref):
            row = rc.store.one(
                "SELECT step_id, name FROM artifacts WHERE run_id=? AND artifact_id=? AND "
                "status='produced'",
                (rc.run_id, ref),
            )
            if row is None:
                raise ConfigError(f"input {name}: no produced artifact {ref} in run {rc.run_id}")
            ref = f"$steps.{row['step_id']}.{row['name']}"
        Ref.parse(ref)  # raises ConfigError on a malformed reference
        out[name] = ref
    for name, spec in module.manifest.inputs.items():
        if name in out:
            continue
        # the upstream pipeline's own inputs bind only when named: a tool reads the delivery
        candidates: list[str] = [
            f"$inputs.{n}"
            for n, item in sorted(inputs_by_name.items())
            if item.type == spec.type and item.upstream_input is None
        ]
        produced = [
            f"$steps.{r['step_id']}.{r['name']}"
            for r in rc.store.all(
                "SELECT a.step_id, a.name FROM artifacts a JOIN steps s ON s.run_id=a.run_id AND "
                "s.step_id=a.step_id WHERE a.run_id=? AND a.kind=? AND a.status='produced' AND "
                "s.status='completed' ORDER BY a.rowid DESC",
                (rc.run_id, spec.type),
            )
        ]
        if spec.optional:
            # an optional input binds nothing by type alone (a table of another purpose bound to
            # score-pathways' gene sets, 2026-10-20, backlog L49): only --in, or an artifact this
            # run produced under the input's own name
            same_name = [p for p in produced if p.endswith(f".{name}")]
            if same_name:
                out[name] = same_name[0]
            continue
        latest = _latest_of_one_output(rc, candidates) if len(candidates) > 1 else None
        if len(candidates) == 1 and not produced:
            out[name] = candidates[0]
        elif produced:
            out[name] = produced[0]
        elif latest is not None:
            out[name] = latest[0]
            if record is not None:
                record[name] = {
                    "bound_by": "latest_step",
                    "ref": latest[0],
                    "alternatives": latest[1],
                }
        else:
            upstream = [
                f"$inputs.{n}"
                for n, item in sorted(inputs_by_name.items())
                if item.type == spec.type and item.upstream_input is not None
            ]
            forms = " or ".join(f"--in {name}={c}" for c in candidates + upstream)
            if len(candidates) > 1:
                why = (
                    f"{len(candidates)} inputs have its type and are not one output delivered "
                    "by several steps"
                )
            else:
                why = "no delivered input or produced artifact has its type"
            raise ConfigError(
                f"input {name} ({spec.type}) of {module.manifest.name} is unbound: {why}; "
                + (f"name one with {forms}" if forms else f"name it with --in {name}=<ref>")
                + (
                    " (an upstream input binds only by name)"
                    if upstream and len(candidates) <= 1
                    else ""
                )
            )
    return out


def propose_tool(
    rc: RunContext,
    name: str,
    bindings: dict[str, str],
    proposed: dict[str, Any] | None,
    rationale: str | None,
    *,
    source: str = "agent",
    question_id: str | None = None,
    gives: str | None = None,
) -> Proposal:
    """`call <tool>`: add a tool step to an open run and propose it (open_mode_plan.md 2.2).
    The declaration carries no `params`, so `build_action` fills the module schema's defaults;
    `source` labels every proposed value (`agent`, or `person` for a value the person dictated,
    which opens no `param.agent_proposed` hold). Writes: steps, step_events (`created` with the
    on-demand declaration, `gives` when said (L139), and, when an input was bound by the
    latest-step rule, its `binding`), then everything `propose` writes."""
    if not rc.open_ended:
        raise RefusedError("call runs a tool on demand in an open project only")
    module = rc.project.tool(name)
    bound: dict[str, Any] = {}
    decl = StepDecl(
        id=rc.next_step_id(module.manifest.name),
        module=module.ref,
        title=module.manifest.name,
        inputs=bind_inputs(rc, module, bindings, record=bound),
        runner="engine",
    )
    rc.create_on_demand_step(
        decl, "tool", module, question_id=question_id, binding=bound or None, gives=gives
    )
    return propose(rc, decl.id, proposed, rationale=rationale, source=source)


EXEC_FORMATS = {
    "table": "tsv",
    "frame": "csv",
    "json": "json",
    "jsonl": "jsonl",
    "text": "md",
    "prose": "md",
    "figure": "svg",
}
EXEC_LANGS = {"py": "py", "python": "py", "r": "R", "R": "R", "sh": "sh", "bash": "sh"}


def _kind_of_ref(rc: RunContext, ref: str) -> str:
    """The recorded kind of what a reference binds: a project input's type or a produced
    artifact's kind."""
    r = Ref.parse(ref)
    if r.kind == "inputs":
        item = rc.project.inputs.by_name().get(r.name)
        if item is None:
            raise ConfigError(f"no input named {r.name} in inputs.yml")
        return item.type
    produced = step_outputs(rc.store, rc.run_id, r.name)
    row = produced.get(r.output or "")
    if row is None:
        raise ConfigError(f"{ref} has not been produced in run {rc.run_id}")
    return str(row["kind"])


def exec_egress_class(executor: str) -> int:
    """What a session script may send off the machine (backlog L40): nothing when the executor
    isolates its network (apptainer, `--net --network none`, verified at run time and recorded
    in `executions.network`), anything under the local executor, which enforces nothing."""
    return 0 if executor == "apptainer" else 4


def exec_manifest(
    *,
    blob: str,
    domain: str,
    env: str,
    ext: str,
    inputs: dict[str, str],
    outputs: dict[str, tuple[str, str]],
    seed: int,
) -> ModuleManifest:
    """The synthetic manifest of an exec step (open_mode_plan.md 2.4): name `exec`, version the
    script's hash prefix, deterministic, operation `exec`, open mode only, the bound inputs by
    kind, the declared outputs, and a `seed` parameter whose default is the seed the step runs
    with (so the engine records one and no `param.agent_proposed` hold opens for it)."""
    return ModuleManifest(
        contract=1,
        name="exec",
        version=blob[:12],
        kind="deterministic",
        operation="exec",
        domain=domain,
        modes=["open"],
        env=env,
        runner="engine",
        entry=f"script.{ext}",
        inputs={k: IOSpec(type=t) for k, t in inputs.items()},
        outputs={k: IOSpec(type=t, format=f) for k, (t, f) in outputs.items()},
        stochastic=True,
        seed_param="seed",
        params_schema={
            "type": "object",
            "properties": {"seed": {"type": "integer", "default": seed}},
            "additionalProperties": False,
        },
    )


def parse_outs(outs: list[str]) -> dict[str, tuple[str, str]]:
    """`--out <name>=<type>[/<format>]`; the format defaults by type (table/tsv, frame/csv,
    json, text/md, figure/svg), else the type's own name."""
    out: dict[str, tuple[str, str]] = {}
    for s in outs:
        if "=" not in s:
            raise ConfigError(f"--out expects <name>=<type>[/<format>], got {s!r}")
        name, _, spec = s.partition("=")
        typ, _, fmt = spec.partition("/")
        name, typ, fmt = name.strip(), typ.strip(), fmt.strip()
        if not name or not typ:
            raise ConfigError(f"--out expects <name>=<type>[/<format>], got {s!r}")
        out[name] = (typ, fmt or EXEC_FORMATS.get(typ, typ))
    return out


def propose_exec(
    rc: RunContext,
    script: str,
    *,
    lang: str = "py",
    bindings: dict[str, str] | None = None,
    outputs: dict[str, tuple[str, str]],
    env: str | None = None,
    seed: int | None = None,
    rationale: str | None = None,
    question_id: str | None = None,
    allow_local: bool = False,
    gives: str | None = None,
) -> Proposal:
    """`exec`: run a script written in the session as an on-demand step of the open run
    (open_mode_plan.md 2.4; owner's decision 1, 2026-10-16). The script text (a file or stdin,
    never argv) is copied to `runs/<run>/<step>/script.<ext>`, hashed and stored in `messages`
    under its hash; the step's manifest is `exec_manifest`; the declaration binds `--in` names
    (added to every delivered input by name; an upstream pipeline input only when named) and
    runs on the engine. Refused (exit 16) when the profile's `open.exec` is `refused`, and under
    the `local` executor without `allow_local` (the local executor inherits the engine's whole
    environment; development only).
    `gives` (L139), the quantity the script's output is, goes on the `created` event.
    Writes: the script file, messages, steps, step_events, then everything `propose` writes."""
    if not rc.open_ended:
        raise RefusedError("exec runs a session script in an open project only")
    profile = rc.project.policy.profile(rc.project.config.profile)
    if profile.open.exec != "allowed":
        raise RefusedError(
            f"exec is refused under profile {rc.project.config.profile} (policy open.exec)"
        )
    egress_cfg = rc.project.config.egress
    exec_class = exec_egress_class(rc.project.config.executor)
    if egress_cfg.max_class is not None and exec_class > egress_cfg.max_class:
        from stringency.egress import CLASS_NAMES

        raise BlockedError(
            "blocked at exec: prov.egress_exceeds_ceiling@1 [block]: a session script under the "
            f"{rc.project.config.executor} executor is class {exec_class} {CLASS_NAMES[exec_class]} "
            f"(backlog L40), over the project ceiling class {egress_cfg.max_class} "
            f"{CLASS_NAMES[egress_cfg.max_class]}; report {rc.project.root / 'prov' / 'egress.md'}"
        )
    if rc.project.config.executor == "local" and not allow_local:
        raise RefusedError(
            "exec under the local executor runs the script with the engine's own environment "
            "and no containment; pass --allow-local for development only"
        )
    ext = EXEC_LANGS.get(lang)
    if ext is None:
        raise ConfigError(f"--lang must be one of {', '.join(sorted(set(EXEC_LANGS)))}")
    if not script.strip():
        raise ConfigError("the script is empty")
    if not outputs:
        raise ConfigError("exec needs at least one --out <name>=<type>[/<format>]")
    envs = rc.project.env_names()
    if env is None:
        if len(envs) != 1:
            raise ConfigError(
                "--env is required: the tools use " + (", ".join(envs) or "no environment")
            )
        env = envs[0]
    elif env not in envs:
        raise ConfigError(
            f"--env {env} is not an environment of the method's tools ({', '.join(envs)})"
        )
    # every delivered input by name, plus what `--in` names: an input of the upstream pipeline
    # (`upstream_*`) is bound only when named, so a script's lineage holds what it may read
    bindings = {
        **{
            i.name: f"$inputs.{i.name}" for i in rc.project.inputs.items if i.upstream_input is None
        },
        **dict(bindings or {}),
    }
    kinds = {name: _kind_of_ref(rc, ref) for name, ref in bindings.items()}
    if seed is None:
        import secrets

        seed = secrets.randbelow(2**31)
    blob = hashing.hash_text(script)
    rc.store.store_message(blob, script)
    manifest = exec_manifest(
        blob=blob,
        domain=rc.project.pipeline.domain,
        env=env,
        ext=ext,
        inputs=kinds,
        outputs=outputs,
        seed=int(seed),
    )
    step_id = rc.next_step_id("exec")
    step_dir = rc.project.step_dir(rc.run_id, step_id)
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / f"script.{ext}").write_text(script)
    module = Module(step_dir, manifest)
    decl = StepDecl(
        id=step_id,
        module=manifest.ref,
        title="a script written in the session",
        inputs=bindings,
        runner="engine",
    )
    rc.create_on_demand_step(
        decl,
        "exec",
        module,
        manifest=manifest.model_dump(mode="json"),
        question_id=question_id,
        gives=gives,
    )
    return propose(rc, step_id, None, rationale=rationale, source="agent")


# -- propose: action + pre-gate ----------------------------------------------------------


def starting_params(rc: RunContext, step_id: str) -> dict[str, tuple[Any, str]] | None:
    """What a step's proposal starts from, below the operator's own values (design 2.5, 2.6):
    the objective's declared parameters for the step (`declared`), overlaid by what a fork's
    ancestor admitted (`fork.inherited_for`). None when there is neither.
    Reads: runs, steps, actions."""
    from stringency.fork import inherited_for

    out: dict[str, tuple[Any, str]] = {
        k: (v, "declared") for k, v in (rc.project.objective.params.get(step_id) or {}).items()
    }
    out.update(inherited_for(rc, step_id) or {})
    return out or None


def propose(
    rc: RunContext,
    step_id: str,
    proposed: dict[str, Any] | None = None,
    rationale: str | None = None,
    source: str = "agent",
    inherited: dict[str, tuple[Any, str]] | None = None,
    cites: list[dict[str, Any]] | None = None,
    considered: list[Any] | None = None,
) -> Proposal:
    """Construct the Action, write it, run the pre-gate, and settle the step as admissible,
    held, or blocked (design 3.4 step 1, 7.1). For operator-run steps an admissible action
    becomes a ticket and the step awaits execution. `inherited` is a forked run's starting
    point for the step (`fork.inherited_for`), below `proposed` and above the defaults.

    `cites` and `considered` (backlog L55) are stored with the reason as one message
    (`{text, cited, considered}`, each citation resolved to its cell) behind `rationale_ref`,
    and the pre-gate reads them from the action in memory.

    The `proposed` step event carries `rendered`, the latest `present --step` mark of each step
    of the run so far (L134 a), when there is one.

    Writes: actions, messages (rationale), predicate_results, steps, step_events, holds.
    Reads: step_events (`rendered`).
    """
    store = rc.store
    if not rc.pipeline.has_step(step_id):
        raise ConfigError(f"no step {step_id} in pipeline {rc.pipeline.name}")
    current = step_status(store, rc.run_id, step_id)
    if current not in RETRYABLE:
        raise RefusedError(f"step {step_id} is {current}; it cannot be proposed now")
    skip = skip_decision(store, rc.pipeline, rc.run_id, step_id)
    if skip is not None:
        raise RefusedError(
            f"step {step_id} does not run in this run ({skip['reason']}); `run` records it as skipped"
        )
    prev_attempt = (
        store.scalar(
            "SELECT attempt FROM steps WHERE run_id = ? AND step_id = ?", (rc.run_id, step_id)
        )
        or 0
    )
    attempt = int(prev_attempt) + 1
    plan = plan_step(rc, step_id, attempt)
    rationale_ref = None
    record: dict[str, Any] | None = None
    if rationale or cites or considered:
        from stringency.citations import resolve_cites

        record = {
            "text": rationale or "",
            "cited": resolve_cites(rc, list(cites or [])),
            "considered": list(considered or []),
        }
        text = (
            rationale
            if rationale and not cites and not considered
            else json.dumps(record, sort_keys=True, default=str)
        )
        assert text is not None
        rationale_ref = hashing.hash_text(text)
        store.store_message(rationale_ref, text)
    action = build_action(
        run_id=rc.run_id,
        step=plan.step,
        module=plan.module,
        attempt=attempt,
        input_digests={k: v.digest for k, v in plan.inputs.items()},
        proposed=proposed,
        rationale_ref=rationale_ref,
        source_label=source,
        inherited=inherited,
    )
    if plan.runner == "operator":
        action = action.with_ticket(action.action_id)
    if record is not None:
        action = Action(**{**action.__dict__, "rationale": record})
    from stringency.present import rendered_marks

    # what `present --step` rendered in this run before the proposal (L134 a), on the event
    proposed_payload: dict[str, Any] = {"action_id": action.action_id}
    marks = rendered_marks(store, rc.run_id)
    if marks:
        proposed_payload["rendered"] = marks
    with store.transaction():
        write_action(store, action)
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.PROPOSED,
            attempt=attempt,
            payload=proposed_payload,
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
        holds = [inherit_flag_acceptance(rc, h, plan) for h in holds]
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
            payload={"ticket": action.ticket, **operator_allocation(rc, action, plan)},
        )
        write_job_file(action, plan)
        status = StepStatus.AWAITING_EXECUTION
    rc.refresh_status()
    return Proposal(action, plan, gate, status, holds)


def inherit_flag_acceptance(rc: RunContext, h: HoldOutcome, plan: StepPlan) -> HoldOutcome:
    """Accept once (backlog L6): an open `param.agent_proposed` hold whose proposed values this
    project's reviewer already accepted on the same step and module version in a sibling of
    the same study is resolved at once, `via: inherited`, by a `reviews` row naming the
    sibling's hold and review. Reads: holds, the siblings' traces. Writes: reviews, holds."""
    if h.rebound or not rc.project.config.study:
        return h
    from stringency import study as st

    store = rc.store
    row = store.one("SELECT * FROM holds WHERE hold_id = ?", (h.hold_id,))
    if row is None or row["kind"] != "flag":
        return h
    ctx = json.loads(row["context_json"] or "{}")
    predicate = str(ctx.get("predicate", "")).split("@")[0]
    if predicate != "param.agent_proposed":
        return h
    proposed = (ctx.get("evidence") or {}).get("proposed")
    if not proposed:
        return h
    siblings = st.study_siblings(rc.project.root, rc.project.config.study, rc.project.siblings_root)
    prior = st.flag_acceptance(
        siblings,
        predicate=predicate,
        step_id=str(row["step_id"]),
        module_version=plan.module.ref,
        proposed=proposed,
        reviewer=rc.project.config.roles.reviewer,
    )
    if prior is None:
        return h
    import socket

    review_id = new_id()
    store.insert(
        "reviews",
        {
            "review_id": review_id,
            "hold_id": h.hold_id,
            "reviewer": prior["reviewer"],
            "host": socket.gethostname(),
            "via": "inherited",
            "ts": now_iso(),
            "verdict": "accept",
            "reason": (
                f"accept once (study {rc.project.config.study}): the same values were accepted "
                f"in {prior['project']}, hold {prior['hold_id']}, review {prior['review_id']} by "
                f"{prior['reviewer']} at {prior['ts']}"
            ),
            "bound_module_version": row["bound_module_version"],
            "bound_input_digest": row["bound_input_digest"],
            "bound_params_hash": row["bound_params_hash"],
        },
    )
    store.resolve_hold(h.hold_id, review_id, "inherited")
    return HoldOutcome(h.hold_id, True, review_id)


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
            payload={"ticket": action.ticket, **operator_allocation(rc, action, plan)},
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
    """The executor job of a step. Input directories are bound read-write for a declared step
    (as before) and read-only for an on-demand one (`plan.inputs_read_only`, design 10.3
    amended 2026-10-16); the method checkout is read-only always. The step's allocation
    (L130) is the stdin's `resources` and the Job's, from which the executor sets the
    environment; the timeout enforced is still the plan's (an exec step's) only."""
    m = plan.module.manifest
    seed = action.parameters.get(m.seed_param) if m.stochastic and m.seed_param else None
    input_dirs = [p.parent for ri in plan.inputs.values() for p in ri.paths]
    # the method checkout (design 10.3); an exec module lives in its step directory, so the
    # checkout is named by the plan, not derived from the module's path
    ro = [plan.method_root or plan.module.path.parent.parent]
    if plan.inputs_read_only:
        ro = input_dirs + ro
        input_dirs = []
    resources = (plan.resources or Allocation()).job_value()
    return Job(
        command=interpreter_for(script),
        env_name=m.env,
        cwd=plan.step_dir,
        bind_paths=input_dirs + [plan.step_dir],
        ro_bind_paths=ro,
        network="none" if plan.network_isolation else None,
        stdin_json={
            "inputs": {k: v.job_value() for k, v in plan.inputs.items()},
            "params": action.parameters,
            "outputs": {k: str(v) for k, v in plan.output_paths.items()},
            "output_dir": str(plan.step_dir),
            "seed": seed,
            "design": plan.design,
            "objective": plan.objective,
            # the allocation the script should size its workers by (L130, module contract note)
            "resources": resources,
        },
        timeout=plan.timeout,
        resources=resources,
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
    # the apptainer line binds <step dir>/tmp:/tmp; the engine's own run() creates it, an
    # operator running the printed line does not (K8, 2026-09-23)
    (plan.step_dir / "tmp").mkdir(exist_ok=True)
    path = plan.step_dir / JOB_FILE
    # keys in the order the engine composed them and the declarations declare them (L128,
    # 2026-10-27): a module reading "the design's first factor" must see design.yml's order,
    # which sorted keys replaced with the alphabetical one
    path.write_text(json.dumps(dict(job.stdin_json or {}), indent=2) + "\n")
    return path


def allocation_payload(executor: Executor, plan: StepPlan, job: Job | None) -> dict[str, Any]:
    """What a step's started event carries about its allocation (L130): `resources` (cpus,
    memory_gb, timeout_s), `resources_source` (each value's source: module, override or
    policy), and `cgroups`, whether the executor enforces the CPUs and memory as limits
    (`applied`, `unavailable`, `not_used`), absent when no job is given (a judgment's started
    event: its scripts ran or run apart from it). Reads nothing from the trace; the caller
    writes it into step_events with the transition."""
    out = (plan.resources or Allocation()).event_payload()
    if job is not None:
        out["cgroups"] = executor.limits_for(job)
    return out


def operator_allocation(rc: RunContext, action: Action, plan: StepPlan) -> dict[str, Any]:
    """`allocation_payload` for an operator step: the job the ticket's printed line runs."""
    script = plan.module.entry_script
    job = job_for(action, plan, script) if script is not None else None
    return allocation_payload(rc.executor, plan, job)


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
    job = job_for(action, plan, script)
    transition(
        store,
        rc.run_id,
        action.step_id,
        StepStatus.RUNNING,
        payload=allocation_payload(rc.executor, plan, job),
    )
    plan.step_dir.mkdir(parents=True, exist_ok=True)
    blob = script_blob(plan.module)  # hashed before it runs; exec.script_drift compares
    with executing(rc.project.root, rc.run_id, action.step_id):
        res = rc.executor.run(job)
    info = ExecInfo(
        runner="engine",
        env_status="verified" if res.env_digest else "as_reported",
        command=res.command,
        exit_code=res.exit_code,
        duration_ms=res.duration_ms,
        stdout_path=str(res.stdout_path),
        stderr_path=str(res.stderr_path),
        script_blob=blob,
        network=(res.network or "n/a") if plan.network_isolation else None,
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
            "network": info.network,
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
        if ri is not None and ri.type == "table" and not ri.many:
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
    cited: list[Any] | None = None
    for name, spec in m.outputs.items():
        if spec.type == "prose":
            prose = produced[name].read_text()
        elif spec.type == "cited" and name in produced:
            # a report's citations (backlog L57): `[{table, row, column, value}]`, the cells
            # its numerals are checked against
            try:
                doc = json.loads(produced[name].read_text())
            except (OSError, json.JSONDecodeError):
                doc = None
            cited = list(doc) if isinstance(doc, list) else []
    extra = dict(bundle_extra or {})
    observed = dict(info.observed)
    if cited is not None:
        observed["cited"] = cited
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
        pending_now = [h.hold_id for h in extra_holds if not h.rebound]
        if pending_now:
            store.withdraw_holds(pending_now, "post-phase block closed the attempt")
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
