"""Lint (design 13). Errors fail; warnings do not.

`lint_path` accepts a module directory or a method repo. A method repo is linted whole:
every module, every pipeline, the policy, and the `open:` blocks of its analyze skill files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from stringency import __version__
from stringency.config import Design
from stringency.controls import load_control
from stringency.egress import module_scripts, scan_module
from stringency.executor.apptainer import resolve_image
from stringency.exit_codes import ConfigError
from stringency.gate import in_scope_specs
from stringency.modules import Module, ModuleIndex, load_module
from stringency.pipelines import Pipeline, load_pipeline
from stringency.plugins import Plugin, load_plugins
from stringency.policy import Policy, load_policy
from stringency.predicates import registry
from stringency.prompting import check_vars
from stringency.resources import host_core_reads, parse_duration_s, parse_memory_gb
from stringency.schemas import includes_base_judgment, schema_is_valid, validate
from stringency.versions import check_requires


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    def render(self) -> str:
        lines = [f"error: {e}" for e in self.errors] + [f"warning: {w}" for w in self.warnings]
        if not lines:
            lines = ["lint: no errors, no warnings"]
        return "\n".join(lines)


def _ensure_predicates() -> None:
    import stringency.predicates.engine  # noqa: F401

    load_plugins()


def lint_module(
    module: Module,
    report: LintReport,
    *,
    plugin: Plugin | None,
    policy: Policy | None,
    design: Design | None = None,
) -> None:
    m = module.manifest
    where = f"module {m.ref}"
    plugins = load_plugins()
    if plugin is None:
        plugin = plugins.get(m.domain)
    if plugin is None:
        report.error(where, f"domain {m.domain} is not a loaded plugin")
    else:
        if m.operation not in plugin.operations:
            report.error(where, f"operation {m.operation} is not in the {plugin.name} vocabulary")
        for mode in m.modes:
            if mode not in plugin.modes:
                report.error(where, f"mode {mode} is not supported by plugin {plugin.name}")
        if m.vocabulary and plugin.vocabulary(m.vocabulary) is None:
            report.error(
                where, f"vocabulary {m.vocabulary} is not provided by plugin {plugin.name}"
            )
        so = m.judgment.sign_off if m.judgment else None
        vocab = plugin.vocabulary(m.vocabulary) if m.vocabulary else None
        if so and so.labels and vocab is not None:
            for label in so.labels:
                if label not in vocab:
                    report.error(
                        where, f"sign_off label {label} is not in vocabulary {m.vocabulary}"
                    )

    for g in m.gates:
        if registry.resolve(g) is None:
            report.error(
                where, f"gates entry {g} does not resolve to a registered predicate id and version"
            )

    # params schema
    pschema = module.params_schema
    bad = schema_is_valid(pschema)
    if bad:
        report.error(where, f"params.schema.json is not a valid schema: {bad}")
    if m.stochastic and m.seed_param and m.seed_param not in module.declared_params:
        report.error(where, f"seed_param {m.seed_param} is missing from params.schema.json")
    if not m.decision_points and len(module.declared_params) > 1:
        report.warn(where, "decision_points is empty for a module with more than one parameter")
    for dp in m.decision_points:
        if dp not in module.declared_params:
            report.error(where, f"decision point {dp} is not a declared parameter")

    # row keys (L138): `key` is read on outputs only; a declared key names its columns once.
    # Whether it is unique is a property of an output, which lint does not have.
    for name, io in m.inputs.items():
        if io.key is not None:
            report.warn(where, f"inputs.{name}.key is read on outputs only")
    for name, io in m.outputs.items():
        if io.key is not None and (not io.key or len(set(io.key)) != len(io.key)):
            report.error(where, f"outputs.{name}.key must name at least one column, each once")

    # scripts
    if m.kind in ("deterministic", "report") and module.entry_script is None:
        report.error(where, "no pre.* script (or entry:) found")
    for label, script in (("entry", module.entry_script), ("post", module.post_script)):
        if script is not None and not script.exists():
            report.error(where, f"{label} script {script.name} is missing")
    # data egress (backlog L1, L46): the scan against the declaration. Scripts that reach the
    # network with no `egress` block, or under a declared class 0, fail; a class above 0 with
    # nothing found is a warning (a library may connect on its own; the scan cannot see that).
    hits = scan_module(module.path)
    decl = m.egress
    if hits:
        found = ", ".join(h.describe() for h in hits[:3]) + (" ..." if len(hits) > 3 else "")
        if decl is None:
            report.error(
                where,
                f"scripts reach the network but the module declares no egress ({found}); "
                "declare `egress: {class, hosts, sends}` in module.yml",
            )
        elif decl.cls == 0:
            report.error(
                where,
                f"scripts reach the network but module.yml declares egress class 0 ({found})",
            )
    elif decl is not None and decl.cls > 0:
        report.warn(
            where,
            f"module.yml declares egress class {decl.cls} but no script matches the network scan; "
            "the declaration stands",
        )

    # the allocation (L130): a script that sizes its workers by the host's core count rather
    # than by the job's `resources` (a text check, `resources.host_core_reads`), and a
    # `resources` value the engine cannot read
    for script in module_scripts(module.path):
        reads = host_core_reads(script)
        if reads:
            lines = ", ".join(str(n) for n, _ in reads)
            report.warn(
                where,
                f"{script.relative_to(module.path)} reads the host's core count (line {lines}) "
                "and not the job's allocation; size workers by job.json `resources.cpus` or "
                "$STRINGENCY_CPUS",
            )
    for key, parse in (("memory", parse_memory_gb), ("timeout", parse_duration_s)):
        try:
            parse(getattr(m.resources, key))
        except ConfigError as e:
            report.warn(where, f"resources.{key}: {e}; the engine allocates none for it")

    # judgment modules
    if m.kind == "judgment":
        if m.judgment is None:
            report.error(where, "kind judgment requires the judgment block")
        if m.prompt is None or not (module.path / m.prompt.template).exists():
            report.error(where, "kind judgment requires prompt.md")
        schema = module.output_schema
        if schema is None:
            report.error(where, "kind judgment requires schema.json")
        else:
            bad = schema_is_valid(schema)
            if bad:
                report.error(where, f"schema.json is not a valid schema: {bad}")
            for p in includes_base_judgment(schema):
                report.error(where, f"schema.json does not include the base judgment schema: {p}")
        if m.judgment is not None:
            if m.judgment.items_from not in m.inputs:
                report.error(where, f"judgment.items_from {m.judgment.items_from} is not an input")
            for ev in m.judgment.evidence:
                # a pre.* script may produce an evidence table that is not an input (design 3.5
                # step 2); without a pre-script every evidence name must be an input
                if ev not in m.inputs and module.entry_script is None:
                    report.error(where, f"judgment.evidence {ev} is not an input")
            for ref in m.judgment.must_cite:
                table, dot, column = ref.partition(".")
                if not dot or not table or not column:
                    report.error(where, f"judgment.must_cite {ref!r} is not <table>.<column>")
                elif table not in m.judgment.evidence:
                    report.error(
                        where,
                        f"judgment.must_cite {ref} names table {table}, not one of judgment.evidence",
                    )
            if policy is not None:
                minimum = policy.profile("standard").replicates_min
                if m.judgment.replicates < minimum:
                    report.error(
                        where,
                        f"replicates {m.judgment.replicates} is below the policy minimum {minimum}",
                    )
        if m.vocabulary is None:
            report.error(where, "kind judgment requires a vocabulary")

    # prompt variables (judgment and report modules with a template)
    if m.prompt is not None:
        text = module.prompt_template
        if text is None:
            report.error(where, f"prompt template {m.prompt.template} is missing")
        else:
            try:
                for p in check_vars(text, m.prompt.vars):
                    report.error(where, p)
            except ConfigError as e:
                report.error(where, str(e))

    # controls
    kinds: dict[str, int] = {}
    for cf in module.control_files():
        try:
            c = load_control(cf)
        except ConfigError as e:
            report.error(where, str(e))
            continue
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
        if design is not None:
            held = {h.blake3 for h in design.holdout}
            if c.fixture.input.blake3 in held:
                report.warn(where, f"control {c.name} fixture matches a design.holdout hash")
    if m.kind == "judgment":
        for need in ("negative", "positive"):
            if need not in kinds:
                report.error(where, f"judgment module lacks a {need} control")
        if "planted" not in kinds:
            report.warn(where, "judgment module has no planted control")
    for need in m.controls.required:
        if need not in kinds:
            report.error(where, f"controls.required names {need} but no such control exists")
    if "open" in m.modes and m.kind == "deterministic" and "positive" not in kinds:
        report.warn(
            where,
            "lists open with no positive control: an answer built on its outputs will be "
            "labelled untested",
        )

    # in-scope predicates not listed
    listed = {g.split("@")[0] for g in m.gates}
    for phase in ("pre", "post"):
        for spec in in_scope_specs(
            registry, phase, operation=m.operation, module=m, runner=m.runner
        ):
            if spec.id not in listed and spec.scope != ("*",):
                report.warn(where, f"in-scope predicate {spec.ref} is not listed in gates")


DECISION_ENGINE = "0.2.29"  # the first engine that knows `decision:` (L61)


def _requires_decision_engine(policy: Policy | None) -> bool:
    """True when the method's `requires.engine` admits no engine older than the one that knows
    the `decision:` block, which is the method opting in to the silent-case error (L61: a
    warning before, an error after)."""
    if policy is None or policy.requires is None or not policy.requires.engine:
        return False
    try:
        from stringency.versions import satisfies

        older = "0.2.28"
        return not satisfies(older, policy.requires.engine)
    except ConfigError:
        return False


def _lint_decisions(
    pipeline: Pipeline, modules: ModuleIndex, report: LintReport, where: str, policy: Policy | None
) -> None:
    """The `decision:` block (design 3.1, backlog L61): a ranged decision point with none is
    the silent case (warning, or error once `requires.engine` names an engine that knows the
    block); the evidence source must be an output of a step upstream or a project input; the
    menu keys must name what exists; the parameter must be one of the module's decision points."""
    strict = _requires_decision_engine(policy)
    order = pipeline.order()
    for step in pipeline.steps:
        mod = modules.get(step.module)
        upstream = order[: order.index(step.id)] if step.id in order else []
        for name, decl in step.params.items():
            at = f"step {step.id} parameter {name}"
            if decl.decision is None:
                if not decl.fixed:
                    msg = (
                        f"{at}: a decision point with no `decision:` block (what evidence a person "
                        "judges the proposal by); declare one, or `evidence: none` with `because:`"
                    )
                    (report.error if strict else report.warn)(where, msg)
                continue
            d = decl.decision
            if decl.fixed:
                report.warn(where, f"{at}: `decision:` on a fixed parameter is never read")
            if (
                mod is not None
                and mod.manifest.decision_points
                and name not in mod.manifest.decision_points
            ):
                report.error(
                    where,
                    f"{at}: `decision:` on a parameter that is not a decision point of {mod.ref}",
                )
            if d.evidence.because and not d.evidence.none:
                report.warn(where, f"{at}: `because` is read only with `evidence: none`")
            if d.evidence.source:
                src = d.evidence.source
                if src.startswith("$inputs."):
                    pass  # a project input: resolved per project at the hold
                else:
                    src_step, _, rest = src.partition("/")
                    out = rest.split("/")[0].split(".")[0] if rest else ""
                    if src_step not in upstream:
                        report.error(
                            where,
                            f"{at}: evidence {src} names {src_step}, which is not a step upstream of {step.id}",
                        )
                    else:
                        smod = modules.get(pipeline.step(src_step).module)
                        if smod is not None and out not in smod.manifest.outputs:
                            report.error(
                                where,
                                f"{at}: evidence {src} names output {out}, which {smod.ref} does not declare",
                            )
            for key in ("sweep", "rule"):
                spec = getattr(d, key)
                if spec is None:
                    continue
                out = str(spec.get("output") or "")
                if mod is not None and out not in mod.manifest.outputs:
                    report.error(where, f"{at}: {key}.output {out!r} is not an output of {mod.ref}")
            if d.judged is not None:
                ref = str(d.judged.get("module") or "")
                jm = modules.get(ref) if ref else None
                if jm is None or jm.manifest.kind != "judgment":
                    report.error(
                        where, f"{at}: judged.module {ref!r} is not a judgment module of the repo"
                    )
            if d.sensitivity is not None:
                through = str(d.sensitivity.get("through") or "")
                if through not in order or order.index(through) <= order.index(step.id):
                    report.error(
                        where,
                        f"{at}: sensitivity.through {through!r} is not a step downstream of {step.id}",
                    )


def lint_pipeline(
    pipeline: Pipeline,
    modules: ModuleIndex,
    report: LintReport,
    *,
    plugin: Plugin | None,
    method_root: Path | None = None,
    policy: Policy | None = None,
) -> None:
    where = f"pipeline {pipeline.name}"
    if method_root is not None and (method_root / "skills" / f"{pipeline.name}.yml").exists():
        untitled = pipeline.untitled()
        if untitled:
            report.warn(
                where,
                f"skills/{pipeline.name}.yml exists but steps have no title: {', '.join(untitled)}",
            )
    if plugin is None:
        report.error(where, f"domain {pipeline.domain} is not a loaded plugin")
    else:
        for q in pipeline.answers:
            if q not in plugin.objective_questions:
                report.error(where, f"answers names {q}, not a question in plugin {plugin.name}")
    outputs: dict[str, set[str]] = {}
    for step in pipeline.steps:
        mod = modules.get(step.module)
        if mod is None:
            have = modules.by_name(step.module_name)
            if have is not None:
                report.error(
                    where, f"step {step.id} asks for {step.module}; the repo has {have.ref}"
                )
            else:
                report.error(
                    where, f"step {step.id} references module {step.module}, not in the repo"
                )
            outputs[step.id] = set()
            continue
        outputs[step.id] = set(mod.manifest.outputs)
        if mod.manifest.domain != pipeline.domain:
            report.error(
                where,
                f"step {step.id}: module domain {mod.manifest.domain} differs from {pipeline.domain}",
            )
        for name in step.inputs:
            if name not in mod.manifest.inputs:
                report.error(
                    where, f"step {step.id} wires input {name}, which {mod.ref} does not declare"
                )
                continue
            spec = mod.manifest.inputs[name]
            try:
                refs = step.refs()[name]
            except ConfigError as e:
                report.error(where, f"step {step.id} input {name}: {e}")
                continue
            if spec.arity != "many" and (step.is_list(name) or any(r.pattern for r in refs)):
                report.error(
                    where,
                    f"step {step.id} binds input {name} of {mod.ref} to a list or a glob, but the "
                    "input is not `arity: many`",
                )
            if (
                mod.manifest.judgment
                and name in mod.manifest.judgment.evidence
                and spec.arity == "many"
            ):
                report.error(where, f"{mod.ref}: judgment evidence {name} cannot have arity many")
        for name, spec in mod.manifest.inputs.items():
            if name not in step.inputs and not spec.optional:
                report.error(where, f"step {step.id} leaves input {name} of {mod.ref} unwired")
        # params: defaults must validate against the module schema
        merged = {k: v.default for k, v in step.params.items()}
        for k, sch in mod.declared_params.items():
            if k not in merged and isinstance(sch, dict) and "default" in sch:
                merged[k] = sch["default"]
        for p in validate(merged, mod.params_schema):
            report.error(where, f"step {step.id} params fail {mod.ref} params.schema.json: {p}")
        for k in step.params:
            if k not in mod.declared_params:
                report.error(where, f"step {step.id} declares parameter {k}, unknown to {mod.ref}")
        # a default outside its own range or options (L96): the step could admit no value
        for k, decl in step.params.items():
            if decl.fixed or decl.in_range(decl.default):
                continue
            bound = f"range {decl.range}" if decl.range is not None else f"options {decl.options}"
            report.error(
                where,
                f"step {step.id} parameter {k}: the declared default {decl.default!r} is outside "
                f"its {bound}; every proposal would be out of range",
            )
        if mod.manifest.kind == "report":
            for other in pipeline.steps:
                for ref in (r for rs in other.refs().values() for r in rs):
                    if ref.kind == "steps" and ref.name == step.id:
                        report.error(
                            where,
                            f"step {other.id} consumes report step {step.id}; report outputs cannot be inputs",
                        )
    for step in pipeline.steps:
        for name, refs in step.refs().items():
            for ref in refs:
                if ref.kind == "steps" and ref.output not in outputs.get(ref.name, set()):
                    report.error(
                        where, f"step {step.id} input {name} references {ref}, which does not exist"
                    )
    _lint_when(pipeline, modules, report, where)
    _lint_decisions(pipeline, modules, report, where, policy)


def _lint_when(pipeline: Pipeline, modules: ModuleIndex, report: LintReport, where: str) -> None:
    """Conditional steps (L13): the parameter a `when` asks about is declared by the step it
    names, and every input that could bind only skipped outputs is optional on its module."""
    skippable = pipeline.skippable()
    for step in pipeline.steps:
        if step.when is not None:
            ref = pipeline.step(step.when.step)
            ref_mod = modules.get(ref.module)
            declared = set(ref.params) | (set(ref_mod.declared_params) if ref_mod else set())
            if step.when.param not in declared:
                report.error(
                    where,
                    f"step {step.id}: when asks about {step.when.param}, which step {ref.id} "
                    "does not declare",
                )
            decl = ref.params.get(step.when.param)
            if (
                decl is not None
                and decl.options is not None
                and step.when.value not in decl.options
            ):
                report.warn(
                    where,
                    f"step {step.id}: when compares {ref.id}.{step.when.param} with "
                    f"{step.when.value!r}, not one of its options {decl.options}",
                )
        mod = modules.get(step.module)
        if mod is None:
            continue
        for name, refs in step.refs().items():
            if not refs or not all(r.kind == "steps" and r.name in skippable for r in refs):
                continue
            spec = mod.manifest.inputs.get(name)
            if spec is not None and not spec.optional:
                names = ", ".join(sorted({r.name for r in refs}))
                report.error(
                    where,
                    f"step {step.id} input {name} binds only outputs of a conditional step "
                    f"({names}); the input must be optional on {mod.ref}",
                )


def lint_path(path: Path, *, design: Design | None = None) -> LintReport:
    """Lint a module directory or a method repo."""
    _ensure_predicates()
    report = LintReport()
    path = Path(path)
    plugins = load_plugins()
    if (path / "module.yml").exists():
        try:
            module = load_module(path)
        except ConfigError as e:
            report.errors.append(str(e))
            return report
        lint_module(
            module, report, plugin=plugins.get(module.manifest.domain), policy=None, design=design
        )
        return report

    policy: Policy | None = None
    if (path / "policy.yml").exists():
        try:
            policy = load_policy(path / "policy.yml")
        except ConfigError as e:
            report.errors.append(str(e))
    else:
        report.warnings.append(f"{path}: no policy.yml")
    if policy is not None:
        # what the method needs against what is installed here (backlog L28)
        if policy.requires is None:
            report.warn(
                str(path / "policy.yml"),
                "no `requires` (the engine and plugin versions this method needs)",
            )
        else:
            installed = {n: pl.version for n, pl in plugins.items()}
            for problem in check_requires(policy.requires, __version__, installed):
                report.error(str(path / "policy.yml"), f"requires: {problem}")

    try:
        modules = ModuleIndex(path)
    except ConfigError as e:
        report.errors.append(str(e))
        return report
    _lint_env_manifest(path, modules, report)
    _lint_analyze_open(path, report)
    for module in modules.all():
        lint_module(
            module, report, plugin=plugins.get(module.manifest.domain), policy=policy, design=design
        )

    pipelines_dir = path / "pipelines"
    if pipelines_dir.exists():
        for pf in sorted(pipelines_dir.glob("*.yml")):
            try:
                pipeline = load_pipeline(pf)
            except ConfigError as e:
                report.errors.append(str(e))
                continue
            lint_pipeline(
                pipeline,
                modules,
                report,
                plugin=plugins.get(pipeline.domain),
                method_root=path,
                policy=policy,
            )
    return report


def _lint_analyze_open(path: Path, report: LintReport) -> None:
    """`skills/*.analyze.yml` `open:` (L136): two files that both carry `open.intro` are a
    warning, since an open project reads every analyze file and the later file's intro wins; a
    file that takes another's words says `open: {words_of: <pipeline>}` instead. A `words_of`
    naming no analyze file, or one that itself points on, is a warning (followed once)."""
    skills = path / "skills"
    if not skills.is_dir():
        return
    intros: list[str] = []
    pointers: dict[str, str] = {}
    for f in sorted(skills.glob("*.analyze.yml")):
        try:
            data = yaml.safe_load(f.read_text())
        except (OSError, yaml.YAMLError):
            continue  # the renderer's `--check` reports a malformed file
        ob = data.get("open") if isinstance(data, dict) else None
        if not isinstance(ob, dict):
            continue
        target = ob.get("words_of")
        if isinstance(target, str) and target.strip():
            pointers[f.name] = target.strip()
        elif isinstance(ob.get("intro"), str) and ob["intro"].strip():
            intros.append(f.name)
    if len(intros) > 1:
        report.warn(
            str(skills),
            f"open.intro in {len(intros)} analyze files ({', '.join(intros)}): an open project "
            "reads them all and the later file's intro wins; let one carry the words and point "
            "the others at it with `open: {words_of: <pipeline>}`",
        )
    for name, target in pointers.items():
        tf = skills / f"{target}.analyze.yml"
        if not tf.exists():
            report.warn(
                str(skills / name), f"open.words_of names {target}, but {tf.name} is absent"
            )
        elif f"{target}.analyze.yml" in pointers:
            report.warn(
                str(skills / name),
                f"open.words_of names {target}, whose file points on; the pointer is followed once",
            )


def _lint_env_manifest(path: Path, modules: ModuleIndex, report: LintReport) -> None:
    """`envs/manifest.yml` (design 10.3; Lane A item 5, 2026-09-23): parses; every module env is
    an entry; an entry has a `lock` or an `image`; a `sha256` is 64 hex characters; an image
    path that does not exist on this machine is a warning (it may live on the workstation)."""
    import re

    import yaml

    mf = path / "envs" / "manifest.yml"
    envs_used = {m.manifest.env for m in modules.all()}
    if not mf.exists():
        if envs_used:
            report.warn(
                str(mf), "no environment manifest; module envs " + ", ".join(sorted(envs_used))
            )
        return
    try:
        doc = yaml.safe_load(mf.read_text()) or {}
    except yaml.YAMLError as e:
        report.error(str(mf), f"not valid YAML: {e}")
        return
    entries = doc.get("environments") if isinstance(doc, dict) else None
    if not isinstance(entries, dict):
        report.error(str(mf), "expected a top-level `environments:` mapping")
        return
    for name, spec in entries.items():
        where = f"{mf}: environments.{name}"
        if not isinstance(spec, dict):
            report.error(where, "expected a mapping with lock and/or image")
            continue
        if not spec.get("lock") and not spec.get("image"):
            report.error(where, "needs `lock` (local executor) or `image` (apptainer)")
        sha = spec.get("sha256")
        if sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
            report.error(where, "sha256 must be 64 lowercase hex characters")
        image = spec.get("image")
        if image:
            resolved = resolve_image(str(image), path / "envs")
            if not resolved.exists():
                report.warn(where, f"image {image} is not on this machine (looked for {resolved})")
    for env in sorted(envs_used):
        if env not in entries:
            report.error(str(mf), f"module env {env} has no entry in environments")
