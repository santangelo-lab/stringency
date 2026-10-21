#!/usr/bin/env python3
"""Harness conformance (backlog L36; `commons-assessment.md` 4.2): enumerate `tests/shared/
dispatch.json` and `holds.json` against a harness's operator text and the engine's reader, so a
new operator harness (Codex, a future one) has something to run rather than prose to read.

    python integrations/conformance.py --harness codex \\
        --skill integrations/claude-science/stringency-operator/SKILL.md \\
        --skill integrations/codex/README.md
    python integrations/conformance.py --harness claude-science \\
        --skill integrations/claude-science/stringency-operator/SKILL.md

Exit 0 when every case holds and the sets were not empty; 1 otherwise, naming each failure.
Reads only; the engine must be importable (run from the repository with `uv run`)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "tests" / "shared"


def dispatch_cases(operator: str | None = None) -> list[str]:
    """Run every accepted and refused envelope through the engine's reader."""
    from stringency.harness.base import Request
    from stringency.harness.subagent import read_response

    doc = json.loads((SHARED / "dispatch.json").read_text())
    r = doc["request"]
    req = Request(
        replicate=r["replicate"],
        nonce=r["nonce"],
        prompt=r["prompt"],
        schema=r["schema"],
        items=tuple(r["items"]),
        module="m@1",
        template_ref="t",
    )
    failures: list[str] = []
    n = 0
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for case in doc["accepted"]:
            n += 1
            (d / "resp_1.json").write_text(json.dumps(case["response"]))
            inv = read_response(req, d, case.get("operator", operator))
            if inv.error is not None or inv.structured != case["structured"]:
                failures.append(f"accepted/{case['name']}: {inv.error or inv.structured}")
            if inv.via != case.get("via", "subagent"):
                failures.append(f"accepted/{case['name']}: via {inv.via}")
            if "isolation" in case and inv.isolation != case["isolation"]:
                failures.append(f"accepted/{case['name']}: isolation {inv.isolation}")
        for case in doc["refused"]:
            n += 1
            p = d / "resp_1.json"
            if p.exists():
                p.unlink()
            if "response" in case:
                p.write_text(json.dumps(case["response"]))
            elif "text" in case:
                p.write_text(case["text"])
            inv = read_response(req, d, operator)
            if inv.error is None:
                failures.append(f"refused/{case['name']}: parsed")
            elif (
                "error" in case
                and inv.error != case["error"]
                or "error_prefix" in case
                and not inv.error.startswith(case["error_prefix"])
            ):
                failures.append(f"refused/{case['name']}: {inv.error}")
    if n == 0:
        failures.append("dispatch.json enumerates nothing")
    return failures


def hold_cases(skill_text: str) -> list[str]:
    """The harness's operator text carries every sentence the protocol needs and none it
    forbids."""
    doc = json.loads((SHARED / "holds.json").read_text())
    failures: list[str] = []
    n = 0
    for must in doc["skill_must_say"]:
        n += 1
        if must not in skill_text:
            failures.append(f"skill must say: {must!r}")
    for never in doc["skill_must_not_say"]:
        n += 1
        if never in skill_text:
            failures.append(f"skill must not say: {never!r}")
    relay = doc["relay"]
    n += 1
    expected = (
        f"stringency review --verdict {relay['verdict']} --hold {relay['hold']} "
        f'--reason "{relay["words"]}" --attest'
    )
    if expected != relay["command"]:
        failures.append("relay command shape drifted in holds.json")
    if n == 0:
        failures.append("holds.json enumerates nothing")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--harness", required=True, help="the operator harness name, e.g. codex")
    ap.add_argument(
        "--skill",
        required=True,
        action="append",
        help="the skill the harness follows, and its appendix; repeatable, read together",
    )
    args = ap.parse_args()
    text = "\n".join(Path(p).read_text() for p in args.skill)
    failures = dispatch_cases(args.harness) + hold_cases(text)
    for f in failures:
        print(f"{args.harness}: {f}")
    print(f"{args.harness}: {'conforms' if not failures else f'{len(failures)} failure(s)'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
