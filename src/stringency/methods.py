"""The methods paragraph (design 12.3): the engine owns the structure and fills it from the
trace; the plugin supplies domain wording through `describe(action)`."""

from __future__ import annotations

import json
from typing import Any

from stringency import __version__
from stringency.runs import RunContext
from stringency.steps import action_from_row


def methods_paragraph(rc: RunContext, coverage: dict[str, Any]) -> str:
    store, run, project = rc.store, rc.run, rc.project
    sentences: list[str] = []
    sentences.append(
        f"Analysis was run with stringency {__version__} using the {project.pipeline.name} pipeline "
        f"v{project.pipeline.version} (commit {run['git_sha'][:7]}) under the {project.config.profile} profile "
        f"and policy {run['policy_version']}."
    )
    described: list[str] = []
    for step in project.pipeline.steps:
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        if st != "completed":
            continue
        row = store.one(
            "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
            (rc.run_id, step.id),
        )
        if row is None:
            continue
        action = action_from_row(row)
        m = project.modules.require(step.module).manifest
        text = project.plugin.describe(action).strip().rstrip(".")
        if m.kind == "judgment":
            j = next((x for x in coverage["judgment"] if x["step"] == step.id), None)
            invs = store.all(
                "SELECT DISTINCT model_resolved FROM invocations WHERE run_id=? AND step_id=?",
                (rc.run_id, step.id),
            )
            models = ", ".join(sorted(i["model_resolved"] for i in invs)) or "unknown"
            reviewers = store.all(
                "SELECT DISTINCT r.reviewer FROM reviews r JOIN holds h ON h.hold_id=r.hold_id WHERE h.run_id=? AND h.step_id=? AND r.verdict IN ('accept','override')",
                (rc.run_id, step.id),
            )
            if j:
                text += (
                    f" (model as recorded: {models}; {j['replicates']} independent replicates per item); "
                    f"{j['agreed']} of {j['items']} items were labelled unanimously"
                )
                resolved = j["accepted"] + j["override"]
                if resolved:
                    who = ", ".join(sorted(r["reviewer"] for r in reviewers)) or "the reviewer"
                    text += f" and {resolved} were resolved by reviewer {who} ({j['accepted']} accepted, {j['override']} corrected)"
        described.append(text)
    if described:
        joined = "; ".join(described)
        sentences.append(joined[0].upper() + joined[1:] + ".")
    g = coverage["gate"]
    n_flags = len(g["flags"])
    sentences.append(
        f"{_num(g['evaluated']).capitalize()} admissibility predicates were evaluated with {_num(g['fired']['block'])} blocks"
        + (f"; {_num(n_flags)} flags were reviewed." if n_flags else ".")
    )
    sentences.append(f"Run {rc.run_id}; environment digest {run['env_digest']}.")
    return " ".join(sentences) + "\n"


def _num(n: int) -> str:
    words = [
        "no",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
    ]
    return words[n] if 0 <= n < len(words) else str(n)


__all__ = ["methods_paragraph", "json"]
