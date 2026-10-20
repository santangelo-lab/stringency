"""Project: layout, binding at init, loading a bound project (design 2).

`init_project` writes the layout, clones the method repo at its tag, verifies inputs, runs
lint and the `init.*` predicates, writes `stringency.yml`, opens the trace, and opens the
project-level `confirm` hold bound to the declaration hashes and the `egress` hold bound to the
data egress fingerprint (backlog L1). `Project.load` reads it back.
"""

from __future__ import annotations

import contextlib
import fnmatch
import getpass
import json
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
    EgressSetting,
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
from stringency.echo import render_echo, render_inherited_echo, render_open_echo
from stringency.egress import EgressAssessment, assess
from stringency.egress import render_markdown as render_egress_markdown
from stringency.executor.base import Executor
from stringency.executor.local import LocalExecutor
from stringency.exit_codes import ConfigError
from stringency.extract import extract_object
from stringency.gate import GateResult, evaluate
from stringency.ids import new_id
from stringency.modules import Module, ModuleIndex
from stringency.operator_id import operator_env
from stringency.pipelines import (
    Pipeline,
    StepDecl,
    find_pipeline,
    load_pipeline,
    open_pipeline,
)
from stringency.plugins import Plugin, installed_plugin_versions, require_plugin
from stringency.policy import Policy, load_policy
from stringency.predicates import registry
from stringency.predicates.context import GateContext, ProjectConfig
from stringency.schemas import validate
from stringency.state import ObjectState, State
from stringency.versions import check_requires

DECLARATIONS = ("design.yml", "objective.yml", "inputs.yml")


def _ensure_engine_predicates() -> None:
    import stringency.predicates.engine  # noqa: F401  (registers engine predicates)


@dataclass
class InitRequest:
    path: Path
    method: str  # <url>@<tag>
    pipeline: str | None  # None in open mode
    objective: Path | None
    design: Path | None
    inputs: Path | None
    mode: str = "pipeline"
    profile: str = "standard"
    owner: str | None = None
    reviewer: str | None = None
    judgment_harness: str = "subagent"
    execution: str = "operator"
    executor: str = "apptainer"
    egress_max: int | None = None  # the person's ceiling, 0 none to 4 data (backlog L1)
    operator_model: str = "hosted"  # hosted | local | none: the operating agent's model
    drafted_by: str = "person"  # person | agent (design 2.7)
    brief: Path | None = None  # the person's own words, kept beside the declarations
    check_only: bool = False  # `declare --check`: every init check, no project record
    # open mode (open_mode_plan.md 2.1): derive the declarations from a delivery directory
    from_delivery: Path | None = None
    upstream: Path | None = None  # the upstream project root; default: derived from the directory


@dataclass
class DeclarationCheck:
    """What `declare --check` returns: the echo-back and what was verified."""

    echo: str
    hashes: dict[str, str]
    inputs: dict[str, str]
    predicates: list[dict[str, Any]]
    method_sha: str
    egress: dict[str, Any] | None = None  # the assessment init would save (backlog L1)
    egress_report: str | None = None

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
        self.modules = ModuleIndex(self.method_root)
        _ensure_engine_predicates()
        # open mode (open_mode_plan.md 2.1): no declared topology; the tools are the method's
        # modules listing `open`, and the run's topology grows one on-demand step at a time
        self.open_ended: bool = self.config.pipeline is None
        self.pipeline: Pipeline
        if self.open_ended:
            self.pipeline = open_pipeline(
                self.config.domain or "",
                self.config.method.tag,
                require_plugin(self.config.domain or "").objective_questions,
            )
        else:
            assert self.config.pipeline is not None
            self.pipeline = load_pipeline(find_pipeline(self.method_root, self.config.pipeline))
        self.plugin: Plugin = require_plugin(self.pipeline.domain)
        self.policy: Policy = load_policy(self.root / self.config.policy)
        self._store: Store | None = None

    # -- tools (open mode) -----------------------------------------------------------

    def tools(self) -> list[Module]:
        """The method's modules that list `open` in their `modes`: what an open project may
        run on demand (open_mode_plan.md 1). Empty on a pipeline project whose method ships
        none. Reads the module index only."""
        return open_tools(self.modules)

    def tool(self, name: str) -> Module:
        """The tool named `name` (a module name), or a ConfigError naming the tools there are."""
        for m in self.tools():
            if m.manifest.name == name:
                return m
        have = ", ".join(m.manifest.name for m in self.tools()) or "none"
        raise ConfigError(f"no tool named {name} in this method; tools: {have}")

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
        module's image is the one that can read the object; else the first env in the pipeline.
        An open project has no steps: the first tool whose input type matches, else the first
        tool's env."""
        if self.open_ended:
            item = self.inputs.by_name().get(name)
            for tool in self.tools():
                if item is not None and any(
                    spec.type == item.type for spec in tool.manifest.inputs.values()
                ):
                    return tool.manifest.env
            names = self.env_names()
            return names[0] if names else "default"
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
        if self.open_ended:
            for tool in self.tools():
                if tool.manifest.env not in names:
                    names.append(tool.manifest.env)
            return names
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
        """The static facts a gate reads; a run context passes its own `pipeline` and `modules`
        when the topology has grown on demand (open mode)."""
        fields: dict[str, Any] = {
            "config": self.config,
            "pipeline": self.pipeline,
            "modules": self.manifests(),
            "inputs": self.inputs,
            "plugin_modes": tuple(self.plugin.modes),
            "vocabularies": self.plugin.vocabularies,
            "object_types": tuple(self.plugin.object_types),
        }
        fields.update(runtime)
        return ProjectConfig(**fields)

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
            project=self.project_config(egress=self.egress_assessment()),
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
        if self.open_ended:
            # the switch paragraph and the bound delivery (open_mode_plan.md 1, decision 4)
            return render_open_echo(
                self.objective, self.inputs, self.declaration_hashes(), self.tools()
            )
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
        `design.yml` and `prov/run.db` (runs, holds, reviews). Never for an open project: the
        switch to questions is one relayed yes on the pinned paragraph (owner, 2026-10-16)."""
        if self.config.mode == "open":
            return None
        if not self.inputs.items:
            return None
        if self.objective.params:
            return None  # a declared parameter is a decision this owner must see (2026-10-14)
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

    # -- data egress and the egress hold (backlog L1) -----------------------------------

    def egress_steps(self) -> list[StepDecl]:
        """The steps the assessment reads: the pipeline's, or in open mode one per tool."""
        if self.open_ended:
            return [
                StepDecl(id=t.manifest.name, module=t.ref, title="a tool, run when called")
                for t in self.tools()
            ]
        return list(self.pipeline.steps)

    def egress_assessment(self) -> EgressAssessment:
        """What this setup sends off the machine (egress.assess). Reads: stringency.yml, the
        module manifests and scripts, and holds (the ceiling on the last acknowledged report,
        shown beside the current one). Writes nothing. Not cached: a control project copies
        this object's attributes and binds another pipeline."""
        e = self.config.egress
        return assess(
            steps=self.egress_steps(),
            modules={m.ref: m for m in self.modules.all()},
            harness=self.config.judgment_harness,
            execution=self.config.execution,
            max_class=e.max_class,
            operator=e.operator,
            previous_max_class=self._acknowledged_egress_ceiling(),
        )

    def _acknowledged_egress_ceiling(self) -> int | None:
        """Reads: holds, reviews. The ceiling recorded on the last accepted egress hold."""
        row = self.store.one(
            "SELECT h.context_json FROM holds h JOIN reviews r "
            "ON r.review_id = h.resolved_by_review WHERE h.kind = 'egress' AND h.run_id IS NULL "
            "AND r.verdict IN ('accept', 'override') ORDER BY h.created DESC, h.rowid DESC LIMIT 1"
        )
        if row is None or not row["context_json"]:
            return None
        ctx = row["context_json"]
        ctx = json.loads(ctx) if isinstance(ctx, str) else ctx
        v = ctx.get("max_class") if isinstance(ctx, dict) else None
        return int(v) if isinstance(v, int) else None

    def egress_report_path(self, a: EgressAssessment) -> Path:
        return self.root / "prov" / f"egress-{a.fingerprint[:12]}.md"

    def write_egress_report(self, a: EgressAssessment) -> Path:
        """Writes `prov/egress-<fp12>.md` and `.json` (the record for this profile) and
        `prov/egress.md` and `.json` (the current one). Returns the fingerprinted report."""
        prov = self.root / "prov"
        prov.mkdir(parents=True, exist_ok=True)
        text = render_egress_markdown(a, project_id=self.config.project_id, assessed_at=now_iso())
        body = json.dumps(a.to_json(), indent=2, sort_keys=True) + "\n"
        path = self.egress_report_path(a)
        for target in (path, prov / "egress.md"):
            target.write_text(text)
            target.with_suffix(".json").write_text(body)
        return path

    def egress_hold(self, a: EgressAssessment | None = None) -> Any:
        """Reads: holds. The egress hold bound to the current fingerprint, or None."""
        a = a or self.egress_assessment()
        return self.store.one(
            "SELECT * FROM holds WHERE kind = 'egress' AND run_id IS NULL AND step_id IS NULL "
            "AND bound_input_digest = ? ORDER BY created DESC, rowid DESC LIMIT 1",
            (hashing.prefixed(a.fingerprint),),
        )

    def ensure_egress_hold(self, a: EgressAssessment | None = None) -> str | None:
        """Open the egress hold for the current fingerprint if none exists (backlog L1).

        Writes: the report files (`write_egress_report`) and one `holds` row (kind `egress`,
        run_id NULL, waits on the owner, bound to the fingerprint). Never inherited from an
        upstream project. Opens nothing when the setup exceeds the ceiling: that is a block
        (`init.egress_exceeds_ceiling`, `prov.egress_exceeds_ceiling`), not a question.
        Returns the new hold_id, or None."""
        a = a or self.egress_assessment()
        if a.within is False or self.egress_hold(a) is not None:
            return None
        path = self.write_egress_report(a)
        return self.store.create_hold(
            {
                "run_id": None,
                "step_id": None,
                "kind": "egress",
                "reason": "the data egress report awaits the owner's acknowledgement",
                "waits_on_role": "owner",
                "bound_input_digest": hashing.prefixed(a.fingerprint),
                "context_json": {
                    "report_path": str(path),
                    "report_json": str(path.with_suffix(".json")),
                    "assessed_class": a.assessed_class,
                    "max_class": a.max_class,
                    "previous_max_class": a.previous_max_class,
                    "within": a.within,
                    "operator": a.operator,
                    "summary": a.summary_line(),
                },
            }
        )

    def egress_status(self, a: EgressAssessment | None = None) -> str:
        """`accepted`, `rejected`, `pending`, or `exceeds` for the current fingerprint. Opens
        the hold (and writes the report) when the profile changed since the last one."""
        a = a or self.egress_assessment()
        if a.within is False:
            self.write_egress_report(a)
            return "exceeds"
        self.ensure_egress_hold(a)
        h = self.egress_hold(a)
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
    holds (confirm, egress), echo.md, prov/egress*.md and .json, stringency.yml, and the layout
    in 2.1."""
    root = req.path.resolve()
    existed = root.exists()
    if existed and any(root.iterdir()):
        raise ConfigError(f"refusing to init: {root} is not empty")
    if req.mode == "open" and req.profile == "strict":
        raise ConfigError("mode open with profile strict is refused")
    if req.mode == "open" and req.pipeline is not None:
        raise ConfigError(
            "mode open binds no pipeline: its tools are the method's modules that list open; "
            "drop --pipeline"
        )
    if req.mode == "pipeline" and req.pipeline is None:
        raise ConfigError("--pipeline is required in pipeline mode")
    if req.mode not in ("pipeline", "open"):
        raise ConfigError(f"mode {req.mode} is reserved")
    if req.from_delivery is not None and req.mode != "open":
        raise ConfigError(
            "--from-delivery derives an open project's declarations; it needs --mode open"
        )
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
        egress = project.egress_assessment()
        return DeclarationCheck(
            echo=project.render_echo(objects),
            hashes=project.declaration_hashes(),
            inputs={i.name: i.blake3 for i in project.inputs.items},
            predicates=[
                {"predicate_id": r.spec.id, "fired": r.verdict.fired, "reason": r.verdict.reason}
                for r in gate.records
            ],
            method_sha=project.config.method.sha,
            egress=egress.to_json(),
            egress_report=render_egress_markdown(
                egress, project_id="(not yet bound)", assessed_at=now_iso()
            ),
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


def _verify_upstream_input(item: InputItem) -> None:
    """An upstream pipeline's input bound in an open project must be one that project declared,
    with the same hash (2026-10-19). Reads the upstream's `inputs.yml`."""
    u = item.upstream_input
    assert u is not None
    path = Path(u.project) / "inputs.yml"
    if not path.exists():
        raise ConfigError(
            f"input {item.name}: upstream_input names {u.project}, which has no inputs.yml"
        )
    declared = load_model(InputsManifest, path).by_name().get(u.input)
    if declared is None:
        raise ConfigError(
            f"input {item.name}: the upstream {u.project} declares no input {u.input}"
        )
    if declared.blake3 != item.blake3:
        raise ConfigError(
            f"input {item.name}: hash {item.blake3[:12]} differs from the upstream's "
            f"{declared.blake3[:12]} for {u.input}"
        )


def open_tools(modules: ModuleIndex) -> list[Module]:
    """Every module of the index that lists `open` in its `modes`, in index order."""
    return [m for m in modules.all() if "open" in m.manifest.modes]


def upstream_of_delivery(delivery_dir: Path, upstream: Path | None) -> Path:
    """The upstream project root: `--upstream` when given, else the delivery directory's
    grandparent when it holds `stringency.yml` (`<project>/deliver/<run>/`)."""
    if upstream is not None:
        root = Path(upstream).resolve()
        if not (root / "stringency.yml").exists():
            raise ConfigError(f"--upstream {root} is not a stringency project (no stringency.yml)")
        return root
    cand = delivery_dir.resolve().parent.parent
    if (cand / "stringency.yml").exists():
        return cand
    raise ConfigError(
        f"cannot tell which project delivered {delivery_dir}: pass --upstream <project root>"
    )


def declarations_from_delivery(
    delivery_dir: Path, upstream: Path | None, *, into: Path
) -> dict[str, Path]:
    """Write the three declaration files of an open project from a delivery (open_mode_plan.md
    2.1, 2026-10-16): `inputs.yml` with one item per delivered file (`name` the output name, the
    step id prefixed on a clash; `type` the recorded kind, `prose` read as `text`; `derived_from`
    the run, step, output and upstream project), then one item per input the upstream declared
    (`upstream_<name>`, its `upstream_input` naming it), `design.yml` byte for byte from the upstream,
    `objective.yml` from the upstream's with `id` suffixed `-open`, no deliverables and no params.
    Reads `<dir>/index.json` and the upstream's `inputs.yml`, `design.yml` and `objective.yml`; writes the
    three files under `into` and returns them by key (`objective`, `design`, `inputs`)."""
    delivery_dir = Path(delivery_dir).resolve()
    index_path = delivery_dir / "index.json"
    if not index_path.exists():
        raise ConfigError(f"{delivery_dir} is not a delivery directory (no index.json)")
    try:
        index = json.loads(index_path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"{index_path}: not JSON ({e})") from None
    if not isinstance(index, dict) or not isinstance(index.get("files"), list):
        raise ConfigError(f"{index_path}: expected an object with a files list")
    root = upstream_of_delivery(delivery_dir, upstream)
    run_id = str(index.get("run_id") or "")
    if not run_id:
        raise ConfigError(f"{index_path} names no run_id")
    names: dict[str, int] = {}
    for f in index["files"]:
        names[str(f.get("output"))] = names.get(str(f.get("output")), 0) + 1
    items: list[dict[str, Any]] = []
    for f in index["files"]:
        output, step_id = str(f.get("output")), str(f.get("step_id"))
        name = output if names.get(output, 0) == 1 else f"{step_id}_{output}"
        kind = str(f.get("kind") or "text")
        path = delivery_dir / str(f.get("file"))
        if not path.exists():
            raise ConfigError(f"delivered file {path} is missing")
        # the run that produced the file: a resumed or forked run delivers steps an earlier run
        # completed, and the file's sidecar names that run (2026-10-20, the Lyons liver delivery)
        produced_by = run_id
        sc = delivery_dir / str(f.get("sidecar") or f"{f.get('file')}.stringency.json")
        if sc.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                produced_by = str(json.loads(sc.read_text()).get("run_id") or run_id)
        items.append(
            {
                "name": name,
                "path": str(path),
                "type": "text" if kind == "prose" else kind,
                "blake3": str(f.get("blake3") or hashing.hash_path(path)),
                "source": f"delivered by run {run_id} of {root}",
                "derived_from": {
                    "run_id": produced_by,
                    "step_id": step_id,
                    "output": output,
                    "project": str(root),
                },
            }
        )
    if not items:
        raise ConfigError(f"{index_path} lists no files; nothing to ask questions of")
    # the upstream pipeline's own inputs, read-only beside the delivery (2026-10-19): a question
    # about what the pipeline removed or changed needs the data from before it ran
    taken = {str(i["name"]) for i in items}
    up_inputs = load_model(InputsManifest, root / "inputs.yml")
    for u in up_inputs.items:
        name = f"upstream_{u.name}"
        if name in taken:
            continue
        entry: dict[str, Any] = {
            **u.model_dump(exclude_none=True),
            "name": name,
            "source": f"input {u.name} of the upstream pipeline {root}, before it ran",
            "upstream_input": {"project": str(root), "input": u.name},
        }
        items.append(entry)
    up_objective = load_yaml(root / "objective.yml")
    if not isinstance(up_objective, dict):
        raise ConfigError(f"{root / 'objective.yml'}: expected a mapping")
    objective = {
        **up_objective,
        "id": f"{up_objective.get('id', 'project')}-open",
        "deliverables": [],
        "params": {},
    }
    into.mkdir(parents=True, exist_ok=True)
    out = {
        "inputs": into / "inputs.yml",
        "design": into / "design.yml",
        "objective": into / "objective.yml",
    }
    dump_yaml({"inputs": 1, "items": items}, out["inputs"])
    shutil.copyfile(root / "design.yml", out["design"])
    dump_yaml(objective, out["objective"])
    return out


def _init_in(root: Path, req: InitRequest) -> tuple[Project, dict[str, ObjectState], GateResult]:
    """Returns the project, the init extractor states, and the init gate result."""
    from stringency.git import clone_at
    from stringency.lint import lint_path

    _ensure_engine_predicates()
    for d in ("prov/justifications", "runs", "deliver", "controls", ".stringency"):
        (root / d).mkdir(parents=True, exist_ok=True)

    url, tag = _parse_method(req.method)
    sha = clone_at(url, tag, root / "method")

    modules = ModuleIndex(root / "method")
    tools: list[Module] = []
    if req.mode == "open":
        # the tools are the modules listing `open`; the domain is theirs (open_mode_plan.md 2.1)
        tools = open_tools(modules)
        if not tools:
            raise ConfigError(
                f"method {url}@{tag} ships no module that lists open in its modes; "
                "an open project has nothing to run"
            )
        domains = sorted({m.manifest.domain for m in tools})
        if len(domains) != 1:
            raise ConfigError(f"the tools belong to more than one domain: {', '.join(domains)}")
        plugin = require_plugin(domains[0])
        pipeline = open_pipeline(domains[0], tag, plugin.objective_questions)
        pipeline_digest = hashing.hash_json(sorted(m.ref for m in tools))
    else:
        assert req.pipeline is not None
        pipeline_path = find_pipeline(root / "method", req.pipeline)
        pipeline = load_pipeline(pipeline_path)
        plugin = require_plugin(pipeline.domain)
        pipeline_digest = hashing.hash_file(pipeline_path)
    if req.mode not in plugin.modes:
        raise ConfigError(f"plugin {plugin.name} does not support mode {req.mode}")

    # the declaration files: given, or derived from a delivery (open mode)
    files: dict[str, Path | None] = {
        "objective": req.objective,
        "design": req.design,
        "inputs": req.inputs,
    }
    if req.from_delivery is not None:
        derived = declarations_from_delivery(
            Path(req.from_delivery), req.upstream, into=root / ".stringency" / "from-delivery"
        )
        for key, derived_path in derived.items():
            if files[key] is None:
                files[key] = derived_path
    for key, given in files.items():
        if given is None:
            raise ConfigError(f"--{key} is required (or --from-delivery <dir> in open mode)")
    req_objective, req_design, req_inputs = files["objective"], files["design"], files["inputs"]
    assert req_objective is not None and req_design is not None and req_inputs is not None

    # declarations: validate, then copy in
    inputs = load_model(InputsManifest, req_inputs)
    design_raw = load_yaml(req_design)
    design = load_model(Design, req_design)
    objective = load_model(Objective, req_objective)
    problems = validate(design_raw, plugin.design_schema)
    if problems:
        raise ConfigError("design.yml fails the plugin schema: " + "; ".join(problems))
    if objective.question not in plugin.objective_questions:
        raise ConfigError(
            f"objective question {objective.question} is not in the plugin vocabulary "
            f"{list(plugin.objective_questions)}"
        )
    if req.mode == "open" and objective.params:
        raise ConfigError(
            "an open objective declares no params: a tool's parameters are settled per question"
        )
    if req.mode == "open" and objective.deliverables:
        raise ConfigError(
            "an open objective declares no deliverables: the person chooses which answers to "
            "deliver at the end"
        )
    for name, src in (
        ("design.yml", req_design),
        ("objective.yml", req_objective),
        ("inputs.yml", req_inputs),
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
        # a delivered artifact's kind was recorded by the engine that produced it; a declared
        # raw input's type must be one the plugin or the engine can read
        if (
            item.derived_from is None
            and item.type not in plugin.object_types
            and item.type not in {"json", "table", "tsv", "csv", "text"}
        ):
            raise ConfigError(
                f"input {item.name}: type {item.type} is unknown to plugin {plugin.name}"
            )
        if item.derived_from is not None:
            _verify_derived_from(item)
        if item.upstream_input is not None:
            _verify_upstream_input(item)

    # modules resolve and admit the mode (the pipeline's steps, or in open mode the tools)
    if req.mode == "open":
        for m in tools:
            if m.manifest.domain != pipeline.domain:
                raise ConfigError(
                    f"tool {m.ref} belongs to domain {m.manifest.domain}, not {pipeline.domain}"
                )
    for step in pipeline.steps:
        m = modules.require(step.module)
        if req.mode not in m.manifest.modes:
            raise ConfigError(f"module {m.ref} does not admit mode {req.mode}")
        if m.manifest.domain != pipeline.domain:
            raise ConfigError(
                f"module {m.ref} belongs to domain {m.manifest.domain}, pipeline is {pipeline.domain}"
            )

    # declared parameters (design 2.5): every step and parameter must exist; the value itself is
    # gated when the step runs (param.out_of_range, param.locked_changed)
    for sid, values in objective.params.items():
        if not pipeline.has_step(sid):
            raise ConfigError(f"objective params: no step {sid} in pipeline {pipeline.name}")
        if not isinstance(values, dict):
            raise ConfigError(
                f"objective params for {sid}: expected a mapping of parameter to value"
            )
        step_decl = pipeline.step(sid)
        declared = set(step_decl.params) | set(modules.require(step_decl.module).declared_params)
        for name in values:
            if name not in declared:
                raise ConfigError(f"objective params: step {sid} declares no parameter {name}")

    report = lint_path(root / "method")
    if not report.ok:
        raise ConfigError("lint failed:\n" + report.render())

    policy_path = root / "method" / "policy.yml"
    if not policy_path.exists():
        raise ConfigError("method repo has no policy.yml")
    method_policy = load_policy(policy_path)
    if method_policy.requires is not None:
        problems = check_requires(method_policy.requires, __version__, installed_plugin_versions())
        if problems:
            raise ConfigError("the method's policy requires: " + "; ".join(problems))

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
        harness=operator_env()["harness"] if req.drafted_by == "agent" else None,
        session_ref=operator_env()["session_ref"] if req.drafted_by == "agent" else None,
        brief=brief_name,
    )
    cfg = StringencyConfig(
        project_id=project_id,
        created=now_iso(),
        stringency_version=__version__,
        method=MethodRef(repo=url, tag=tag, sha=sha),
        pipeline=req.pipeline,
        mode=req.mode,
        domain=pipeline.domain if req.mode == "open" else None,
        profile=req.profile,
        roles=Roles(owner=owner, reviewer=reviewer),
        judgment_harness=req.judgment_harness,
        execution=req.execution,
        executor=req.executor,
        declarations=declarations,
        plugins=installed_plugin_versions(),
        egress=_egress_setting(req),
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
            "pipeline_digest": pipeline_digest,
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
    project.ensure_egress_hold()
    return project, objects, gate


def _egress_setting(req: InitRequest) -> EgressSetting:
    if req.egress_max is not None and not 0 <= req.egress_max <= 4:
        raise ConfigError("--egress-max must be a class from 0 (none) to 4 (data)")
    if req.operator_model not in ("hosted", "local", "none"):
        raise ConfigError("--operator-model must be hosted, local or none")
    return EgressSetting(max_class=req.egress_max, operator=req.operator_model)
