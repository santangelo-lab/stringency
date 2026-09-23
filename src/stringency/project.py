"""Project: layout, binding at init, loading a bound project (design 2).

`init_project` writes the layout, clones the method repo at its tag, verifies inputs, runs
lint and the `init.*` predicates, writes `stringency.yml`, opens the trace, and opens the
project-level `confirm` hold bound to the declaration hashes. `Project.load` reads it back.
"""

from __future__ import annotations

import fnmatch
import getpass
import json
import os
import re
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from stringency import __version__, hashing
from stringency.actions import Action
from stringency.clock import now_iso
from stringency.config import (
    Declarations,
    Design,
    InputItem,
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
from stringency.echo import render_echo, render_inherited_echo
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
    drafted_by: str = "person"  # person | agent (design 2.7)
    brief: Path | None = None  # the person's own words, kept beside the declarations
    check_only: bool = False  # `declare --check`: every init check, no project record


@dataclass
class DeclarationCheck:
    """What `declare --check` returns: the echo-back and what was verified."""

    echo: str
    hashes: dict[str, str]
    inputs: dict[str, str]
    predicates: list[dict[str, Any]]
    method_sha: str

    def to_json(self) -> dict[str, Any]:
        return {"schema": "stringency.declare/1", **self.__dict__}


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

    def env_for_input(self, name: str) -> str:
        """The environment the init extractor runs in for input `name` (Lane A item 5,
        2026-09-23): the env of the first pipeline step that binds `$inputs.<name>`, since that
        module's image is the one that can read the object; else the first env in the pipeline."""
        for step in self.pipeline.steps:
            for rs in step.refs().values():
                for r in rs:
                    if r.kind != "inputs":
                        continue
                    hit = fnmatch.fnmatchcase(name, r.name) if r.pattern else r.name == name
                    if hit:
                        m = self.modules.get(step.module)
                        if m is not None:
                            return m.manifest.env
        names = self.env_names()
        return names[0] if names else "default"

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
            out[item.name] = hashing.hash_path(p) if p.exists() else "missing"
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
        for item in self.inputs.items:
            if item.type not in self.plugin.object_types:
                continue
            ext = extract_object(
                self.plugin,
                executor,
                object_type=item.type,
                object_path=Path(item.path),
                design=self.design.model_dump(),
                env_name=self.env_for_input(item.name),
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
        inherited = self.inherited_confirmation()
        if inherited is not None:
            return render_inherited_echo(
                self.objective,
                self.inputs,
                self.declaration_hashes(),
                inherited,
                f"{self.pipeline.name} {self.pipeline.version}",
            )
        counts = {k: v.summary for k, v in (objects or {}).items()}
        if not counts:
            cached = self.scratch / "init-extract.json"
            if cached.exists():
                counts = json.loads(cached.read_text())
        return render_echo(
            self.plugin, self.design, self.objective, self.inputs, counts, self.declaration_hashes()
        )

    @staticmethod
    def _major(tag: str) -> str | None:
        m = re.match(r"v?(\d+)\.", tag)
        return m.group(1) if m else None

    def inherited_confirmation(self) -> dict[str, Any] | None:
        """Design 2.7 (added 2026-09-23): when every input is `derived_from` a run of a project
        this owner confirmed, whose `design.yml` is byte-identical and whose method has the same
        major version, the confirmation is inherited. Returns the upstream holds and acceptances
        (`upstreams`: project, run_id, hold_id, review_id, reviewer, ts), or None when any input
        is raw, any upstream is unconfirmed, differently owned, differently designed, or on
        another method major version. Reads, read-only: each upstream's `stringency.yml`,
        `design.yml` and `prov/run.db` (runs, holds, reviews)."""
        if not self.inputs.items:
            return None
        my_design = hashing.hash_file(self.root / "design.yml")
        my_major = self._major(self.config.method.tag)
        upstreams: list[dict[str, Any]] = []
        seen: dict[str, dict[str, Any]] = {}
        for item in self.inputs.items:
            d = item.derived_from
            if d is None or not d.project:
                return None
            root = Path(d.project)
            if d.project in seen:
                continue
            cfg_path, design_path, db_path = (
                root / "stringency.yml",
                root / "design.yml",
                root / "prov" / "run.db",
            )
            if not (cfg_path.exists() and design_path.exists() and db_path.exists()):
                return None
            try:
                cfg = load_model(StringencyConfig, cfg_path)
            except Exception:  # noqa: BLE001  (an unreadable upstream is simply not inheritable)
                return None
            if cfg.roles.owner != self.config.roles.owner:
                return None
            if hashing.hash_file(design_path) != my_design:
                return None
            if my_major is None or self._major(cfg.method.tag) != my_major:
                return None
            with Store.open(db_path, create=False) as up:
                if up.one("SELECT 1 FROM runs WHERE run_id = ?", (d.run_id,)) is None:
                    return None
                row = up.one(
                    "SELECT h.hold_id, r.review_id, r.reviewer, r.ts, r.verdict FROM holds h "
                    "JOIN reviews r ON r.review_id = h.resolved_by_review "
                    "WHERE h.kind = 'confirm' AND h.run_id IS NULL "
                    "ORDER BY h.created DESC, h.rowid DESC LIMIT 1"
                )
            if row is None or row["verdict"] not in ("accept", "override"):
                return None
            entry = {
                "project": d.project,
                "run_id": d.run_id,
                "hold_id": row["hold_id"],
                "review_id": row["review_id"],
                "reviewer": row["reviewer"],
                "ts": row["ts"],
            }
            seen[d.project] = entry
            upstreams.append(entry)
        return {"upstreams": upstreams, "design_blake3": my_design, "method_major": my_major}

    def confirm_hold(self) -> Any:
        """Reads: holds. The confirm hold bound to the current declaration digest, or None."""
        return self.store.one(
            "SELECT * FROM holds WHERE kind = 'confirm' AND run_id IS NULL AND step_id IS NULL "
            "AND bound_input_digest = ? ORDER BY created DESC, rowid DESC LIMIT 1",
            (hashing.prefixed(self.declaration_digest()),),
        )

    def ensure_confirm_hold(self, objects: dict[str, ObjectState] | None = None) -> str | None:
        """Open the init confirm hold for the current declarations if none exists (design 2.7).

        Reads: holds. Writes: holds (kind `confirm`, waits on the owner) and `echo.md`. When the
        confirmation is inherited (2.7, `inherited_confirmation`), also writes one `reviews` row
        (`via: inherited`, the upstream owner's acceptance by reference) and resolves the hold at
        once, so `run` may open without a new acceptance.
        Returns the new hold_id, or None when a hold for these declarations already exists.
        """
        if self.confirm_hold() is not None:
            return None
        inherited = self.inherited_confirmation()
        text = self.render_echo(objects)
        self.echo_path().write_text(text)
        hashes = self.declaration_hashes()
        context: dict[str, Any] = {"echo_path": str(self.echo_path()), "hashes": hashes}
        decl = self.config.declarations
        if decl is not None:
            context["drafted_by"] = decl.drafted_by
            if decl.brief and (self.root / decl.brief).exists():
                context["brief"] = decl.brief
                context["brief_blake3"] = hashing.hash_file(self.root / decl.brief)
        if inherited is not None:
            context["inherited"] = inherited
        digest = hashing.prefixed(self.declaration_digest())
        hold_id = self.store.create_hold(
            {
                "run_id": None,
                "step_id": None,
                "kind": "confirm",
                "reason": (
                    "init echo-back: confirmation inherited from the upstream project(s)"
                    if inherited is not None
                    else "init echo-back awaits the owner's acceptance"
                ),
                "waits_on_role": "owner",
                "bound_input_digest": digest,
                "context_json": context,
            }
        )
        if inherited is not None:
            ups = inherited["upstreams"]
            review_id = new_id()
            self.store.insert(
                "reviews",
                {
                    "review_id": review_id,
                    "hold_id": hold_id,
                    "reviewer": ups[0]["reviewer"],
                    "host": socket.gethostname(),
                    "via": "inherited",
                    "ts": now_iso(),
                    "verdict": "accept",
                    "reason": "; ".join(
                        f"inherited from {u['project']}: hold {u['hold_id']}, review "
                        f"{u['review_id']} accepted by {u['reviewer']} at {u['ts']}"
                        for u in ups
                    ),
                    "bound_input_digest": digest,
                },
            )
            self.store.resolve_hold(hold_id, review_id, "inherited")
        return hold_id

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
        return _init_in(root, req)[0]
    except BaseException:
        if not existed:
            shutil.rmtree(root, ignore_errors=True)
        else:
            for child in root.iterdir():
                shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
        raise


def check_declarations(req: InitRequest) -> DeclarationCheck:
    """`declare --check` (design 2.7): run every check `init` runs, in a temporary directory
    that is removed afterwards, and return the echo-back. Writes nothing that persists."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="stringency-declare-") as tmp:
        root = Path(tmp) / "check"
        root.mkdir()
        probe = InitRequest(**{**req.__dict__, "path": root, "check_only": True})
        project, objects, gate = _init_in(root, probe)
        return DeclarationCheck(
            echo=project.render_echo(objects),
            hashes=project.declaration_hashes(),
            inputs={i.name: i.blake3 for i in project.inputs.items},
            predicates=[
                {"predicate_id": r.spec.id, "fired": r.verdict.fired, "reason": r.verdict.reason}
                for r in gate.records
            ],
            method_sha=project.config.method.sha,
        )


def _verify_derived_from(item: InputItem) -> None:
    """A chained input must sit beside a stringency sidecar naming the run it came from, with
    the same hash (design 2.3)."""
    from stringency.artifacts import sidecar_path

    d = item.derived_from
    assert d is not None
    sc = sidecar_path(Path(item.path))
    if not sc.exists():
        raise ConfigError(
            f"input {item.name}: derived_from names run {d.run_id} but no sidecar exists at {sc}"
        )
    try:
        meta = json.loads(sc.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"input {item.name}: sidecar {sc} is not JSON: {e}") from None
    if meta.get("run_id") != d.run_id:
        raise ConfigError(
            f"input {item.name}: sidecar names run {meta.get('run_id')}, derived_from says {d.run_id}"
        )
    if meta.get("blake3") != item.blake3:
        raise ConfigError(
            f"input {item.name}: sidecar hash {str(meta.get('blake3'))[:12]} differs from the declared {item.blake3[:12]}"
        )
    if d.step_id is not None and meta.get("step_id") != d.step_id:
        raise ConfigError(
            f"input {item.name}: sidecar step {meta.get('step_id')}, derived_from says {d.step_id}"
        )
    if d.output is not None and meta.get("name") != d.output:
        raise ConfigError(
            f"input {item.name}: sidecar output {meta.get('name')}, derived_from says {d.output}"
        )


def _init_in(root: Path, req: InitRequest) -> tuple[Project, dict[str, ObjectState], GateResult]:
    """Returns the project, the init extractor states, and the init gate result."""
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
        actual = hashing.hash_path(p)
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
        if item.derived_from is not None:
            _verify_derived_from(item)

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
    drafted_by: Literal["person", "agent"]
    if req.drafted_by == "person":
        drafted_by = "person"
    elif req.drafted_by == "agent":
        drafted_by = "agent"
    else:
        raise ConfigError("--drafted-by must be person or agent")
    brief_name = None
    if req.brief is not None:
        if not Path(req.brief).exists():
            raise ConfigError(f"brief {req.brief} does not exist")
        shutil.copyfile(req.brief, root / "brief.md")
        brief_name = "brief.md"
    declarations = Declarations(
        drafted_by=drafted_by,
        harness=os.environ.get("STRINGENCY_OPERATOR") if req.drafted_by == "agent" else None,
        session_ref=os.environ.get("STRINGENCY_SESSION_REF") if req.drafted_by == "agent" else None,
        brief=brief_name,
    )
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
        declarations=declarations,
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
    if req.check_only:
        return project, objects, gate  # `declare --check`: nothing below is written

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
    return project, objects, gate
