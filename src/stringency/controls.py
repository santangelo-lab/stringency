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
    column: str
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

    @model_validator(mode="after")
    def _check(self) -> ControlSpec:
        if self.control != 1:
            raise ValueError("control must be 1")
        if self.kind == "positive" and self.fixture.truth is None:
            raise ValueError("a positive control needs fixture.truth")
        if self.kind in ("negative", "planted") and self.generator is None:
            raise ValueError(f"a {self.kind} control needs a generator")
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
    ) -> None:
        self.__dict__.update(base.__dict__)
        self.pipeline = pipeline
        self.inputs = inputs
        self.config = base.config.model_copy(update={"execution": "engine"})
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


def synthetic_pipeline(
    project: Project, module: Module, fixture_type: str
) -> tuple[Pipeline, str, str]:
    """The ancestors of the module's step plus the step itself, engine-run, with the object
    input rewired to `control_input`. Returns (pipeline, step id of the module, replaced input name)."""
    pipe = project.pipeline
    target = next((s for s in pipe.steps if s.module_name == module.manifest.name), None)
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
            ref = s.refs()[k]
            if ref.kind == "inputs":
                item = project.inputs.by_name().get(ref.name)
                if item is not None and item.type == fixture_type:
                    inputs[k] = "$inputs.control_input"
                    replaced = ref.name
        steps.append(s.model_copy(update={"inputs": inputs, "runner": "engine"}))
    if replaced is None:
        raise ConfigError(
            f"no input of type {fixture_type} feeds {module.ref}; the control fixture cannot be wired"
        )
    return (
        pipe.model_copy(update={"name": f"control-{module.manifest.name}", "steps": steps}),
        target.id,
        replaced,
    )


def _truth(project: Project, spec: ControlSpec) -> dict[str, str]:
    assert spec.fixture.truth is not None
    t = spec.fixture.truth
    path = project.method_root / t.path
    if not path.exists():
        path = project.root / t.path
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t" if path.suffix == ".tsv" else ","))
    truth = {str(r[t.key]): str(r[t.column]) for r in rows}
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
    """Metrics from the trace (judgments and consensus), then `expect`."""
    store = project.store
    notes: list[str] = []
    if module.manifest.kind != "judgment":
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (run_id, step_id)
        )
        return st == "completed", {"step_status": st}, notes
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


def regression_against(previous: dict[str, Any] | None, metrics: dict[str, Any]) -> bool:
    """A metric moved in the bad direction relative to the last passing result."""
    if not previous:
        return False
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
    if project.config.judgment_harness == "mock" and not allow_mock:
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
    pipeline, step_id, replaced = synthetic_pipeline(project, module, spec.fixture.input.type)
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

    ext = extract_object(
        project.plugin,
        project.executor(),
        object_type=spec.fixture.input.type,
        object_path=input_path,
        design=project.design.model_dump(),
        env_name=project.env_names()[0],
        workdir=ctrl_dir / "extract",
    )
    summaries = {**project.input_summaries(), "control_input": ext.summary}
    cp = ControlProject(project, pipeline, inputs, ctrl_dir, summaries)

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
