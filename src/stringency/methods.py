"""The methods paragraph (design 12.3): the engine owns the structure and fills it from the
trace; the plugin supplies domain wording through `describe(action)`."""

from __future__ import annotations

import json
from typing import Any

from stringency import __version__
from stringency.runs import RunContext, captured_plugins
from stringency.steps import action_from_row
from stringency.when import skip_reason


def methods_paragraph(rc: RunContext, coverage: dict[str, Any]) -> str:
    store, run, project = rc.store, rc.run, rc.project
    sentences: list[str] = []
    plugin_version = captured_plugins(store, rc.run_id).get(project.plugin.name)
    with_plugin = f" (plugin {project.plugin.name} {plugin_version})" if plugin_version else ""
    # a project judged at a band of limits other than its profile's says so (L171)
    at_limits = f" at the policy's {project.config.limits} limits" if project.config.limits else ""
    if rc.open_ended:
        tools = ", ".join(m.ref for m in project.tools()) or "none"
        sentences.append(
            f"Questions were answered with stringency {__version__}{with_plugin} in open mode using the "
            f"tools of method {project.config.method.tag} ({tools}; commit {run['git_sha'][:7]}) under the "
            f"{project.config.profile} profile{at_limits} and policy {run['policy_version']}."
        )
    else:
        sentences.append(
            f"Analysis was run with stringency {__version__}{with_plugin} using the {project.pipeline.name} pipeline "
            f"v{project.pipeline.version} (commit {run['git_sha'][:7]}) under the {project.config.profile} profile{at_limits} "
            f"and policy {run['policy_version']}."
        )
    for name, added in project.added_inputs.items():
        # a person's file brought into the open project after init (L160)
        sentences.append(
            f"Input {name} was supplied by a person after the project was opened "
            f'("{added.get("source") or ""}"; blake3 {str(added.get("blake3") or "")[:12]}).'
        )
    for item in project.inputs.items:
        if item.derived_from is not None:
            d = item.derived_from
            where = f" (step {d.step_id}, output {d.output})" if d.step_id and d.output else ""
            sentences.append(
                f"Input {item.name} was delivered by stringency run {d.run_id}{where}."
            )
    described: list[str] = []
    not_run: list[str] = []
    for step in rc.pipeline.steps:
        st = store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, step.id)
        )
        if st == "skipped":
            reason = (skip_reason(store, rc.run_id, step.id) or "").removeprefix("skipped: ")
            title = rc.pipeline.title(step.id)
            not_run.append(
                f"{title} (step {step.id}) was not run" + (f": {reason}" if reason else "")
            )
            continue
        if st != "completed":
            continue
        row = store.one(
            "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
            (rc.run_id, step.id),
        )
        if row is None:
            continue
        action = action_from_row(row)
        m = rc.module_for(step.id).manifest
        entry = rc.on_demand_entry(step.id)
        if entry is not None and entry.get("kind") == "exec":
            # the engine's own sentence: a plugin describes its operations, not a session script
            blob = store.scalar(
                "SELECT script_blob FROM executions WHERE action_id=? ORDER BY rowid DESC LIMIT 1",
                (action.action_id,),
            )
            described.append(
                f"a script written in the session (blake3 {str(blob or '')[:12]}) was run by the engine "
                f"in environment {m.env} and its outputs were recorded untested (step {step.id})"
            )
            continue
        text = project.plugin.describe(action).strip().rstrip(".")
        if m.kind == "judgment":
            j = next((x for x in coverage["judgment"] if x["step"] == step.id), None)
            invs = store.all(
                "SELECT DISTINCT model_resolved FROM invocations WHERE run_id=? AND step_id=?",
                (rc.run_id, step.id),
            )
            models = ", ".join(sorted(i["model_resolved"] for i in invs)) or "unknown"
            reviewers = store.all(
                "SELECT DISTINCT r.reviewer, r.via, r.operator_harness FROM reviews r JOIN holds h ON h.hold_id=r.hold_id WHERE h.run_id=? AND h.step_id=? AND r.verdict IN ('accept','override')",
                (rc.run_id, step.id),
            )
            if j:
                text += (
                    f" (model as recorded: {models}; {j['replicates']} replicates per item, each in a separate context); "
                    f"{j['agreed']} of {j['items']} items were labelled unanimously"
                )
                resolved = j["accepted"] + j["override"]
                if resolved:
                    from stringency.review import policy_of

                    people = sorted({r["reviewer"] for r in reviewers if r["via"] != "policy"})
                    policies = sorted(
                        {str(policy_of(r)) for r in reviewers if r["via"] == "policy"}
                    )
                    by = [f"reviewer {', '.join(people)}"] if people else []
                    if policies:
                        # a fixed policy's verdict is never worded as a person's (L162)
                        by.append(
                            f"the fixed policy {', '.join(policies)}, with no person's review"
                        )
                    who = " and ".join(by) or "the reviewer"
                    text += f" and {resolved} were resolved by {who} ({j['accepted']} accepted, {j['override']} corrected)"
        described.append(text)
    if described:
        joined = "; ".join(described)
        sentences.append(joined[0].upper() + joined[1:] + ".")
    sentences += _tool_sources(rc)
    for s in not_run:
        sentences.append(s[0].upper() + s[1:] + ".")
    g = coverage["gate"]
    n_flags = len(g["flags"])
    sentences.append(
        f"{_num(g['evaluated']).capitalize()} admissibility predicates were evaluated with {_num(g['fired']['block'])} blocks"
        + (f"; {_num(n_flags)} flags were reviewed." if n_flags else ".")
    )
    sentences.append(f"Run {rc.run_id}; environment digest {run['env_digest']}.")
    return " ".join(sentences) + "\n"


def number_word(n: int) -> str:
    """Counts spelled out up to ninety-nine (a count may open a sentence)."""
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
    if 0 <= n < len(words):
        return words[n]
    tens = {
        20: "twenty",
        30: "thirty",
        40: "forty",
        50: "fifty",
        60: "sixty",
        70: "seventy",
        80: "eighty",
        90: "ninety",
    }
    if 20 < n < 100:
        # the count opens a sentence, so it is spelled out up to ninety-nine
        return tens[n - n % 10] + ("" if n % 10 == 0 else "-" + words[n % 10])
    return str(n)


_num = number_word

__all__ = ["methods_paragraph", "number_word", "json"]


def _tool_sources(rc: RunContext) -> list[str]:
    """One sentence per tool that ran in an open run and whose method entry names its sources
    (`cites`, L175), in the order the tools first ran. Reads: step_events (the on-demand steps),
    steps, the method's skill files."""
    if not rc.open_ended:
        return []
    from stringency.present import Site
    from stringency.tools import tool_sources

    ran: list[str] = []
    for entry in rc.on_demand():
        if entry.get("kind") != "tool":
            continue
        st = rc.store.scalar(
            "SELECT status FROM steps WHERE run_id=? AND step_id=?", (rc.run_id, entry["step_id"])
        )
        ref = str((entry.get("decl") or {}).get("module") or "")
        if st == "completed" and ref and ref not in ran:
            ran.append(ref)
    if not ran:
        return []
    cites = tool_sources(Site(rc.project.root, rc.project.config, rc.store, rc.pipeline))
    return [
        f"The method names the sources of {ref}: {'; '.join(cites[ref.split('@')[0]])}."
        for ref in ran
        if ref.split("@")[0] in cites
    ]
