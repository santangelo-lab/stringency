#!/usr/bin/env python3
"""Render a method repository's analysis skill from `skills/<pipeline>.analyze.yml`.

    <engine python> render_skill.py <method repo | skills/<pipeline>.analyze.yml>
                                    [--pipeline <name>] [--check] [--write] [--out <path>]

The analysis skill is the person-facing entry point for one pipeline (design 10.4, roadmap Track
1d, `spec/plans/ux-two-audiences.md` section 4). Its source is the method's
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
OPTIONAL = {"name": str, "summary": str}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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

    after_delivery_titles: list[str] = []
    if method_root is not None:
        _cross_check(method_root, pipeline, data["question"], steps, deliverables, problems)
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
    ctx = {
        "skill_name": f"stringency-analyze-{name}",
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
    }
    return ctx, problems


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
    if outputs:
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
