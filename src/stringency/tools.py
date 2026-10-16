"""`stringency tools list`: what an open project may run (open_mode_plan.md 2.3, 2026-10-16).

A reading verb, plugin-free like `present`: it loads the project's config, trace and module
index, never the plugin, so it works on a delivered pipeline project (the operator reviews the
tools before proposing the switch) and on an open project. Every tool is a module listing
`open` in its `modes`. With the method's `skills/<pipeline>.analyze.yml` present, each tool's
words for the person (`tools:`) and the method's suggested paths (`open.paths`) are carried
through unread; with `--context`, the objective's question and deliverables and the design's
factors and levels are added, so the operator composes the paths forward from one payload.

Reads: stringency.yml, inputs.yml, objective.yml, design.yml, the module index, `deliveries`,
`artifacts`, `steps`, `controls_runs`, and the skill files. Writes nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from stringency.config import Design, InputsManifest, Objective, load_model
from stringency.exit_codes import ConfigError
from stringency.modules import Module
from stringency.present import Site

UNTESTED_NOTE = "none: outputs will be labelled untested"


def _env_status(site: Site, env: str) -> str:
    """`verified` when the executor can digest the environment, else `unpinned`; `unknown`
    when the executor cannot be built here (an image missing on this machine)."""
    try:
        from stringency.executor.local import LocalExecutor

        if site.config.executor == "local":
            ex: Any = LocalExecutor(site.method_root / "envs")
        else:
            from stringency.executor.apptainer import ApptainerExecutor

            ex = ApptainerExecutor(site.method_root / "envs")
        return "verified" if ex.env_digest(env) else "unpinned"
    except Exception:  # noqa: BLE001  (a reading verb reports; it does not fail on the host)
        return "unknown"


def _last_passing_control(site: Site, module: Module) -> dict[str, Any] | None:
    row = site.store.one(
        "SELECT control_name, kind, ts, run_id FROM controls_runs WHERE module=? AND "
        "module_version=? AND passed=1 ORDER BY ts DESC, rowid DESC LIMIT 1",
        (module.manifest.name, module.manifest.version),
    )
    return dict(row) if row is not None else None


def _candidates(site: Site) -> list[dict[str, Any]]:
    """What a tool's inputs could bind: on an open project the declared inputs and the latest
    run's produced artifacts; on a pipeline project the latest delivery's files."""
    out: list[dict[str, Any]] = []
    if site.open_ended:
        inputs = load_model(InputsManifest, site.root / "inputs.yml")
        for i in inputs.items:
            out.append({"ref": f"$inputs.{i.name}", "name": i.name, "type": i.type, "path": i.path})
        run = site.store.one(
            "SELECT run_id FROM runs WHERE kind='run' ORDER BY started DESC, rowid DESC LIMIT 1"
        )
        if run is not None:
            for a in site.store.all(
                "SELECT a.artifact_id, a.step_id, a.name, a.kind, a.path FROM artifacts a "
                "JOIN steps s ON s.run_id=a.run_id AND s.step_id=a.step_id "
                "WHERE a.run_id=? AND a.status='produced' AND s.status='completed' ORDER BY a.rowid",
                (run["run_id"],),
            ):
                out.append(
                    {
                        "ref": f"$steps.{a['step_id']}.{a['name']}",
                        "artifact_id": a["artifact_id"],
                        "name": a["name"],
                        "type": a["kind"],
                        "path": a["path"],
                    }
                )
        return out
    d = site.store.one("SELECT path FROM deliveries ORDER BY ts DESC, rowid DESC LIMIT 1")
    if d is None:
        return out
    index_path = Path(d["path"]) / "index.json"
    if not index_path.exists():
        return out
    try:
        index = json.loads(index_path.read_text())
    except json.JSONDecodeError:
        return out
    for f in index.get("files", []):
        out.append(
            {
                "ref": None,
                "delivered": f.get("file"),
                "name": f.get("output"),
                "step_id": f.get("step_id"),
                "type": f.get("kind"),
                "path": str(Path(d["path"]) / str(f.get("file"))),
            }
        )
    return out


def _skill_files(site: Site) -> list[Path]:
    d = site.method_root / "skills"
    if not d.exists():
        return []
    if site.open_ended:
        return sorted(d.glob("*.analyze.yml"))
    f = d / f"{site.config.pipeline}.analyze.yml"
    return [f] if f.exists() else []


def _words(site: Site) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    """(tool words by module name, the `open:` block, notes). Malformed files are reported as
    notes, never fatal: the verb reads, it does not lint."""
    words: dict[str, dict[str, Any]] = {}
    open_block: dict[str, Any] = {}
    notes: list[str] = []
    for f in _skill_files(site):
        try:
            data = yaml.safe_load(f.read_text())
        except yaml.YAMLError as e:
            notes.append(f"{f}: not valid YAML ({e})")
            continue
        if not isinstance(data, dict):
            notes.append(f"{f}: not a mapping")
            continue
        for t in data.get("tools") or []:
            if isinstance(t, dict) and t.get("module"):
                words[str(t["module"])] = {k: v for k, v in t.items() if k != "module"}
        ob = data.get("open")
        if isinstance(ob, dict):
            paths = list(open_block.get("paths") or []) + list(ob.get("paths") or [])
            open_block = {**open_block, **ob, "paths": paths}
    return words, open_block, notes


def _tool_entry(
    site: Site, module: Module, candidates: list[dict[str, Any]], words: dict[str, Any] | None
) -> dict[str, Any]:
    m = module.manifest
    inputs: dict[str, Any] = {}
    for name, spec in m.inputs.items():
        inputs[name] = {
            "type": spec.type,
            "format": spec.format,
            "optional": spec.optional,
            "arity": spec.arity,
            "candidates": [c for c in candidates if c.get("type") == spec.type],
        }
    params: dict[str, Any] = {}
    for name, schema in module.declared_params.items():
        params[name] = {
            "schema": schema,
            "default": schema.get("default") if isinstance(schema, dict) else None,
            "decision_point": name in m.decision_points,
        }
    last = _last_passing_control(site, module)
    control: dict[str, Any] = {
        "last_passing": last,
        "declared": [p.stem for p in module.control_files()],
    }
    if last is None:
        control["note"] = UNTESTED_NOTE
    entry = {
        "ref": m.ref,
        "name": m.name,
        "kind": m.kind,
        "operation": m.operation,
        "env": m.env,
        "env_status": _env_status(site, m.env),
        "inputs": inputs,
        "params": params,
        "decision_points": list(m.decision_points),
        "outputs": {k: {"type": v.type, "format": v.format} for k, v in m.outputs.items()},
        "controls": control,
        "words": words,
    }
    return entry


def context_block(site: Site) -> dict[str, Any]:
    """The objective's question, contrasts and deliverables and the design's factors, levels,
    units and batch variables: what the paths forward are composed from."""
    objective = load_model(Objective, site.root / "objective.yml")
    design = load_model(Design, site.root / "design.yml")
    return {
        "objective": {
            "id": objective.id,
            "question": objective.question,
            "contrasts": objective.contrasts,
            "deliverables": objective.deliverables,
            "params": objective.params,
        },
        "design": {
            "units": design.units,
            "factors": {
                k: {"column": f.column, "levels": f.levels} for k, f in design.factors.items()
            },
            "batch": design.batch,
            "replication_unit": design.replication_unit,
        },
    }


def tools_payload(site: Site, *, context: bool = False) -> dict[str, Any]:
    tools = site.tools()
    candidates = _candidates(site)
    words, open_block, notes = _words(site)
    payload: dict[str, Any] = {
        "schema": "stringency.tools/1",
        "project_id": site.config.project_id,
        "mode": site.config.mode,
        "pipeline": site.config.pipeline,
        "method": {"repo": site.config.method.repo, "tag": site.config.method.tag},
        "tools": [_tool_entry(site, m, candidates, words.get(m.manifest.name)) for m in tools],
        "open": open_block,
        "candidates": candidates,
        "notes": notes,
    }
    if context:
        payload["context"] = context_block(site)
    return payload


def render_tools(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    tools = payload["tools"]
    if not tools:
        lines.append(
            f"no tools: no module of method {payload['method']['tag']} lists open in its modes"
        )
    for t in tools:
        w = t.get("words") or {}
        head = f"{t['ref']}  {t['kind']}, {t['operation']}, env {t['env']} ({t['env_status']})"
        if w.get("title"):
            head = f"{w['title']}: " + head
        lines.append(head)
        if w.get("use_when"):
            lines.append(f"  use when: {w['use_when']}")
        for name, spec in t["inputs"].items():
            cands = ", ".join(str(c.get("ref") or c.get("delivered")) for c in spec["candidates"])
            opt = ", optional" if spec["optional"] else ""
            lines.append(f"  input {name} ({spec['type']}{opt}): {cands or 'nothing matches'}")
        for name, p in t["params"].items():
            dp = "  [decision point]" if p["decision_point"] else ""
            ask = w.get("asks", {}).get(name) if isinstance(w.get("asks"), dict) else None
            lines.append(
                f"  param {name}: default {p['default']!r}{dp}" + (f"; ask: {ask}" if ask else "")
            )
        lines.append(
            "  outputs: " + ", ".join(f"{k} ({v['type']})" for k, v in t["outputs"].items())
        )
        c = t["controls"]
        if c["last_passing"]:
            lp = c["last_passing"]
            lines.append(f"  control: {lp['control_name']} passed {lp['ts']}")
        else:
            lines.append(f"  control: {c.get('note', UNTESTED_NOTE)}")
    paths = (payload.get("open") or {}).get("paths") or []
    if paths:
        lines.append("paths the method suggests:")
        for p in paths:
            if isinstance(p, dict):
                by = f"tool {p['tool']}" if p.get("tool") else "code"
                lines.append(
                    f"  {p.get('answers')}: {by}"
                    + (f"; needs {p['needs']}" if p.get("needs") else "")
                )
    ctx = payload.get("context")
    if ctx:
        o, d = ctx["objective"], ctx["design"]
        lines.append(
            f"objective: {o['question']}; deliverables: {', '.join(o['deliverables']) or 'none'}"
        )
        for c in o["contrasts"]:
            lines.append(f"  contrast: {c[1]} versus {c[2]} on {c[0]}")
        for name, f in d["factors"].items():
            lines.append(f"factor {name} (column {f['column']}): {', '.join(f['levels'])}")
        if d.get("replication_unit"):
            lines.append(f"replication unit: {d['replication_unit']}")
    for n in payload.get("notes") or []:
        lines.append(f"note: {n}")
    return "\n".join(lines)


def load_site(start: Path | None = None) -> Site:
    try:
        return Site.find(start)
    except ConfigError:
        raise
