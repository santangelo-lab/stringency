"""Controls (design 11): the `controls/*.yml` model. Execution is filled in at M10."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from stringency.config import load_yaml
from stringency.exit_codes import ConfigError

ControlKind = Literal["negative", "positive", "planted"]


class FixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    type: str
    blake3: str
    path: str | None = None


class FixtureTruth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    key: str
    column: str | None = None  # the label column (judgment); `expect.equals` names its own
    mapping: str | None = None


class Fixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input: FixtureInput
    truth: FixtureTruth | None = None


class Generator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class ControlSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    control: int
    name: str
    kind: ControlKind
    fixture: Fixture
    generator: Generator | None = None
    expect: dict[str, Any]
    # the parameters the control runs the module with, admitted as the synthetic step's defaults
    # so no `param.agent_proposed` hold opens (open_mode_plan.md 2.6, 2026-10-16)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> ControlSpec:
        if self.control != 1:
            raise ValueError("control must be 1")
        if (
            self.kind == "positive"
            and self.fixture.truth is None
            and not self.expect.get("completed")
        ):
            raise ValueError("a positive control needs fixture.truth (or expect.completed: true)")
        if self.kind in ("negative", "planted") and self.generator is None:
            raise ValueError(f"a {self.kind} control needs a generator")
        if "equals" in self.expect:
            eq = self.expect["equals"]
            if not isinstance(eq, dict) or not eq.get("output") or not eq.get("columns"):
                raise ValueError("expect.equals needs output and columns")
            if self.fixture.truth is None:
                raise ValueError("expect.equals needs fixture.truth (the table to compare with)")
        if "count" in self.expect:
            ct = self.expect["count"]
            if (
                not isinstance(ct, dict)
                or not ct.get("output")
                or not isinstance(ct.get("where"), dict)
            ):
                raise ValueError("expect.count needs output and where: {column, below | above}")
            if "max" not in ct and "min" not in ct:
                raise ValueError("expect.count needs max or min")
        return self


def load_control(path: Path) -> ControlSpec:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping")
    try:
        return ControlSpec.model_validate(data)
    except ValueError as e:
        raise ConfigError(f"{path}: {e}") from None


# -- execution (design 11) --------------------------------------------------------------------
#
# A control runs as a real single-module run through the same gate and trace machinery, in an
# isolated context under `controls/<module>/<control>/`. The synthetic pipeline is the bound
# pipeline's steps up to and including the module's step, with the object input replaced by
# the (generated) fixture, every step engine-run.

import contextlib  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from stringency import hashing  # noqa: E402
from stringency.clock import now_iso  # noqa: E402
from stringency.config import InputItem, InputsManifest  # noqa: E402
from stringency.executor.base import Job  # noqa: E402
from stringency.executor.local import interpreter_for  # noqa: E402
from stringency.exit_codes import RefusedError  # noqa: E402
from stringency.ids import new_id  # noqa: E402
from stringency.modules import Module  # noqa: E402
from stringency.pipelines import Pipeline, StepDecl  # noqa: E402
from stringency.project import Project  # noqa: E402


@dataclass
class ControlResult:
    module: str
    control: str
    kind: ControlKind
    run_id: str
    step_status: str
    passed: bool
    metrics: dict[str, Any]
    previous: dict[str, Any] | None = None
    regression: bool = False
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "control": self.control,
            "kind": self.kind,
            "run_id": self.run_id,
            "step_status": self.step_status,
            "passed": self.passed,
            "metrics": self.metrics,
            "previous": self.previous,
            "regression": self.regression,
            "notes": self.notes,
        }


class ControlProject(Project):
    """A view of the project with a synthetic pipeline, a control input, and runs under controls/."""

    def __init__(
        self,
        base: Project,
        pipeline: Pipeline,
        inputs: InputsManifest,
        run_root: Path,
        summaries: dict[str, Any],
        mode: str | None = None,
    ) -> None:
        self.__dict__.update(base.__dict__)
        self.pipeline = pipeline
        self.open_ended = False  # a control run is a declared one-off, never open-ended
        self.inputs = inputs
        # the control is about the module: it runs under a mode the module admits, so a tool that
        # lists `open` only is controlled from a pipeline project too (2026-10-16)
        update: dict[str, Any] = {"execution": "engine"}
        if mode is not None and mode != base.config.mode:
            update.update(mode=mode, pipeline=None if mode == "open" else base.config.pipeline)
            if mode == "open":
                update["domain"] = base.pipeline.domain
        self.config = base.config.model_copy(update=update)
        self._run_root = run_root
        self._summaries = summaries
        self._store = base.store

    def run_dir(self, run_id: str) -> Path:
        return self._run_root / run_id

    def input_summaries(self) -> dict[str, Any]:
        return dict(self._summaries)


def iter_controls(
    project: Project, module_name: str | None = None
) -> Iterator[tuple[Module, ControlSpec, Path]]:
    for module in project.modules.all():
        if module_name and module.manifest.name != module_name:
            continue
        for cf in module.control_files():
            yield module, load_control(cf), cf


def resolve_fixture(project: Project, fx: FixtureInput) -> Path:
    """Fixtures are identified by hash; the path is a hint (design 11)."""
    candidates: list[Path] = []
    if fx.path:
        candidates += [project.method_root / fx.path, project.root / fx.path, Path(fx.path)]
    for d in (
        project.root / "fixtures",
        project.root / "controls" / "fixtures",
        project.method_root / "controls" / "fixtures",
    ):
        if d.exists():
            candidates += sorted(d.iterdir())
    for c in candidates:
        if c.exists() and hashing.hash_path(c) == fx.blake3:
            return c
    raise ConfigError(f"no fixture with blake3 {fx.blake3[:12]} found (hint {fx.path})")


def refuse_holdout(project: Project, digest: str, what: str) -> None:
    if any(h.blake3 == digest for h in project.design.holdout):
        raise RefusedError(
            f"{what} matches a design.holdout fixture; no control or development run may touch it"
        )


def run_generator(project: Project, spec: ControlSpec, fixture: Path, out_dir: Path) -> Path:
    assert spec.generator is not None
    tool = project.plugin.tools.get(spec.generator.tool)
    if tool is None:
        raise ConfigError(f"plugin {project.plugin.name} has no tool {spec.generator.tool}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"generated{fixture.suffix}"
    res = project.executor().run(
        Job(
            command=interpreter_for(tool.script),
            env_name=tool.env or (project.env_names()[0] if project.env_names() else "default"),
            cwd=out_dir,
            ro_bind_paths=[project.method_root],
            stdin_json={
                "inputs": {"input": str(fixture)},
                "params": spec.generator.params,
                "outputs": {"object": str(out)},
            },
            stdout_path=out_dir / "generator.stdout",
            stderr_path=out_dir / "generator.stderr",
        )
    )
    if res.exit_code != 0:
        raise ConfigError(
            f"generator {spec.generator.tool} exited {res.exit_code}: {res.stderr()[-400:]}"
        )
    return out


def _one_step_pipeline(
    project: Project, module: Module, fixture_type: str, params: dict[str, Any]
) -> tuple[Pipeline, str, str]:
    m = module.manifest
    required = [n for n, s in m.inputs.items() if not s.optional]
    matching = [n for n in required if m.inputs[n].type == fixture_type]
    if len(matching) != 1:
        raise ConfigError(
            f"a one-step control of {m.ref} needs exactly one required input of type "
            f"{fixture_type}; it has {len(matching)}"
        )
    unwired = [n for n in required if n != matching[0]]
    if unwired:
        raise ConfigError(
            f"a one-step control of {m.ref} leaves required input(s) unwired: {', '.join(unwired)}"
        )
    step = StepDecl(
        id=f"01_{m.name}",
        module=m.ref,
        title=m.name,
        inputs={matching[0]: "$inputs.control_input"},
        params={k: {"default": v} for k, v in params.items()},
        runner="engine",
    )
    pipe = project.pipeline.model_copy(update={"name": f"control-{m.name}", "steps": [step]})
    return pipe, step.id, "control_input"


def synthetic_pipeline(
    project: Project, module: Module, fixture_type: str, params: dict[str, Any] | None = None
) -> tuple[Pipeline, str, str]:
    """The ancestors of the module's step plus the step itself, engine-run, with the object
    input rewired to `control_input`. Returns (pipeline, step id of the module, replaced input name).
    A module in no pipeline step that lists `open` (a tool; open_mode_plan.md 2.6) runs as a
    one-step pipeline: its one required input of the fixture's type bound to `control_input`,
    the other inputs left unwired (phase 1: they must be optional)."""
    pipe = project.pipeline
    target = next((s for s in pipe.steps if s.module_name == module.manifest.name), None)
    required_types = {s.type for s in module.manifest.inputs.values() if not s.optional}
    if "open" in module.manifest.modes and fixture_type in required_types:
        # a tool is controlled alone, whatever pipeline also uses it: the truth table describes
        # the tool's output on the fixture, not the fixture after some upstream step (2026-10-16)
        return _one_step_pipeline(project, module, fixture_type, params or {})
    if target is None:
        raise ConfigError(f"module {module.ref} is not used by pipeline {pipe.name}")
    keep: set[str] = {target.id}
    frontier = [target.id]
    while frontier:
        cur = pipe.step(frontier.pop())
        for p in cur.predecessors():
            if p not in keep:
                keep.add(p)
                frontier.append(p)
    replaced = None
    steps: list[StepDecl] = []
    for s in pipe.steps:
        if s.id not in keep:
            continue
        inputs = dict(s.inputs)
        for k in list(inputs):
            for ref in s.refs()[k]:
                if ref.kind != "inputs" or ref.pattern:
                    continue
                item = project.inputs.by_name().get(ref.name)
                if item is not None and item.type == fixture_type:
                    inputs[k] = "$inputs.control_input"
                    replaced = ref.name
                    break
        update: dict[str, Any] = {"inputs": inputs, "runner": "engine"}
        if s.id == target.id and params:
            # the control's parameters as the step's defaults: admitted, no hold
            from stringency.pipelines import ParamDecl

            merged = dict(s.params)
            for k, v in params.items():
                prior = merged.get(k)
                merged[k] = ParamDecl(
                    default=v,
                    range=prior.range if prior else None,
                    options=prior.options if prior else None,
                )
            update["params"] = merged
        steps.append(s.model_copy(update=update))
    if replaced is None:
        raise ConfigError(
            f"no input of type {fixture_type} feeds {module.ref}; the control fixture cannot be wired"
        )
    return (
        pipe.model_copy(update={"name": f"control-{module.manifest.name}", "steps": steps}),
        target.id,
        replaced,
    )


def _truth_rows(project: Project, spec: ControlSpec) -> dict[str, dict[str, str]]:
    """The truth table's rows keyed by `truth.key`."""
    assert spec.fixture.truth is not None
    t = spec.fixture.truth
    path = project.method_root / t.path
    if not path.exists():
        path = project.root / t.path
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t" if path.suffix == ".tsv" else ","))
    return {str(r[t.key]): dict(r) for r in rows}


def _truth(project: Project, spec: ControlSpec) -> dict[str, str]:
    assert spec.fixture.truth is not None
    t = spec.fixture.truth
    if t.column is None:
        raise ConfigError(f"control {spec.name}: fixture.truth.column is needed for a label truth")
    rows = _truth_rows(project, spec)
    truth = {k: str(r[t.column]) for k, r in rows.items()}
    if t.mapping:
        mp = project.method_root / t.mapping
        with open(mp, newline="") as f:
            mrows = list(csv.DictReader(f, delimiter="\t" if mp.suffix == ".tsv" else ","))
        cols = list(mrows[0].keys()) if mrows else []
        m = {str(r[cols[0]]): str(r[cols[1]]) for r in mrows} if len(cols) >= 2 else {}
        truth = {k: m.get(v, v) for k, v in truth.items()}
    return truth


def evaluate_expectations(
    project: Project, spec: ControlSpec, run_id: str, step_id: str, module: Module
) -> tuple[bool, dict[str, Any], list[str]]:
    """Metrics from the trace (judgments and consensus), then `expect`. A deterministic module
    is scored by `expect.equals` (the output table against the truth table, keyed by
    `truth.key`), `expect.count` (rows of the output meeting a condition, at most or at least)
    and `expect.completed` (the step completed, the implicit score before 2026-10-16)."""
    store = project.store
    notes: list[str] = []
    if module.manifest.kind != "judgment":
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (run_id, step_id)
        )
        metrics_d: dict[str, Any] = {"step_status": st}
        passed_d = st == "completed"
        exp_d = spec.expect
        if "equals" in exp_d and passed_d:
            ok, m = _expect_equals(project, spec, run_id, step_id, exp_d["equals"])
            metrics_d.update(m)
            passed_d = passed_d and ok
        if "count" in exp_d and passed_d:
            ok, m = _expect_count(project, run_id, step_id, exp_d["count"])
            metrics_d.update(m)
            passed_d = passed_d and ok
        return passed_d, metrics_d, notes
    items = {
        r["item_id"]: r
        for r in store.all(
            "SELECT * FROM consensus WHERE run_id=? AND step_id=?", (run_id, step_id)
        )
    }
    judg = store.all(
        "SELECT * FROM judgments WHERE run_id=? AND step_id=? AND item_id != '*'", (run_id, step_id)
    )
    n_items = len(items)
    per_item_abstain = {
        i: all(bool(j["abstain"]) for j in judg if j["item_id"] == i) for i in items
    }
    any_label = {i: any(j["label"] is not None for j in judg if j["item_id"] == i) for i in items}
    abstain_rate = (sum(1 for v in per_item_abstain.values() if v) / n_items) if n_items else 0.0
    metrics: dict[str, Any] = {
        "items": n_items,
        "abstain_rate": round(abstain_rate, 4),
        "held": store.scalar(
            "SELECT COUNT(*) FROM holds WHERE run_id=? AND step_id=? AND item_id IS NOT NULL",
            (run_id, step_id),
        ),
    }
    passed = True
    exp = spec.expect
    if exp.get("null_output"):
        null = all(not any_label[i] for i in items) if items else False
        metrics["null_output"] = null
        passed = passed and null
    if "agreement_min" in exp or "abstain_max" in exp:
        truth = _truth(project, spec)
        called = {i: r for i, r in items.items() if not per_item_abstain[i]}
        labels: dict[str, str | None] = {}
        for i, r in called.items():
            if r["label"] is not None:
                labels[i] = r["label"]
            else:
                # unresolved item: take the unanimous replicate label when all called replicates agree
                reps = {j["label"] for j in judg if j["item_id"] == i and j["label"] is not None}
                labels[i] = next(iter(reps)) if len(reps) == 1 else None
        agree = sum(1 for i, lab in labels.items() if lab is not None and truth.get(i) == lab)
        agreement = agree / len(called) if called else 0.0
        metrics.update(agreement=round(agreement, 4), compared=len(called), truth_items=len(truth))
        if "agreement_min" in exp:
            passed = passed and agreement >= float(exp["agreement_min"])
        if "abstain_max" in exp:
            passed = passed and abstain_rate <= float(exp["abstain_max"])
    if "detect_at" in exp:
        notes.append(
            "planted-control evaluation needs a truth table from the generator; recorded, not scored"
        )
        metrics["detect_at"] = exp["detect_at"]
    return passed, metrics, notes


def _output_rows(project: Project, run_id: str, step_id: str, output: str) -> list[dict[str, str]]:
    row = project.store.one(
        "SELECT path FROM artifacts WHERE run_id=? AND step_id=? AND name=? AND status='produced' "
        "ORDER BY rowid DESC LIMIT 1",
        (run_id, step_id, output),
    )
    if row is None:
        raise ConfigError(f"control: step {step_id} produced no output {output}")
    path = Path(row["path"])
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t" if path.suffix in (".tsv", ".tab") else ","))


def _close(a: str, b: str, tol: float) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a.strip() == b.strip()


def _expect_equals(
    project: Project, spec: ControlSpec, run_id: str, step_id: str, eq: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    """`expect.equals: {output, columns, tolerance: <abs> | {column: abs}}`: every truth row has
    an output row with the same key whose named columns agree (numbers within the tolerance,
    text exactly). Metrics: rows_compared, rows_matching, missing_keys, max_abs_diff."""
    assert spec.fixture.truth is not None
    key = spec.fixture.truth.key
    truth = _truth_rows(project, spec)
    out = {str(r.get(key)): r for r in _output_rows(project, run_id, step_id, str(eq["output"]))}
    columns = [str(c) for c in eq["columns"]]
    tol = eq.get("tolerance", 0)

    def tol_for(c: str) -> float:
        return float(tol.get(c, 0)) if isinstance(tol, dict) else float(tol)

    matching, missing, max_diff = 0, [], 0.0
    for k, trow in truth.items():
        orow = out.get(k)
        if orow is None:
            missing.append(k)
            continue
        ok = True
        for c in columns:
            a, b = str(orow.get(c, "")), str(trow.get(c, ""))
            if not _close(a, b, tol_for(c)):
                ok = False
            with contextlib.suppress(TypeError, ValueError):
                max_diff = max(max_diff, abs(float(a) - float(b)))
        matching += int(ok)
    metrics = {
        "rows_compared": len(truth),
        "rows_matching": matching,
        "missing_keys": missing,
        "max_abs_diff": round(max_diff, 6),
    }
    return (matching == len(truth) and not missing), metrics


def _expect_count(
    project: Project, run_id: str, step_id: str, ct: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    """`expect.count: {output, where: {column, below | above}, max | min}`: how many rows of
    the output satisfy the condition, against a ceiling or a floor (a negative control: "no
    contrast passes adj_p below 0.05 after shuffling")."""
    where = ct["where"]
    col = str(where["column"])
    rows = _output_rows(project, run_id, step_id, str(ct["output"]))
    n = 0
    for r in rows:
        try:
            v = float(r.get(col, ""))
        except (TypeError, ValueError):
            continue
        below = "below" in where and v < float(where["below"])
        above = "above" in where and v > float(where["above"])
        if below or above:
            n += 1
    ok = True
    if "max" in ct:
        ok = ok and n <= int(ct["max"])
    if "min" in ct:
        ok = ok and n >= int(ct["min"])
    return ok, {"count": n, "rows": len(rows)}


def judge_of(store: Any, run_id: str) -> dict[str, str] | None:
    """The harness kind and resolved model of a run's judgment invocations, each as the sorted
    distinct values joined by `,` (one value in the usual case). None when the run has no
    invocation. Reads: invocations."""
    rows = store.all(
        "SELECT DISTINCT harness_kind, model_resolved FROM invocations WHERE run_id=?", (run_id,)
    )
    if not rows:
        return None
    return {
        "harness_kind": ",".join(sorted({str(r["harness_kind"]) for r in rows})),
        "model_resolved": ",".join(sorted({str(r["model_resolved"]) for r in rows})),
    }


def current_for(store: Any, module: Module, env_digest: str | None) -> dict[str, Any]:
    """Whether a tool's last passing control still speaks for it (open_mode_plan.md 2.5):
    `{status: current | stale | failed | none, last_passing}`. `current` when a passing `controls_runs`
    row exists for `name@version` and it ran under the environment digest given (recorded in
    its metrics as `env_digest`); `stale` when the digest differs or either is unknown; `failed`
    when the version's controls ran and none passed; `none` when none ran. Reads:
    controls_runs."""
    row = store.one(
        "SELECT control_name, kind, ts, metrics_json FROM controls_runs WHERE module=? AND "
        "module_version=? AND passed=1 ORDER BY ts DESC, rowid DESC LIMIT 1",
        (module.manifest.name, module.manifest.version),
    )
    if row is None:
        ran = store.scalar(
            "SELECT COUNT(*) FROM controls_runs WHERE module=? AND module_version=?",
            (module.manifest.name, module.manifest.version),
        )
        return {"status": "failed" if ran else "none", "last_passing": None}
    metrics = json.loads(row["metrics_json"] or "{}")
    ran_under = metrics.get("env_digest")
    status = "current" if env_digest and ran_under == env_digest else "stale"
    return {
        "status": status,
        "last_passing": {
            "control": row["control_name"],
            "kind": row["kind"],
            "ts": row["ts"],
            "env_digest": ran_under,
            "harness_kind": metrics.get("harness_kind"),
            "model_resolved": metrics.get("model_resolved"),
        },
    }


def regression_against(previous: dict[str, Any] | None, metrics: dict[str, Any]) -> bool:
    """A metric moved in the bad direction relative to the last passing result: a lower
    agreement, a higher abstain rate, fewer matching rows, a null output lost."""
    if not previous:
        return False
    if (
        "rows_matching" in previous
        and "rows_matching" in metrics
        and metrics["rows_matching"] < previous["rows_matching"]
    ):
        return True
    if (
        "agreement" in previous
        and "agreement" in metrics
        and metrics["agreement"] < previous["agreement"]
    ):
        return True
    if (
        "abstain_rate" in previous
        and "abstain_rate" in metrics
        and metrics["abstain_rate"] > previous["abstain_rate"]
        and "agreement" in metrics
    ):
        return True
    return bool(previous.get("null_output") and not metrics.get("null_output", True))


def run_control(
    project: Project, module: Module, spec: ControlSpec, *, allow_mock: bool = False
) -> ControlResult:
    """Execute one control end to end and record it. Writes: controls_runs, and everything a
    run writes, under `controls/<module>/<control>/`."""
    # a deterministic tool's control never reaches the harness, so the mock answers nothing
    # there (2026-10-19, open mode: controls run before a tool's first use)
    if (
        project.config.judgment_harness == "mock"
        and not allow_mock
        and module.manifest.kind == "judgment"
    ):
        raise RefusedError(
            "controls must exercise the real judgment harness; the mock is refused (use --allow-mock in tests)"
        )
    ctrl_dir = project.root / "controls" / module.manifest.name / spec.name
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    fixture = resolve_fixture(project, spec.fixture.input)
    refuse_holdout(project, spec.fixture.input.blake3, f"control {spec.name} fixture")
    input_path = (
        run_generator(project, spec, fixture, ctrl_dir / "generated") if spec.generator else fixture
    )
    input_digest = hashing.hash_path(input_path)
    refuse_holdout(project, input_digest, f"control {spec.name} generated input")
    pipeline, step_id, replaced = synthetic_pipeline(
        project, module, spec.fixture.input.type, spec.params
    )
    items = [
        InputItem(
            name="control_input",
            path=str(input_path),
            type=spec.fixture.input.type,
            blake3=input_digest,
            source=f"control {spec.name}",
        )
    ]
    items += [i for i in project.inputs.items if i.name != replaced]
    inputs = InputsManifest(items=items)
    from stringency.extract import extract_object

    summaries = dict(project.input_summaries())
    if spec.fixture.input.type in project.plugin.object_types:
        ext = extract_object(
            project.plugin,
            project.executor(),
            object_type=spec.fixture.input.type,
            object_path=input_path,
            design=project.design.model_dump(),
            env_name=module.manifest.env,
            workdir=ctrl_dir / "extract",
        )
        summaries["control_input"] = ext.summary
    modes = module.manifest.modes
    mode = project.config.mode if project.config.mode in modes else (modes[0] if modes else None)
    cp = ControlProject(project, pipeline, inputs, ctrl_dir, summaries, mode=mode)

    from stringency.runloop import run_loop
    from stringency.runs import open_run

    open_ctrl = project.store.one(
        "SELECT * FROM runs WHERE kind='control' AND status IN ('running','held') AND json_extract(delta_json, '$.control') = ? "
        "AND json_extract(delta_json, '$.module') = ? ORDER BY started DESC LIMIT 1",
        (spec.name, module.ref),
    )
    if open_ctrl is not None and open_ctrl["status"] == "running":
        from stringency.runs import load_run

        rc = load_run(cp, open_ctrl["run_id"])
    else:
        rc = open_run(
            cp,
            kind="control",
            delta={"control": spec.name, "module": module.ref, "kind": spec.kind},
        )
    nx = run_loop(rc)
    st = str(rc.step_status().get(step_id))
    if nx.kind == "dispatching":
        return ControlResult(
            module.ref,
            spec.name,
            spec.kind,
            rc.run_id,
            st,
            False,
            {},
            notes=["dispatching: answer the requests and run controls again"],
        )
    passed, metrics, notes = evaluate_expectations(project, spec, rc.run_id, step_id, module)
    # the environment the control ran under, so `current_for` can tell a stale pass from a
    # current one (open_mode_plan.md 2.5); additive in the metrics, no schema change
    metrics["env_digest"] = rc.env_digests.get(module.manifest.env)
    # the judge that answered (backlog L3): a passing control speaks for one harness and model;
    # additive in the metrics, no schema change. Absent for a deterministic tool's control.
    judge = judge_of(project.store, rc.run_id)
    if judge is not None:
        metrics["harness_kind"] = judge["harness_kind"]
        metrics["model_resolved"] = judge["model_resolved"]
    prev = project.store.one(
        "SELECT metrics_json FROM controls_runs WHERE module=? AND module_version=? AND control_name=? AND passed=1 ORDER BY ts DESC, rowid DESC LIMIT 1",
        (module.manifest.name, module.manifest.version, spec.name),
    )
    previous = json.loads(prev["metrics_json"]) if prev else None
    regression = regression_against(previous, metrics)
    project.store.insert(
        "controls_runs",
        {
            "control_run_id": new_id(),
            "module": module.manifest.name,
            "module_version": module.manifest.version,
            "control_name": spec.name,
            "kind": spec.kind,
            "run_id": rc.run_id,
            "passed": passed,
            "metrics_json": metrics,
            "ts": now_iso(),
        },
    )
    if rc.run["status"] not in ("completed",):
        from stringency.runs import close_run

        if st != "completed":
            # the run's open holds are withdrawn with it, so none lingers in a person's queue
            # (`abandon` would do this but walks the project's pipeline, not the control's)
            open_ids = [
                r["hold_id"]
                for r in project.store.all(
                    "SELECT hold_id FROM holds WHERE run_id = ? AND resolved_by_review IS NULL "
                    "AND resolved_via IS NULL",
                    (rc.run_id,),
                )
            ]
            if open_ids:
                project.store.withdraw_holds(open_ids, "control run closed")
        close_run(
            rc, "completed" if st == "completed" else "abandoned", reason="control run closed"
        )
    return ControlResult(
        module.ref,
        spec.name,
        spec.kind,
        rc.run_id,
        st,
        passed,
        metrics,
        previous,
        regression,
        notes,
    )


def run_controls(
    project: Project, module_name: str | None = None, *, allow_mock: bool = False
) -> list[ControlResult]:
    results = []
    for module, spec, _ in iter_controls(project, module_name):
        results.append(run_control(project, module, spec, allow_mock=allow_mock))
    return results


def ensure_current(project: Project, module: Module, env_digest: str | None) -> list[ControlResult]:
    """Open mode (2026-10-19): before a tool's step, run its controls when none speaks for it
    under this environment (`current_for` is not `current`), so a tool the method tested is
    labelled trusted without the operator having to remember `controls run`. Deterministic
    tools only: a judgment tool's control dispatches to the harness and is the operator's
    `controls run`. Returns the results ([] when nothing ran). Writes what `run_control`
    writes."""
    if module.manifest.kind != "deterministic" or not module.control_files():
        return []
    if current_for(project.store, module, env_digest)["status"] == "current":
        return []
    return run_controls(project, module.manifest.name)
