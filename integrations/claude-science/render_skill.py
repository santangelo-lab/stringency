#!/usr/bin/env python3
"""Render a method repository's analysis skill from `skills/<pipeline>.analyze.yml`.

    <engine python> render_skill.py <method repo | skills/<pipeline>.analyze.yml>
                                    [--pipeline <name>] [--check] [--write] [--out <path>]

The analysis skill is the person-facing entry point for one pipeline (design 10.4, roadmap Track
1d, `spec/ux-two-audiences.md` section 4). Its source is the method's
`skills/<pipeline>.analyze.yml`; the template is `templates/analyze-skill.md.j2` beside this
script; the output is `skills/stringency-analyze-<name>/SKILL.md` in the method repository,
committed there and versioned with the method.

Without flags the rendered skill goes to stdout. `--write` writes it to its place in the method
repository. `--check` validates the source and exits without rendering: 0 when clean, 1 with one
line per problem. Validation reads the pipeline file and the modules when the method repository
has them, so the step ids, titles, question, and deliverable names the skill will say are the
ones the engine uses. Run with the engine's interpreter so jinja2 and pyyaml are present.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import jinja2
import yaml

HERE = Path(__file__).parent
TEMPLATE = "analyze-skill.md.j2"
SUFFIX = ".analyze.yml"

REQUIRED = {
    "pipeline": str,
    "method": str,
    "plugin": str,
    "question": str,
    "title": str,
    "phrasings": dict,
    "steps": dict,
    "deliverables": dict,
    "asks": list,
    "defaults_to_say": dict,
}
OPTIONAL = {"name": str, "summary": str, "decisions": list, "tools": list, "open": dict}
QUESTION_OUTCOMES = ("exec", "cannot", "fork", "explain")  # or tool:<name>
HOW = ("declared", "proposed")
HARNESSES = (
    "claude-science",
    "claude-code",
    "codex",
)  # the operator harnesses a rendering targets (L34 H2)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# Claude Science's skill registry refuses a description over this many characters (seen
# 2026-10-20 on stringency-analyze-xenium-upstream, 1,077).
DESCRIPTION_MAX = 1024


class Problems(list[str]):
    def add(self, msg: str) -> None:
        self.append(msg)


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def _str_list(value: Any, where: str, problems: Problems) -> list[str]:
    if not isinstance(value, list) or not value:
        problems.add(f"{where}: a non-empty list of sentences is required")
        return []
    out = []
    for i, v in enumerate(value, 1):
        if not isinstance(v, str) or not v.strip():
            problems.add(f"{where}[{i}]: must be a non-empty string")
        else:
            out.append(v.strip())
    return out


def _str_map(value: Any, where: str, problems: Problems, *, allow_empty: bool) -> dict[str, str]:
    if not isinstance(value, dict) or (not value and not allow_empty):
        problems.add(f"{where}: a mapping of name to sentence is required")
        return {}
    out = {}
    for k, v in value.items():
        if not isinstance(k, str) or not isinstance(v, str) or not v.strip():
            problems.add(f"{where}.{k}: the value must be a non-empty sentence")
        else:
            out[k] = v.strip()
    return out


def validate(data: Any, source: Path, method_root: Path | None) -> tuple[dict[str, Any], Problems]:
    """Check the analyze yml against its own schema and, when the method repository is present,
    against the pipeline file and the modules. Returns the template context and the problems."""
    problems = Problems()
    if not isinstance(data, dict):
        problems.add(f"{source}: not a mapping")
        return {}, problems
    for key in data:
        if key not in REQUIRED and key not in OPTIONAL:
            problems.add(f"{source}: unknown key `{key}`")
    for key, typ in REQUIRED.items():
        if key not in data:
            problems.add(f"{source}: missing key `{key}`")
        elif not isinstance(data[key], typ):
            problems.add(f"{source}: `{key}` must be a {typ.__name__}")
    for key, typ in OPTIONAL.items():
        if key in data and not isinstance(data[key], typ):
            problems.add(f"{source}: `{key}` must be a {typ.__name__}")
    if problems:
        return {}, problems

    pipeline = data["pipeline"].strip()
    name = data.get("name", pipeline).strip()
    if not SLUG.match(name):
        problems.add(f"name `{name}`: lowercase letters, digits and hyphens only")
    if "@" not in data["method"] or data["method"].endswith("@"):
        problems.add("method: must be `<url or path>@<tag>`")

    phr = data["phrasings"]
    for key in phr:
        if key not in ("positive", "negative"):
            problems.add(f"phrasings: unknown key `{key}`")
    positive = _str_list(phr.get("positive"), "phrasings.positive", problems)
    negative = _str_list(phr.get("negative"), "phrasings.negative", problems)

    steps = _str_map(data["steps"], "steps", problems, allow_empty=False)
    deliverables = _str_map(data["deliverables"], "deliverables", problems, allow_empty=False)
    asks = _str_list(data["asks"], "asks", problems)
    defaults = _str_map(data["defaults_to_say"], "defaults_to_say", problems, allow_empty=True)
    decisions = _decisions(data.get("decisions"), steps, problems)
    tools = _tools(data.get("tools"), problems)
    open_block = _open(data.get("open"), tools, problems)

    after_delivery_titles: list[str] = []
    words_of = open_block.get("words_of")
    words_of_skill = f"stringency-analyze-{words_of}" if words_of else ""
    if method_root is not None:
        _cross_check(method_root, pipeline, data["question"], steps, deliverables, problems)
        _cross_check_decisions(method_root, pipeline, decisions, problems)
        _cross_check_tools(method_root, pipeline, tools, open_block, problems)
        if words_of:
            words_of_skill = _check_words_of(method_root, pipeline, words_of, problems)
        _check_questions_file(method_root, pipeline, tools, problems)
        delivery = method_root / "skills" / f"{pipeline}.yml"
        if delivery.exists():
            try:
                d = _read_yaml(delivery)
                if isinstance(d, dict) and d.get("skill") == 1:
                    after_delivery_titles = [
                        str(item["title"])
                        for item in d.get("after_delivery") or []
                        if isinstance(item, dict) and item.get("title")
                    ]
            except yaml.YAMLError as e:
                problems.add(f"{delivery}: not valid YAML ({e})")

    summary = data.get("summary", data["title"]).strip().rstrip(".")
    description = (
        f"{summary}. Load when the person {'; '.join(positive)}. "
        f"Do not load for {'; '.join(negative)}. "
        f"Runs the `{pipeline}` pipeline under stringency and shows the CLI only on request."
    )
    if len(description) > DESCRIPTION_MAX:
        problems.add(
            f"description: {len(description)} characters; the skill registry caps it at "
            f"{DESCRIPTION_MAX} (shorten summary or phrasings by {len(description) - DESCRIPTION_MAX})"
        )
    ctx = {
        "skill_name": f"stringency-analyze-{name}",
        "harness": "claude-science",  # the rendering's operator harness; `--harness` overrides
        "name": name,
        "description": description,
        "title": data["title"].strip(),
        "source": f"skills/{source.name}",
        "method": data["method"].strip(),
        "pipeline": pipeline,
        "plugin": data["plugin"].strip(),
        "question": data["question"].strip(),
        "asks": asks,
        "defaults_to_say": [{"key": k, "say": v} for k, v in defaults.items()],
        "steps": [{"id": k, "title": v} for k, v in steps.items()],
        "deliverables": [{"name": k, "sentence": v} for k, v in deliverables.items()],
        "after_delivery_titles": after_delivery_titles,
        "declared": [
            {**d, "title": steps.get(d["step"], d["step"])}
            for d in decisions
            if d["how"] == "declared"
        ],
        "proposed": [
            {
                **d,
                "title": steps.get(d["step"], d["step"]),
                "after_title": steps.get(d["after"], d["after"]),
            }
            for d in decisions
            if d["how"] == "proposed"
        ],
        "tools": tools,
        "open_intro": open_block.get("intro", ""),
        "open_paths": open_block.get("paths", []),
        "words_of": words_of or "",
        "words_of_skill": words_of_skill,
    }
    return ctx, problems


def _check_words_of(root: Path, pipeline: str, target: str, problems: Problems) -> str:
    """`open.words_of` names another analyze file of this method that carries tool words and
    is not itself a pointer (followed once). Returns the name of the skill it renders to."""
    skill = f"stringency-analyze-{target}"
    if target == pipeline:
        problems.add("open.words_of: names this pipeline itself")
        return skill
    f = root / "skills" / f"{target}{SUFFIX}"
    if not f.exists():
        problems.add(f"open.words_of: no analyze file {f.name} in this method")
        return skill
    try:
        d = _read_yaml(f)
    except yaml.YAMLError as e:
        problems.add(f"open.words_of: {f.name} is not valid YAML ({e})")
        return skill
    if not isinstance(d, dict):
        problems.add(f"open.words_of: {f.name} is not a mapping")
        return skill
    ob = d.get("open")
    if isinstance(ob, dict) and "words_of" in ob:
        problems.add(f"open.words_of: {f.name} points on to another file; one pointer only")
    if not d.get("tools"):
        problems.add(f"open.words_of: {f.name} carries no `tools` to take the words of")
    name = d.get("name")
    return f"stringency-analyze-{name.strip()}" if isinstance(name, str) else skill


def _tools(value: Any, problems: Problems) -> list[dict[str, Any]]:
    """`tools`: the words a method writes for each tool a person may ask for after delivery
    (open mode, 2026-10-16): `{module, title, use_when, asks: {param: question}, proposed:
    [{param, evidence, ask}], defaults_to_say: {param: phrase}}`. The engine reads `module.yml`
    for what a tool is; this is what the skill says about it."""
    if value is None:
        return []
    if not isinstance(value, list):
        problems.add("tools: a list is required")
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, t in enumerate(value, 1):
        where = f"tools[{i}]"
        if not isinstance(t, dict):
            problems.add(f"{where}: must be a mapping")
            continue
        for key in t:
            if key not in ("module", "title", "use_when", "asks", "proposed", "defaults_to_say"):
                problems.add(f"{where}: unknown key `{key}`")
        module = t.get("module")
        if not isinstance(module, str) or not SLUG.match(module):
            problems.add(f"{where}: `module` must be the module's name")
            continue
        if module in seen:
            problems.add(f"{where}: module `{module}` listed twice")
            continue
        seen.add(module)
        title, use_when = t.get("title"), t.get("use_when")
        if not isinstance(title, str) or not title.strip():
            problems.add(
                f"{where} ({module}): `title` must be a short phrase in the person's words"
            )
            continue
        if not isinstance(use_when, str) or not use_when.strip():
            problems.add(
                f"{where} ({module}): `use_when` must say when this tool answers a question"
            )
            continue
        asks = _str_map(t.get("asks") or {}, f"{where}.asks", problems, allow_empty=True)
        defaults = _str_map(
            t.get("defaults_to_say") or {}, f"{where}.defaults_to_say", problems, allow_empty=True
        )
        proposed: list[dict[str, Any]] = []
        raw_prop = t.get("proposed") or []
        if not isinstance(raw_prop, list):
            problems.add(f"{where}.proposed: a list is required")
            raw_prop = []
        for j, p in enumerate(raw_prop, 1):
            pw = f"{where}.proposed[{j}]"
            if not isinstance(p, dict) or not isinstance(p.get("param"), str):
                problems.add(f"{pw}: must be a mapping with `param`")
                continue
            evidence = _str_list(p.get("evidence"), f"{pw}.evidence", problems)
            ask = p.get("ask")
            if not isinstance(ask, str) or not ask.strip():
                problems.add(f"{pw}: `ask` must be the question in the person's words")
                continue
            proposed.append({"param": p["param"].strip(), "evidence": evidence, "ask": ask.strip()})
        out.append(
            {
                "module": module,
                "title": title.strip(),
                "use_when": use_when.strip(),
                "asks": [{"param": k, "ask": v} for k, v in asks.items()],
                "proposed": proposed,
                "defaults_to_say": [{"key": k, "say": v} for k, v in defaults.items()],
            }
        )
    return out


def _open(value: Any, tools: list[dict[str, Any]], problems: Problems) -> dict[str, Any]:
    """`open`: `{intro, paths: [{answers, tool | code, needs, asks}]}`, the method's suggested
    paths forward in its own words (open mode, 2026-10-16). A path names a listed tool or says
    `code: true`, never both; `needs` names the pipeline outputs it needs delivered. Or
    `{words_of: <pipeline>}` (L136, 2026-10-29): this pipeline's delivery is opened with that
    pipeline's tool words and `open:` block, so the file carries no `tools`, `intro` or `paths`
    of its own."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        problems.add("open: a mapping is required")
        return {}
    for key in value:
        if key not in ("intro", "paths", "words_of"):
            problems.add(f"open: unknown key `{key}`")
    if "words_of" in value:
        target = value["words_of"]
        if not isinstance(target, str) or not SLUG.match(target):
            problems.add("open.words_of: must name a pipeline")
            return {}
        if "intro" in value or "paths" in value:
            problems.add(
                "open.words_of: a file that takes another pipeline's words carries no "
                "`intro` or `paths` of its own"
            )
        if tools:
            problems.add(
                "open.words_of: a file that takes another pipeline's words carries no `tools`"
            )
        return {"words_of": target}
    intro = value.get("intro", "")
    if intro is not None and not isinstance(intro, str):
        problems.add("open.intro: must be a sentence")
        intro = ""
    paths_raw = value.get("paths") or []
    if not isinstance(paths_raw, list):
        problems.add("open.paths: a list is required")
        paths_raw = []
    names = {t["module"] for t in tools}
    paths: list[dict[str, Any]] = []
    for i, p in enumerate(paths_raw, 1):
        where = f"open.paths[{i}]"
        if not isinstance(p, dict):
            problems.add(f"{where}: must be a mapping")
            continue
        for key in p:
            if key not in ("answers", "tool", "code", "needs", "asks"):
                problems.add(f"{where}: unknown key `{key}`")
        answers = p.get("answers")
        if not isinstance(answers, str) or not answers.strip():
            problems.add(f"{where}: `answers` must say what the path answers")
            continue
        tool, code = p.get("tool"), bool(p.get("code"))
        if tool is not None and code:
            problems.add(f"{where}: a path names a tool or says code, not both")
            continue
        if tool is None and not code:
            problems.add(f"{where}: a path names a listed tool or says `code: true`")
            continue
        if tool is not None and tool not in names:
            problems.add(f"{where}: tool `{tool}` is not in `tools`")
            continue
        needs = _str_list(p.get("needs"), f"{where}.needs", problems) if "needs" in p else []
        asks = p.get("asks")
        if asks is not None and (not isinstance(asks, str) or not asks.strip()):
            problems.add(f"{where}: `asks` must be a sentence")
            continue
        paths.append(
            {
                "answers": answers.strip(),
                "tool": tool,
                "code": code,
                "needs": needs,
                "asks": (asks or "").strip(),
                "title": next((t["title"] for t in tools if t["module"] == tool), None),
            }
        )
    return {"intro": (intro or "").strip(), "paths": paths}


def _module_yml(root: Path, name: str) -> dict[str, Any] | None:
    mfile = root / "modules" / name / "module.yml"
    if not mfile.exists():
        return None
    m = _read_yaml(mfile)
    return m if isinstance(m, dict) else None


def _cross_check_tools(
    root: Path,
    pipeline: str,
    tools: list[dict[str, Any]],
    open_block: dict[str, Any],
    problems: Problems,
) -> None:
    """Each tool is a module of the method that lists `open`; every `asks` and `proposed` key is
    a parameter of its schema; every decision point of the module is settled by one of them;
    every path's `needs` is an output of a pipeline step (the `decisions:` check of backlog L32,
    reused)."""
    import json

    if not (root / "modules").is_dir():
        return
    for t in tools:
        m = _module_yml(root, t["module"])
        if m is None:
            problems.add(f"tools: `{t['module']}` is not a module of this method")
            continue
        modes = m.get("modes") or ["pipeline"]
        if "open" not in modes:
            problems.add(f"tools: module `{t['module']}` does not list `open` in its modes")
        schema_path = root / "modules" / t["module"] / "params.schema.json"
        params: set[str] = set()
        if schema_path.exists():
            try:
                sch = json.loads(schema_path.read_text())
                params = set((sch.get("properties") or {}).keys())
            except (json.JSONDecodeError, AttributeError):
                problems.add(f"tools: {schema_path} is not a JSON object")
        settled = {a["param"] for a in t["asks"]} | {p["param"] for p in t["proposed"]}
        for name in settled:
            if name not in params:
                problems.add(
                    f"tools: `{t['module']}` has no parameter `{name}` (asked or proposed)"
                )
        for dp in m.get("decision_points") or []:
            if str(dp) not in settled:
                problems.add(
                    f"tools: decision point `{dp}` of `{t['module']}` is settled by nobody: "
                    "add it to `asks` or `proposed`"
                )
    if not open_block.get("paths"):
        return
    pfile = root / "pipelines" / f"{pipeline}.yml"
    outputs: set[str] = set()
    if pfile.exists():
        p = _read_yaml(pfile)
        for s in (p.get("steps") or []) if isinstance(p, dict) else []:
            if isinstance(s, dict) and s.get("module"):
                m = _module_yml(root, str(s["module"]).split("@")[0])
                if m and isinstance(m.get("outputs"), dict):
                    outputs |= set(m["outputs"])
    if not outputs:
        return
    for i, path in enumerate(open_block["paths"], 1):
        for need in path["needs"]:
            if need not in outputs:
                problems.add(
                    f"open.paths[{i}]: needs `{need}`, which no step of pipeline `{pipeline}` produces"
                )


def _check_questions_file(
    root: Path, pipeline: str, tools: list[dict[str, Any]], problems: Problems
) -> None:
    """`skills/<pipeline>.questions.yml` (open mode): `questions: 1`, `skill`, and lists
    `positive` and `negative` of `{text, expect}` where `expect` is `tool:<listed tool>`,
    `exec`, `cannot`, `fork` or `explain`. Shape only; it is run by hand."""
    f = root / "skills" / f"{pipeline}.questions.yml"
    if not f.exists():
        return
    try:
        data = _read_yaml(f)
    except yaml.YAMLError as e:
        problems.add(f"{f}: not valid YAML ({e})")
        return
    if not isinstance(data, dict) or data.get("questions") != 1:
        problems.add(f"{f}: must be a `questions: 1` document")
        return
    names = {t["module"] for t in tools}
    for key in ("positive", "negative"):
        items = data.get(key)
        if not isinstance(items, list) or not items:
            problems.add(f"{f}: `{key}` must be a non-empty list of {{text, expect}}")
            continue
        for i, it in enumerate(items, 1):
            if not isinstance(it, dict) or not isinstance(it.get("text"), str):
                problems.add(f"{f}: {key}[{i}] must be a mapping with `text`")
                continue
            exp = str(it.get("expect") or "")
            if exp.startswith("tool:"):
                if exp[5:] not in names:
                    problems.add(f"{f}: {key}[{i}] expects tool `{exp[5:]}`, not in `tools`")
            elif exp not in QUESTION_OUTCOMES:
                problems.add(
                    f"{f}: {key}[{i}] `expect` must be tool:<name> or one of {', '.join(QUESTION_OUTCOMES)}"
                )


def _decisions(value: Any, steps: dict[str, str], problems: Problems) -> list[dict[str, Any]]:
    """`decisions`: the decision points a person settles, each `{step, param, how, ask,
    evidence?, after?}`. `how: declared` is asked before the echo-back and written to
    `objective.yml` `params:` (engine 0.2.18); `how: proposed` is proposed by the operator after
    `after` has run, from the evidence named, and approved at the hold (engine 0.2.19 skills)."""
    if value is None:
        return []
    if not isinstance(value, list):
        problems.add("decisions: a list is required")
        return []
    out: list[dict[str, Any]] = []
    order = list(steps)
    for i, d in enumerate(value, 1):
        where = f"decisions[{i}]"
        if not isinstance(d, dict):
            problems.add(f"{where}: must be a mapping")
            continue
        for key in d:
            if key not in ("step", "param", "how", "ask", "evidence", "after"):
                problems.add(f"{where}: unknown key `{key}`")
        step, param, how, ask = d.get("step"), d.get("param"), d.get("how"), d.get("ask")
        if not isinstance(step, str) or step not in steps:
            problems.add(f"{where}: `step` must be one of the pipeline's step ids (got {step!r})")
            continue
        if not isinstance(param, str) or not param.strip():
            problems.add(f"{where}: `param` must name the parameter")
            continue
        if how not in HOW:
            problems.add(f"{where}: `how` must be one of {', '.join(HOW)} (got {how!r})")
            continue
        if not isinstance(ask, str) or not ask.strip():
            problems.add(f"{where}: `ask` must be the question in the person's words")
            continue
        evidence = (
            _str_list(d.get("evidence"), f"{where}.evidence", problems) if "evidence" in d else []
        )
        after = d.get("after")
        if how == "proposed":
            if not isinstance(after, str) or after not in steps:
                problems.add(
                    f"{where}: a proposed decision needs `after`, the step whose outputs it is proposed from"
                )
                continue
            if order.index(after) >= order.index(step):
                problems.add(f"{where}: `after` ({after}) must come before `step` ({step})")
                continue
            if not evidence:
                problems.add(
                    f"{where}: a proposed decision names the `evidence` the operator reads"
                )
                continue
        elif after is not None or evidence:
            problems.add(f"{where}: a declared decision takes no `after` or `evidence`")
            continue
        out.append(
            {
                "step": step,
                "param": param.strip(),
                "how": how,
                "ask": ask.strip(),
                "evidence": evidence,
                "after": after,
            }
        )
    return out


def _cross_check_decisions(
    root: Path, pipeline: str, decisions: list[dict[str, Any]], problems: Problems
) -> None:
    """Each decision's parameter is a decision point of the step's module (or, failing a
    `decision_points` list, a parameter the pipeline declares for the step)."""
    pfile = root / "pipelines" / f"{pipeline}.yml"
    if not decisions or not pfile.exists():
        return
    p = _read_yaml(pfile)
    if not isinstance(p, dict) or not isinstance(p.get("steps"), list):
        return
    by_id = {str(s.get("id")): s for s in p["steps"] if isinstance(s, dict)}
    for d in decisions:
        s = by_id.get(d["step"])
        if s is None or not s.get("module"):
            continue
        mfile = root / "modules" / str(s["module"]).split("@")[0] / "module.yml"
        points: list[str] = []
        if mfile.exists():
            m = _read_yaml(mfile)
            if isinstance(m, dict) and isinstance(m.get("decision_points"), list):
                points = [str(x) for x in m["decision_points"]]
        declared = set(points) | set(
            (s.get("params") or {}).keys() if isinstance(s.get("params"), dict) else []
        )
        if d["param"] not in declared:
            problems.add(
                f"decisions: {d['step']}.{d['param']} is neither a decision point of its module nor a parameter the pipeline declares"
            )
            continue
        # the pipeline's `decision.evidence` (engine 0.2.29, L61) and the skill's `evidence`
        # must name the same source when both name one
        pdecl = (
            (s.get("params") or {}).get(d["param"]) if isinstance(s.get("params"), dict) else None
        )
        block = pdecl.get("decision") if isinstance(pdecl, dict) else None
        ev = block.get("evidence") if isinstance(block, dict) else None
        src = (
            ev
            if isinstance(ev, str) and ev.strip().lower() != "none"
            else (ev.get("source") if isinstance(ev, dict) else None)
        )
        if d["how"] == "proposed" and isinstance(src, str) and d["evidence"]:
            want = _norm_source(src)
            if want not in {_norm_source(e) for e in d["evidence"]}:
                problems.add(
                    f"decisions: {d['step']}.{d['param']} names evidence {d['evidence']}, but the pipeline's `decision.evidence` is {src}"
                )


def _norm_source(source: str) -> str:
    s = source.strip()
    if s.startswith("$inputs.") or "/" in s:
        return s
    head, dot, tail = s.partition(".")
    return f"{head}/{tail}" if dot and head and tail and "." not in tail else s


def _cross_check(
    root: Path,
    pipeline: str,
    question: str,
    steps: dict[str, str],
    deliverables: dict[str, str],
    problems: Problems,
) -> None:
    pdir = root / "pipelines"
    if not pdir.is_dir() or not any(pdir.glob("*.yml")):
        return  # an unpopulated template repository; nothing to check against
    pfile = pdir / f"{pipeline}.yml"
    if not pfile.exists():
        problems.add(f"{pfile}: pipeline file not found (the skill names pipeline `{pipeline}`)")
        return
    p = _read_yaml(pfile)
    if not isinstance(p, dict) or not isinstance(p.get("steps"), list):
        problems.add(f"{pfile}: not a pipeline document")
        return
    answers = p.get("answers") or []
    if question not in answers:
        problems.add(f"question `{question}` is not among the pipeline's answers {answers}")
    ids = [str(s.get("id")) for s in p["steps"] if isinstance(s, dict)]
    if list(steps) != ids:
        problems.add(f"steps: ids must be the pipeline's, in order: {ids} (got {list(steps)})")
    for s in p["steps"]:
        if not isinstance(s, dict):
            continue
        sid, title = str(s.get("id")), s.get("title")
        if title and sid in steps and steps[sid] != title:
            problems.add(
                f"steps.{sid}: title must be the pipeline's `{title}` (got `{steps[sid]}`)"
            )
        if not title:
            problems.add(f"steps.{sid}: the pipeline declares no title; add one there first")
    outputs: set[str] = set()
    for s in p["steps"]:
        if not isinstance(s, dict) or not s.get("module"):
            continue
        mname = str(s["module"]).split("@")[0]
        mfile = root / "modules" / mname / "module.yml"
        if mfile.exists():
            m = _read_yaml(mfile)
            if isinstance(m, dict) and isinstance(m.get("outputs"), dict):
                outputs |= set(m["outputs"])
                outputs |= {f"{s.get('id')}.{o}" for o in m["outputs"]}
    if outputs:
        # a bare output name, or `<step>.<output>` for one step's (L135)
        for d in deliverables:
            if d not in outputs:
                problems.add(
                    f"deliverables.{d}: no module of the pipeline produces an output named `{d}`"
                )


def render(ctx: dict[str, Any]) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(HERE / "templates"),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(TEMPLATE).render(**ctx)


def locate(source: Path, pipeline: str | None) -> tuple[Path, Path | None]:
    """(analyze yml, method root or None). A file argument is used as is; a directory is a method
    repository whose `skills/` holds the analyze files."""
    source = source.resolve()
    if source.is_file():
        root = source.parent.parent if source.parent.name == "skills" else None
        return source, root
    skills = source / "skills"
    if pipeline:
        return skills / f"{pipeline}{SUFFIX}", source
    found = sorted(skills.glob(f"*{SUFFIX}")) if skills.is_dir() else []
    if len(found) != 1:
        names = ", ".join(f.name for f in found) or "none"
        sys.exit(f"{skills}: pass --pipeline; analyze files found: {names}")
    return found[0], source


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", help="method repository, or a skills/<pipeline>.analyze.yml file")
    ap.add_argument("--pipeline", help="which analyze file, when the repository has several")
    ap.add_argument("--check", action="store_true", help="validate only; exit 1 with the problems")
    ap.add_argument(
        "--write", action="store_true", help="write skills/stringency-analyze-<name>/SKILL.md"
    )
    ap.add_argument("--out", help="write the rendered skill to this path instead")
    ap.add_argument(
        "--harness",
        choices=HARNESSES,
        default="claude-science",
        help="the operator harness the rendering is for: its mechanics section differs",
    )
    args = ap.parse_args()

    yml, root = locate(Path(args.source), args.pipeline)
    if not yml.exists():
        sys.exit(f"{yml}: not found")
    try:
        data = _read_yaml(yml)
    except yaml.YAMLError as e:
        sys.exit(f"{yml}: not valid YAML ({e})")
    ctx, problems = validate(data, yml, root)
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        sys.exit(1)
    ctx["harness"] = args.harness
    if args.check:
        print(f"{yml}: ok ({ctx['skill_name']})")
        return
    text = render(ctx)
    if args.out:
        Path(args.out).write_text(text)
        print(args.out)
    elif args.write:
        if root is None:
            sys.exit("--write needs the file to live in <method repo>/skills/")
        out = root / "skills" / ctx["skill_name"] / "SKILL.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        print(out)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
