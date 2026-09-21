"""Lint (design 13). Errors fail; warnings do not.

`lint_path` accepts a module directory or a method repo. A method repo is linted whole:
every module, every pipeline, and the policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from stringency.config import Design
from stringency.controls import load_control
from stringency.exit_codes import ConfigError
from stringency.gate import in_scope_specs
from stringency.modules import Module, ModuleIndex, load_module
from stringency.pipelines import Pipeline, load_pipeline
from stringency.plugins import Plugin, load_plugins
from stringency.policy import Policy, load_policy
from stringency.predicates import registry
from stringency.prompting import check_vars
from stringency.schemas import includes_base_judgment, schema_is_valid, validate


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

    # scripts
    if m.kind in ("deterministic", "report") and module.entry_script is None:
        report.error(where, "no pre.* script (or entry:) found")
    for label, script in (("entry", module.entry_script), ("post", module.post_script)):
        if script is not None and not script.exists():
            report.error(where, f"{label} script {script.name} is missing")

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

    # in-scope predicates not listed
    listed = {g.split("@")[0] for g in m.gates}
    for phase in ("pre", "post"):
        for spec in in_scope_specs(
            registry, phase, operation=m.operation, module=m, runner=m.runner
        ):
            if spec.id not in listed and spec.scope != ("*",):
                report.warn(where, f"in-scope predicate {spec.ref} is not listed in gates")


def lint_pipeline(
    pipeline: Pipeline,
    modules: ModuleIndex,
    report: LintReport,
    *,
    plugin: Plugin | None,
    method_root: Path | None = None,
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
        if mod.manifest.kind == "report":
            for other in pipeline.steps:
                for ref in other.refs().values():
                    if ref.kind == "steps" and ref.name == step.id:
                        report.error(
                            where,
                            f"step {other.id} consumes report step {step.id}; report outputs cannot be inputs",
                        )
    for step in pipeline.steps:
        for name, ref in step.refs().items():
            if ref.kind == "steps" and ref.output not in outputs.get(ref.name, set()):
                report.error(
                    where, f"step {step.id} input {name} references {ref}, which does not exist"
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

    try:
        modules = ModuleIndex(path)
    except ConfigError as e:
        report.errors.append(str(e))
        return report
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
                pipeline, modules, report, plugin=plugins.get(pipeline.domain), method_root=path
            )
    return report
