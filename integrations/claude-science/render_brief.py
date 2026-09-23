#!/usr/bin/env python3
"""Render the first message for a Claude Science session that drives a stringency project over
an SSH compute provider, or the project's agent-context text.

    <engine python> render_brief.py <project dir> --provider <name> [--context] [--app-version V]
                                   [--method <url>@<tag> --pipeline <name>] [--image <sif>]...
                                   [--declare]

Reads `<project>/stringency.yml` and `<project>/method/envs/manifest.yml` when the project is
bound. For a project that `init` has not created yet, pass --method and --pipeline; the brief
then includes the init phase and expects the declaration files in the parent directory; with
--declare, Phase 1 instead hands over to the `stringency-declare` skill, which drafts the files
from the person's brief and a sample manifest. --image names a container image the probe should
check when the project is unbound (bound projects read the method manifest). Run with
the engine's interpreter so jinja2 and pyyaml are present:
`/usr/local/lib/stringency/current/bin/python render_brief.py ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jinja2
import yaml

HERE = Path(__file__).parent
ENGINE_BIN = "/data/lab/env/stringency/current/bin"


def load(args: argparse.Namespace) -> dict:
    project = Path(args.project).resolve()
    cfg_path = project / "stringency.yml"
    ctx: dict = {
        "provider": args.provider,
        "project": str(project),
        "parent": str(project.parent),
        "name": project.name,
        "engine_bin": args.engine_bin,
        "app_version": args.app_version or "unknown",
        "bound": cfg_path.exists(),
        "images": list(args.image or []),
        "declare": bool(args.declare),
    }
    if ctx["bound"]:
        cfg = yaml.safe_load(cfg_path.read_text())
        ctx.update(
            method=f"{cfg['method']['repo']}@{cfg['method']['tag']}",
            method_sha=cfg["method"]["sha"][:12],
            pipeline=cfg["pipeline"],
            profile=cfg["profile"],
            harness=cfg["judgment_harness"],
            executor=cfg["executor"],
            owner=cfg["roles"]["owner"],
            reviewer=cfg["roles"]["reviewer"],
        )
        manifest = project / "method" / "envs" / "manifest.yml"
        if manifest.exists():
            envs = yaml.safe_load(manifest.read_text()).get("environments", {}) or {}
            ctx["images"] = sorted(
                set(ctx["images"])
                | {str(e["image"]) for e in envs.values() if isinstance(e, dict) and e.get("image")}
            )
    else:
        if not (args.method and args.pipeline):
            sys.exit(f"{cfg_path} not found: pass --method <url>@<tag> and --pipeline <name>")
        ctx.update(
            method=args.method,
            method_sha=None,
            pipeline=args.pipeline,
            profile=args.profile,
            harness="subagent",
            executor="apptainer",
            owner=None,
            reviewer=None,
        )
    return ctx


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("project", help="project directory (bound, or to be created by init)")
    ap.add_argument("--provider", required=True, help="Claude Science compute provider name")
    ap.add_argument(
        "--context", action="store_true", help="render the agent context instead of the brief"
    )
    ap.add_argument("--app-version", default=None, help="Claude Science version, if known")
    ap.add_argument("--engine-bin", default=ENGINE_BIN)
    ap.add_argument("--method", help="<url>@<tag>, for an unbound project")
    ap.add_argument("--pipeline", help="pipeline name, for an unbound project")
    ap.add_argument("--profile", default="standard")
    ap.add_argument(
        "--image", action="append", help="container image the probe checks (unbound projects)"
    )
    ap.add_argument(
        "--declare",
        action="store_true",
        help="Phase 1 hands over to the stringency-declare skill instead of init from files",
    )
    args = ap.parse_args()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(HERE / "templates"),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    name = "agent-context.md.j2" if args.context else "brief.md.j2"
    sys.stdout.write(env.get_template(name).render(**load(args)))


if __name__ == "__main__":
    main()
