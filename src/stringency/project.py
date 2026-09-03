"""Project: layout, binding at init, loading a bound project (design 2).

`init_project` writes the layout, clones the method repo at its tag, verifies inputs, runs
lint and the `init.*` predicates, writes `stringency.yml`, opens the trace, and opens the
project-level `confirm` hold bound to the declaration hashes. `Project.load` reads it back.
"""

from __future__ import annotations

import getpass
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stringency import __version__, hashing
from stringency.actions import Action
from stringency.clock import now_iso
from stringency.config import (
    Design,
    InputsManifest,
    MethodRef,
    Objective,
    Roles,
    StringencyConfig,
    dump_yaml,
    load_model,
    load_yaml,
)
from stringency.db.store import Store
from stringency.echo import render_echo
from stringency.executor.base import Executor
from stringency.executor.local import LocalExecutor
from stringency.exit_codes import ConfigError
from stringency.extract import extract_object
from stringency.gate import GateResult, evaluate
from stringency.ids import new_id
from stringency.modules import ModuleIndex
from stringency.pipelines import Pipeline, find_pipeline, load_pipeline
from stringency.plugins import Plugin, require_plugin
from stringency.policy import Policy, load_policy
from stringency.predicates import registry
from stringency.predicates.context import GateContext, ProjectConfig
from stringency.schemas import validate
from stringency.state import ObjectState, State

DECLARATIONS = ("design.yml", "objective.yml", "inputs.yml")


def _ensure_engine_predicates() -> None:
    import stringency.predicates.engine  # noqa: F401  (registers engine predicates)


@dataclass
class InitRequest:
    path: Path
    method: str  # <url>@<tag>
    pipeline: str
    objective: Path
    design: Path
    inputs: Path
    mode: str = "pipeline"
    profile: str = "standard"
    owner: str | None = None
    reviewer: str | None = None
    judgment_harness: str = "subagent"
    execution: str = "operator"
    executor: str = "apptainer"


class Project:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.config = load_model(StringencyConfig, self.root / "stringency.yml")
        self.inputs = load_model(InputsManifest, self.root / "inputs.yml")
        self.design = load_model(Design, self.root / "design.yml")
        self.objective = load_model(Objective, self.root / "objective.yml")
        self.method_root = self.root / "method"
        self.pipeline: Pipeline = load_pipeline(
            find_pipeline(self.method_root, self.config.pipeline)
        )
        self.modules = ModuleIndex(self.method_root)
        _ensure_engine_predicates()
        self.plugin: Plugin = require_plugin(self.pipeline.domain)
        self.policy: Policy = load_policy(self.root / self.config.policy)
        self._store: Store | None = None

    @classmethod
    def load(cls, path: Path | str) -> Project:
        root = Path(path)
        if not (root / "stringency.yml").exists():
            raise ConfigError(f"{root} is not a stringency project (no stringency.yml)")
        return cls(root)

    @classmethod
    def find(cls, start: Path | None = None) -> Project:
        cur = (start or Path.cwd()).resolve()
        for cand in (cur, *cur.parents):
            if (cand / "stringency.yml").exists():
                return cls(cand)
        raise ConfigError("no stringency project found here or in a parent directory")

    # -- paths ----------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return self.root / "prov" / "run.db"

    @property
    def store(self) -> Store:
        if self._store is None:
            self._store = Store.open(self.db_path)
        return self._store

    def run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

    def step_dir(self, run_id: str, step_id: str) -> Path:
        return self.run_dir(run_id) / step_id

    @property
    def scratch(self) -> Path:
        p = self.root / ".stringency"
        p.mkdir(exist_ok=True)
        return p

    # -- environment -----------------------------------------------------------------

    def executor(self, kind: str | None = None) -> Executor:
        k = kind or self.config.executor
        ex: Executor
        if k == "local":
            ex = LocalExecutor(self.method_root / "envs")
        elif k == "apptainer":
            from stringency.executor.apptainer import ApptainerExecutor

            ex = ApptainerExecutor(self.method_root / "envs")
        else:
            raise ConfigError(f"unknown executor {k}")
        return ex

    def env_names(self) -> list[str]:
        names: list[str] = []
        for step in self.pipeline.steps:
            m = self.modules.get(step.module)
            if m and m.manifest.env not in names:
                names.append(m.manifest.env)
        return names

    def policy_digest(self) -> str:
        return self.policy.digest(registry)

    def manifests(self) -> dict[str, Any]:
        return {m.ref: m.manifest for m in self.modules.all()}

    def project_config(self, **runtime: Any) -> ProjectConfig:
        return ProjectConfig(
            config=self.config,
            pipeline=self.pipeline,
            modules=self.manifests(),
            inputs=self.inputs,
            plugin_modes=tuple(self.plugin.modes),
            vocabularies=self.plugin.vocabularies,
            object_types=tuple(self.plugin.object_types),
            **runtime,
        )

    # -- declarations and the confirm hold -------------------------------------------

    def declaration_hashes(self) -> dict[str, str]:
        return {name: hashing.hash_file(self.root / name) for name in DECLARATIONS}

    def declaration_digest(self) -> str:
        return hashing.hash_json(self.declaration_hashes())

    def input_digests_now(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in self.inputs.items:
            p = Path(item.path)
            out[item.name] = hashing.hash_file(p) if p.exists() else "missing"
        return out

    def verify_inputs(self) -> list[str]:
        """Names of inputs whose current hash differs from the recorded one."""
        now = self.input_digests_now()
        return [i.name for i in self.inputs.items if now.get(i.name) != i.blake3]

    def initial_state(self, run_id: str, objects: dict[str, ObjectState] | None = None) -> State:
        return State(
            run_id=run_id,
            after_step=None,
            objects=dict(objects or {}),
            design=self.design.model_dump(),
            objective=self.objective.model_dump(),
            history=(),
            env={"executor": self.config.executor},
            mode=self.config.mode,
            profile=self.config.profile,
        )

    def input_summaries(self) -> dict[str, Any]:
        """Extractor output per object input, from the init pass."""
        cached = self.scratch / "init-extract.json"
        data = json.loads(cached.read_text()) if cached.exists() else {}
        return dict(data) if isinstance(data, dict) else {}

    def extract_inputs(self, executor: Executor, workdir: Path) -> dict[str, ObjectState]:
        """One extractor pass per object input (design 2.7). Returns states by input name."""
        objects: dict[str, ObjectState] = {}
        env = self.env_names()[0] if self.env_names() else "default"
        for item in self.inputs.items:
            if item.type not in self.plugin.object_types:
                continue
            ext = extract_object(
                self.plugin,
                executor,
                object_type=item.type,
                object_path=Path(item.path),
                design=self.design.model_dump(),
                env_name=env,
                workdir=workdir / item.name,
            )
            objects[item.name] = ObjectState(
                type=item.type, digest=hashing.prefixed(item.blake3), summary=ext.summary
            )
        return objects

    def init_context(self, objects: dict[str, ObjectState]) -> GateContext:
        action = Action(
            action_id=self.config.project_id,
            run_id="init",
            step_id="init",
            attempt=0,
            operation="project",
            module="project",
            parameters={},
            param_source={},
            inputs={},
            input_digest=hashing.prefixed(self.declaration_digest()),
            params_hash=hashing.prefixed(hashing.hash_json({})),
            proposed_by="pipeline",
        )
        return GateContext(
            phase="init",
            project=self.project_config(),
            objective=self.objective,
            design=self.design,
            state=self.initial_state("init", objects),
            action=action,
            history=(),
            output=None,
            policy=self.policy,
        )

    def run_init_predicates(self, objects: dict[str, ObjectState], *, record: bool) -> GateResult:
        """Evaluate `init.*` against the declarations. Writes predicate_results when `record`."""
        return evaluate(
            self.init_context(objects),
            registry=registry,
            store=self.store if record else None,
            policy_digest=self.policy_digest(),
            module=None,
            runner=None,
        )

    def echo_path(self) -> Path:
        return self.root / "echo.md"

    def render_echo(self, objects: dict[str, ObjectState] | None = None) -> str:
        counts = {k: v.summary for k, v in (objects or {}).items()}
        if not counts:
            cached = self.scratch / "init-extract.json"
            if cached.exists():
                counts = json.loads(cached.read_text())
        return render_echo(
            self.plugin, self.design, self.objective, self.inputs, counts, self.declaration_hashes()
        )

    def confirm_hold(self) -> Any:
        """Reads: holds. The confirm hold bound to the current declaration digest, or None."""
        return self.store.one(
            "SELECT * FROM holds WHERE kind = 'confirm' AND run_id IS NULL AND step_id IS NULL "
            "AND bound_input_digest = ? ORDER BY created DESC, rowid DESC LIMIT 1",
            (hashing.prefixed(self.declaration_digest()),),
        )

    def ensure_confirm_hold(self, objects: dict[str, ObjectState] | None = None) -> str | None:
        """Open the init confirm hold for the current declarations if none exists (design 2.7).

        Reads: holds. Writes: holds (kind `confirm`, waits on the owner) and `echo.md`.
        Returns the new hold_id, or None when a hold for these declarations already exists.
        """
        if self.confirm_hold() is not None:
            return None
        text = self.render_echo(objects)
        self.echo_path().write_text(text)
        hashes = self.declaration_hashes()
        return self.store.create_hold(
            {
                "run_id": None,
                "step_id": None,
                "kind": "confirm",
                "reason": "init echo-back awaits the owner's acceptance",
                "waits_on_role": "owner",
                "bound_input_digest": hashing.prefixed(self.declaration_digest()),
                "context_json": {"echo_path": str(self.echo_path()), "hashes": hashes},
            }
        )

    def confirm_status(self) -> str:
        """`accepted`, `rejected`, or `pending` for the current declarations. Reopens the
        hold (regenerating the echo-back) when the declarations changed since the last one."""
        self.ensure_confirm_hold()
        h = self.confirm_hold()
        assert h is not None
        if h["resolved_by_review"] is None:
            return "pending"
        verdict = self.store.scalar(
            "SELECT verdict FROM reviews WHERE review_id = ?", (h["resolved_by_review"],)
        )
        return "accepted" if verdict in ("accept", "override") else "rejected"


# -- init ---------------------------------------------------------------------------


def _parse_method(spec: str) -> tuple[str, str]:
    url, sep, tag = spec.rpartition("@")
    if not sep or not url or not tag or "/" in tag:
        raise ConfigError(f"--method must be <git-url>@<tag>: {spec}")
    return url, tag


def init_project(req: InitRequest) -> Project:
    """Bind a project (design 2.7). Writes: projects, predicate_results (run_id 'init'),
    holds (confirm), echo.md, stringency.yml, and the layout in 2.1."""
    root = req.path.resolve()
    existed = root.exists()
    if existed and any(root.iterdir()):
        raise ConfigError(f"refusing to init: {root} is not empty")
    if req.mode == "open" and req.profile == "strict":
        raise ConfigError("mode open with profile strict is refused")
    if req.mode != "pipeline":
        raise ConfigError(f"mode {req.mode} is reserved; v1 accepts only pipeline")
    root.mkdir(parents=True, exist_ok=True)
    try:
        return _init_in(root, req)
    except BaseException:
        if not existed:
            shutil.rmtree(root, ignore_errors=True)
        else:
            for child in root.iterdir():
                shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
        raise


def _init_in(root: Path, req: InitRequest) -> Project:
    from stringency.git import clone_at
    from stringency.lint import lint_path

    _ensure_engine_predicates()
    for d in ("prov/justifications", "runs", "deliver", "controls", ".stringency"):
        (root / d).mkdir(parents=True, exist_ok=True)

    url, tag = _parse_method(req.method)
    sha = clone_at(url, tag, root / "method")

    pipeline = load_pipeline(find_pipeline(root / "method", req.pipeline))
    plugin = require_plugin(pipeline.domain)
    if req.mode not in plugin.modes:
        raise ConfigError(f"plugin {plugin.name} does not support mode {req.mode}")

    # declarations: validate, then copy in
    inputs = load_model(InputsManifest, req.inputs)
    design_raw = load_yaml(req.design)
    design = load_model(Design, req.design)
    objective = load_model(Objective, req.objective)
    problems = validate(design_raw, plugin.design_schema)
    if problems:
        raise ConfigError("design.yml fails the plugin schema: " + "; ".join(problems))
    if objective.question not in plugin.objective_questions:
        raise ConfigError(
            f"objective question {objective.question} is not in the plugin vocabulary "
            f"{list(plugin.objective_questions)}"
        )
    for name, src in (
        ("design.yml", req.design),
        ("objective.yml", req.objective),
        ("inputs.yml", req.inputs),
    ):
        shutil.copyfile(src, root / name)

    # inputs: every hash matches
    for item in inputs.items:
        p = Path(item.path)
        if not p.exists():
            raise ConfigError(f"input {item.name}: {p} does not exist")
        actual = hashing.hash_file(p)
        if actual != item.blake3:
            raise ConfigError(
                f"input {item.name}: hash mismatch (recorded {item.blake3[:12]}, actual {actual[:12]})"
            )
        if item.type not in plugin.object_types and item.type not in {
            "json",
            "table",
            "tsv",
            "csv",
            "text",
        }:
            raise ConfigError(
                f"input {item.name}: type {item.type} is unknown to plugin {plugin.name}"
            )

    # modules resolve and admit the mode
    modules = ModuleIndex(root / "method")
    for step in pipeline.steps:
        m = modules.require(step.module)
        if req.mode not in m.manifest.modes:
            raise ConfigError(f"module {m.ref} does not admit mode {req.mode}")
        if m.manifest.domain != pipeline.domain:
            raise ConfigError(
                f"module {m.ref} belongs to domain {m.manifest.domain}, pipeline is {pipeline.domain}"
            )

    report = lint_path(root / "method")
    if not report.ok:
        raise ConfigError("lint failed:\n" + report.render())

    policy_path = root / "method" / "policy.yml"
    if not policy_path.exists():
        raise ConfigError("method repo has no policy.yml")
    load_policy(policy_path)

    owner = req.owner or getpass.getuser()
    reviewer = req.reviewer or owner
    project_id = new_id()
    cfg = StringencyConfig(
        project_id=project_id,
        created=now_iso(),
        stringency_version=__version__,
        method=MethodRef(repo=url, tag=tag, sha=sha),
        pipeline=req.pipeline,
        mode=req.mode,
        profile=req.profile,
        roles=Roles(owner=owner, reviewer=reviewer),
        judgment_harness=req.judgment_harness,
        execution=req.execution,
        executor=req.executor,
    )
    dump_yaml(cfg.model_dump(mode="json"), root / "stringency.yml")

    project = Project(root)
    # extractor pass on every object input, so init.column_missing can read the columns
    objects = project.extract_inputs(project.executor(), project.scratch / "init-extract")
    (project.scratch / "init-extract.json").write_text(
        json.dumps({k: v.summary for k, v in objects.items()}, sort_keys=True)
    )
    gate = project.run_init_predicates(objects, record=False)
    if gate.blocked:
        raise ConfigError("init refused:\n" + "\n".join("  " + r.line() for r in gate.blocked))

    store = project.store
    store.insert(
        "projects",
        {
            "project_id": project_id,
            "path": str(root),
            "pipeline_name": pipeline.name,
            "pipeline_version": pipeline.version,
            "pipeline_digest": hashing.hash_file(find_pipeline(root / "method", req.pipeline)),
            "method_repo": url,
            "method_tag": tag,
            "mode": req.mode,
            "profile": req.profile,
            "owner": owner,
            "reviewer": reviewer,
            "judgment_harness": req.judgment_harness,
            "executor": req.executor,
            "objective_json": objective.model_dump(),
            "design_json": design.model_dump(),
            "splits_json": None,
            "created": cfg.created,
            "stringency_version": __version__,
        },
    )
    project.run_init_predicates(objects, record=True)
    project.ensure_confirm_hold(objects)
    return project
