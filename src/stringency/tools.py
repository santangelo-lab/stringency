"""`stringency tools list`: what an open project may run (open_mode_plan.md 2.3, 2026-10-16).

A reading verb, plugin-free like `present`: it loads the project's config, trace and module
index, never the plugin, so it works on a delivered pipeline project (the operator reviews the
tools before proposing the switch) and on an open project. Every tool is a module listing
`open` in its `modes`. With the method's `skills/<pipeline>.analyze.yml` present, each tool's
words for the person (`tools:`) and the method's suggested paths (`open.paths`) are carried
through unread; with `--context`, the objective's question and deliverables and the design's
factors and levels are added, so the operator composes the paths forward from one payload.
With `--method <repo@tag>` (L135, 2026-10-29) the tools and words are another checkout's, cloned
the way `init --method` clones, read against this project's delivery: a delivery whose own
method predates the open tools is listed with the method the open project will pin. An analyze
file that says `open: {words_of: <pipeline>}` (L136) takes that pipeline's words.

Reads: stringency.yml, inputs.yml, objective.yml, design.yml, the module index, `deliveries`,
`artifacts`, `steps`, `controls_runs`, and the skill files. Writes nothing in the project (a
`--method` clone goes to a temporary directory, removed after).
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

from stringency.config import Design, InputsManifest, Objective, load_model
from stringency.exit_codes import ConfigError
from stringency.modules import Module
from stringency.present import Site

UNTESTED_NOTE = "none: outputs will be labelled untested"
# a deterministic tool with declared controls: `call` runs them before its first step
# (controls.ensure_current, 2026-10-19), so no pass on record yet is not an untested label
BEFORE_USE_NOTE = "runs before the tool's first use; its outputs are trusted if it passes"


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


BINDS_BY_NAME = "binds by name (--in)"
OPTIONAL_NOTE = "bind with --in to use"


def _candidates(site: Site) -> list[dict[str, Any]]:
    """What a tool's inputs could bind: on an open project the declared inputs and the latest
    run's produced artifacts; on a pipeline project the latest delivery's files and the
    project's own declared inputs, as the open project will hold them (`upstream_<name>`,
    `binds_by_name`: `call` binds them only when named with `--in`, L135)."""
    out: list[dict[str, Any]] = []
    inputs = load_model(InputsManifest, site.root / "inputs.yml")
    if site.open_ended:
        for i in inputs.items:
            c: dict[str, Any] = {
                "ref": f"$inputs.{i.name}",
                "name": i.name,
                "type": i.type,
                "path": i.path,
            }
            if i.upstream_input is not None:
                # read-only, from before the pipeline ran; binds only with --in
                c["upstream_input"] = i.upstream_input.input
                c["binds_by_name"] = True
            out.append(c)
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
    index: dict[str, Any] = {}
    if d is not None and (Path(d["path"]) / "index.json").exists():
        try:
            index = json.loads((Path(d["path"]) / "index.json").read_text())
        except json.JSONDecodeError:
            index = {}
    files = index.get("files", []) if isinstance(index, dict) else []
    for f in files:
        out.append(
            {
                "ref": None,
                "delivered": f.get("file"),
                "name": f.get("output"),
                "step_id": f.get("step_id"),
                "type": f.get("kind"),
                "path": str(Path(d["path"]) / str(f.get("file"))) if d is not None else None,
            }
        )
    # the project's own inputs: the open project holds them read-only as `upstream_<name>`
    # (project.declarations_from_delivery), and `call` binds one only when it is named
    taken = {str(f.get("output")) for f in files} | {
        f"{f.get('step_id')}_{f.get('output')}" for f in files
    }
    for i in inputs.items:
        name = f"upstream_{i.name}"
        if name in taken:
            continue
        out.append(
            {
                "ref": f"$inputs.{name}",
                "name": name,
                "type": i.type,
                "path": i.path,
                "upstream_input": i.name,
                "binds_by_name": True,
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


def _read_analyze(f: Path, notes: list[str]) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(f.read_text())
    except yaml.YAMLError as e:
        notes.append(f"{f}: not valid YAML ({e})")
        return None
    except OSError as e:
        notes.append(f"{f}: cannot be read ({e})")
        return None
    if not isinstance(data, dict):
        notes.append(f"{f}: not a mapping")
        return None
    return data


def words_of(data: dict[str, Any]) -> str | None:
    """The pipeline whose analyze file holds this file's tool words and `open:` block (`open:
    {words_of: <pipeline>}`, L136), or None."""
    ob = data.get("open")
    target = ob.get("words_of") if isinstance(ob, dict) else None
    return str(target) if isinstance(target, str) and target.strip() else None


def _words(
    site: Site,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str], str | None]:
    """(tool words by module name, the `open:` block, notes, the pipeline whose words were
    taken through `words_of`). On a pipeline project the pipeline's own analyze file, or, when
    it says `open: {words_of: <pipeline>}`, that pipeline's file instead (the pointer is followed
    once, never a chain); on an open project every analyze file, a file with `words_of`
    contributing nothing of its own. Malformed files are reported as notes, never fatal: the
    verb reads, it does not lint."""
    words: dict[str, dict[str, Any]] = {}
    open_block: dict[str, Any] = {}
    notes: list[str] = []
    followed: str | None = None
    for f in _skill_files(site):
        data = _read_analyze(f, notes)
        if data is None:
            continue
        target = words_of(data)
        if target is not None:
            if site.open_ended:
                continue  # the file it points to is read in its own turn
            tf = f.parent / f"{target}.analyze.yml"
            if not tf.exists():
                notes.append(f"{f}: open.words_of names {target}, but {tf} does not exist")
                continue
            data = _read_analyze(tf, notes)
            if data is None:
                continue
            followed = target
            again = words_of(data)
            if again is not None:
                notes.append(
                    f"{tf}: open.words_of names {again}; the pointer is followed once, not again"
                )
        for t in data.get("tools") or []:
            if isinstance(t, dict) and t.get("module"):
                words[str(t["module"])] = {k: v for k, v in t.items() if k != "module"}
        ob = data.get("open")
        if isinstance(ob, dict):
            ob = {k: v for k, v in ob.items() if k != "words_of"}
            paths = list(open_block.get("paths") or []) + list(ob.get("paths") or [])
            open_block = {**open_block, **ob, "paths": paths}
    return words, open_block, notes, followed


def _tool_entry(
    site: Site, module: Module, candidates: list[dict[str, Any]], words: dict[str, Any] | None
) -> dict[str, Any]:
    m = module.manifest
    inputs: dict[str, Any] = {}
    unmatched: list[str] = []
    by_name: list[str] = []
    for name, spec in m.inputs.items():
        cands = [c for c in candidates if c.get("type") == spec.type]
        inputs[name] = {
            "type": spec.type,
            "format": spec.format,
            "optional": spec.optional,
            "arity": spec.arity,
            "candidates": cands,
        }
        if spec.optional:
            # an optional input binds nothing by type (steps.bind_inputs, L49)
            inputs[name]["note"] = OPTIONAL_NOTE
            continue
        if not cands:
            unmatched.append(name)
        elif all(c.get("binds_by_name") for c in cands):
            by_name.extend(f"{name}={c['ref']}" for c in cands)
    if unmatched:
        offer = f"not offered: no candidate for {', '.join(unmatched)}"
    elif by_name:
        offer = "offerable; bind with --in " + " or ".join(by_name)
    else:
        offer = "offerable"
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
        auto = m.kind == "deterministic" and bool(control["declared"])
        control["note"] = BEFORE_USE_NOTE if auto else UNTESTED_NOTE
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
        "offerable": not unmatched,
        "offer": offer,
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


def tools_payload(
    site: Site, *, context: bool = False, method: str | None = None
) -> dict[str, Any]:
    """The listing. With `method` (`<repo>@<tag>`, as `init --method` takes it), that method is
    cloned into a temporary directory by the resolver `init` uses and its tools and skill files
    are read against this project's delivery and declared inputs (L135)."""
    if method is None:
        return _payload(site, context=context)
    from stringency.git import clone_at
    from stringency.project import _parse_method

    url, tag = _parse_method(method)
    with tempfile.TemporaryDirectory(prefix="stringency-tools-") as tmp:
        dest = Path(tmp) / "method"
        sha = clone_at(url, tag, dest)
        payload = _payload(dataclasses.replace(site, method_dir=dest), context=context)
    payload["method"] = {
        "repo": url,
        "tag": tag,
        "sha": sha,
        "from": "--method",
        "project_pins": {"repo": site.config.method.repo, "tag": site.config.method.tag},
    }
    return payload


def _payload(site: Site, *, context: bool) -> dict[str, Any]:
    tools = site.tools()
    candidates = _candidates(site)
    words, open_block, notes, followed = _words(site)
    payload: dict[str, Any] = {
        "schema": "stringency.tools/1",
        "project_id": site.config.project_id,
        "mode": site.config.mode,
        "pipeline": site.config.pipeline,
        "method": {"repo": site.config.method.repo, "tag": site.config.method.tag},
        "tools": [_tool_entry(site, m, candidates, words.get(m.manifest.name)) for m in tools],
        "open": open_block,
        "words_of": followed,
        "candidates": candidates,
        "notes": notes,
    }
    if context:
        payload["context"] = context_block(site)
    return payload


def render_tools(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    tools = payload["tools"]
    meth = payload["method"]
    if meth.get("from") == "--method":
        pins = meth["project_pins"]
        lines.append(
            f"tools of method {meth['repo']}@{meth['tag']} ({str(meth['sha'])[:12]}), against "
            f"this project's delivery; the project pins {pins['repo']}@{pins['tag']}"
        )
    if payload.get("words_of"):
        lines.append(f"words: the {payload['words_of']} analyze file's (open.words_of)")
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
        if w.get("not_for"):
            lines.append(f"  not for: {w['not_for']}")
        for name, spec in t["inputs"].items():
            cands = ", ".join(
                str(c.get("ref") or c.get("delivered"))
                + (f" {BINDS_BY_NAME}" if c.get("binds_by_name") else "")
                for c in spec["candidates"]
            )
            opt = ", optional" if spec["optional"] else ""
            note = f"; {spec['note']}" if spec.get("note") else ""
            lines.append(
                f"  input {name} ({spec['type']}{opt}): {cands or 'nothing matches'}{note}"
            )
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
        lines.append(f"  {t['offer']}")
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
