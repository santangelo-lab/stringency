"""`stringency probe` (design 14.1, backlog L30): is this install ready to run a method? The
engine and its path, every plugin and its version, the container runtime, the skills installed
beside the engine, and with `--method` the method's `requires` against what is installed and
every image its environment manifest names (resolved, present, readable, hashing to the
manifest's sha256). Replaces the shell probe the session brief carried. Reads only."""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from stringency import __version__, siteconfig
from stringency.executor.apptainer import find_binary, resolve_image, sha256_file
from stringency.operator_exec.envcheck import load_env_manifest
from stringency.plugins import installed_plugin_versions
from stringency.policy import load_policy
from stringency.versions import check_requires, compare


@dataclass
class Check:
    name: str
    ok: bool | None  # None: reported, not judged
    detail: str


def probe(method: str | None = None, *, hash_images: bool = True) -> dict[str, Any]:
    import stringency

    checks: list[Check] = []
    engine = {
        "version": __version__,
        "path": str(Path(stringency.__file__).resolve().parent),
        "python": sys.executable,
        "prefix": sys.prefix,
    }
    checks.append(Check("engine", True, f"stringency {__version__} at {engine['path']}"))
    plugins = installed_plugin_versions()
    checks.append(
        Check(
            "plugins",
            bool(plugins),
            ", ".join(f"{n} {v}" for n, v in sorted(plugins.items())) or "no plugin installed",
        )
    )
    binary = find_binary()
    where = shutil.which(binary)
    container = {"binary": binary, "path": where, "version": _binary_version(where)}
    skill = _skill_path()
    skills = {"operator": str(skill) if skill else None, "for_engine": _skill_engine(skill)}
    if skill is None:
        checks.append(Check("skills", None, "no skills installed beside this engine (a checkout)"))
    else:
        checks.append(skills_check(skill, skills["for_engine"], __version__))
    site = {
        "images_root": str(siteconfig.images_root()) if siteconfig.images_root() else None,
        "STRINGENCY_IMAGES": os.environ.get("STRINGENCY_IMAGES"),
    }
    report: dict[str, Any] | None = None
    needs_container = False
    if method:
        report = _probe_method(method, plugins, checks, hash_images)
        needs_container = any(e.get("image") for e in report["envs"].values())
    checks.append(
        Check(
            "container",
            (where is not None) if needs_container else None,
            f"{binary}: {where or 'not on PATH'}"
            + (f" ({container['version']})" if container["version"] else ""),
        )
    )
    return {
        "schema": "stringency.probe/1",
        "ok": all(c.ok is not False for c in checks),
        "engine": engine,
        "plugins": plugins,
        "container": container,
        "skills": skills,
        "site": site,
        "method": report,
        "checks": [asdict(c) for c in checks],
    }


def _probe_method(
    spec: str, plugins: dict[str, str], checks: list[Check], hash_images: bool
) -> dict[str, Any]:
    with contextlib.ExitStack() as stack:
        path = Path(spec)
        if not path.exists() and "@" in spec:
            from stringency.git import clone_at
            from stringency.project import _parse_method

            url, tag = _parse_method(spec)
            tmp = stack.enter_context(tempfile.TemporaryDirectory(prefix="stringency-probe-"))
            path = Path(tmp) / "method"
            clone_at(url, tag, path)
        report: dict[str, Any] = {"spec": spec, "path": str(path), "requires": None, "envs": {}}
        policy_path = path / "policy.yml"
        if not policy_path.exists():
            checks.append(Check("requires", False, f"{policy_path} does not exist"))
        else:
            policy = load_policy(policy_path)
            if policy.requires is None:
                checks.append(Check("requires", None, "policy.yml declares no requires"))
            else:
                problems = check_requires(policy.requires, __version__, plugins)
                report["requires"] = {
                    "engine": policy.requires.engine,
                    "plugins": dict(policy.requires.plugins),
                    "problems": problems,
                }
                checks.append(
                    Check(
                        "requires",
                        not problems,
                        "; ".join(problems)
                        if problems
                        else "the installed engine and plugins satisfy it",
                    )
                )
        envs_root = path / "envs"
        for name, entry in load_env_manifest(envs_root).items():
            env: dict[str, Any] = {"image": None, "lock": None}
            image = entry.get("image")
            if image:
                resolved = resolve_image(str(image), envs_root)
                env["image"] = str(resolved)
                exists, readable = resolved.exists(), os.access(resolved, os.R_OK)
                want = str(entry.get("sha256") or "").removeprefix("sha256:")
                if not exists:
                    checks.append(Check(f"image {name}", False, f"{resolved} not found"))
                elif not readable:
                    checks.append(Check(f"image {name}", False, f"{resolved} is not readable"))
                elif want and hash_images:
                    have = sha256_file(resolved)
                    env["sha256_ok"] = have == want
                    checks.append(
                        Check(
                            f"image {name}",
                            have == want,
                            f"{resolved} "
                            + (
                                "hashes to the manifest's sha256"
                                if have == want
                                else f"hashes to {have[:12]}, manifest says {want[:12]}"
                            ),
                        )
                    )
                else:
                    checks.append(
                        Check(
                            f"image {name}",
                            True,
                            f"{resolved} present"
                            + (" (not hashed)" if want else " (no sha256 in the manifest)"),
                        )
                    )
            lock = entry.get("lock")
            if lock:
                lp = Path(str(lock))
                if not lp.is_absolute():
                    lp = path / lp
                env["lock"] = str(lp)
                checks.append(
                    Check(
                        f"lock {name}",
                        lp.is_file(),
                        f"{lp}" + ("" if lp.is_file() else " not found"),
                    )
                )
            report["envs"][name] = env
        return report


def _binary_version(where: str | None) -> str | None:
    if not where:
        return None
    try:
        out = subprocess.run([where, "--version"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[0] if line else None


def _skill_path() -> Path | None:
    p = Path(sys.prefix) / "skills" / "stringency-operator" / "SKILL.md"
    return p if p.is_file() else None


def _skill_engine(path: Path | None) -> str | None:
    """The engine version the installed operator skill says it is for ("This text is for engine
    0.2.19."), or None when the line is absent."""
    if path is None:
        return None
    m = re.search(r"This text is for engine (\d+(?:\.\d+)+)", path.read_text())
    return m.group(1) if m else None


def skills_check(path: Path, for_engine: str | None, engine: str) -> Check:
    """The skill is written for an engine no newer than this one: the text changes only when a
    verb, a flag or the hold protocol does, so a skill for 0.2.19 drives 0.2.20. A skill for a
    newer engine than the one installed, or one with no version line, fails the check."""
    if for_engine is None:
        return Check("skills", False, f"operator skill at {path} names no engine version")
    ok = compare(for_engine, engine) <= 0
    return Check(
        "skills",
        ok,
        f"operator skill for engine {for_engine} at {path}"
        + ("" if ok else f"; newer than this engine, {engine}"),
    )


def render(payload: dict[str, Any]) -> str:
    lines = []
    for c in payload["checks"]:
        mark = "ok  " if c["ok"] else ("--  " if c["ok"] is None else "FAIL")
        lines.append(f"{mark} {c['name']}: {c['detail']}")
    failed = sum(1 for c in payload["checks"] if c["ok"] is False)
    lines.append("ready" if payload["ok"] else f"not ready: {failed} check(s) failed")
    return "\n".join(lines)
