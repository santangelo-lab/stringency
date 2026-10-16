"""Labels and lineage for open mode (open_mode_plan.md 2.5, 2026-10-16).

An answer's label is never stored on an artifact: it is derived when the answer is filed and
again at delivery by walking the cited artifact's lineage through the run's trace. `trusted`
only when every step on the path is a tool or a declared pipeline step, run by the engine,
under a verified environment, with a current control, and completed; anything else, one exec
anywhere included, is `untested`. One fixed-structure qualifier line beside the label names
what the two words would hide: flags accepted on the path, parameters outside their range,
parameters the person set, the upstream delivery's environment status, the state of the
tools' controls, and the untested inputs.

Reads: artifacts, steps, actions, executions, holds, reviews, predicate_results, controls_runs,
step_events (through `RunContext.on_demand`), and the upstream project's `prov/run.db`
(executions, steps) read-only for the `upstream` qualifier. Writes nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.controls import current_for
from stringency.db.store import Store
from stringency.echo import OPEN_SWITCH
from stringency.exit_codes import ConfigError
from stringency.runs import RunContext

TRUSTED = "trusted"
UNTESTED = "untested"

# The two label sentences (open_mode_plan.md 1, "The pinned sentences"): printed by `answer`,
# relayed by the operator as written, held identical to the skills' copies by a test.
LABEL_SENTENCES = {
    TRUSTED: (
        "Label: trusted. Produced by {tools}, a tool shipped with the method, run by the "
        "engine on the delivered data. Numbers checked against the cited cells: {matched} of "
        "{total}. Everything else in this answer is the assistant's reading."
    ),
    UNTESTED: (
        "Label: untested. Produced by code written in this session, run and recorded by the "
        "engine on the delivered data; no test or control has checked it. Numbers checked "
        "against the cited cells: {matched} of {total}. Everything else in this answer is the "
        "assistant's reading."
    ),
}
QUALIFIER_LINE = (
    "flags accepted on the path: {flags} | parameters outside range: {ranges} | "
    "person-set parameters: {person} | upstream: {upstream} | controls: {controls} | "
    "untested inputs: {untested}"
)
SWITCH = OPEN_SWITCH


@dataclass
class StepFact:
    """What the label and the qualifier are derived from, per step on the path."""

    step_id: str
    kind: str  # tool | exec | pipeline | input
    module: str | None = None
    title: str | None = None
    status: str | None = None
    runner: str | None = None
    env_status: str | None = None
    controls: str | None = None  # current | stale | none (tools only)
    holds: list[dict[str, Any]] = field(default_factory=list)
    param_sources: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    out_of_range: list[str] = field(default_factory=list)
    input_name: str | None = None  # kind input: the declared input
    derived_from: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], {})}


def _artifact(store: Store, run_id: str, artifact_id: str) -> Any:
    return store.one(
        "SELECT * FROM artifacts WHERE run_id = ? AND artifact_id = ?", (run_id, artifact_id)
    )


def _step_fact(rc: RunContext, step_id: str) -> StepFact:
    store = rc.store
    entry = rc.on_demand_entry(step_id)
    kind = str(entry["kind"]) if entry is not None else "pipeline"
    status = store.scalar(
        "SELECT status FROM steps WHERE run_id = ? AND step_id = ?", (rc.run_id, step_id)
    )
    fact = StepFact(step_id=step_id, kind=kind, status=status)
    try:
        decl = rc.decl(step_id)
        fact.module, fact.title = decl.module, decl.title or step_id
    except ConfigError:
        fact.module = store.scalar(
            "SELECT module || '@' || module_version FROM steps WHERE run_id=? AND step_id=?",
            (rc.run_id, step_id),
        )
    action = store.one(
        "SELECT * FROM actions WHERE run_id = ? AND step_id = ? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    if action is not None:
        fact.param_sources = json.loads(action["param_source_json"] or "{}")
        fact.params = json.loads(action["params_json"] or "{}")
        ex = store.one(
            "SELECT runner, env_status FROM executions WHERE action_id = ? ORDER BY rowid DESC LIMIT 1",
            (action["action_id"],),
        )
        if ex is not None:
            fact.runner, fact.env_status = ex["runner"], ex["env_status"]
        for r in store.all(
            "SELECT evidence_json FROM predicate_results WHERE action_id = ? AND "
            "predicate_id = 'param.out_of_range' AND fired = 1",
            (action["action_id"],),
        ):
            ev = json.loads(r["evidence_json"] or "{}")
            fact.out_of_range += [
                f"{k}={v.get('proposed')}" for k, v in dict(ev.get("out_of_range", {})).items()
            ]
    for h in store.all(
        "SELECT h.hold_id, h.kind, h.context_json, r.verdict, r.reviewer, r.via FROM holds h "
        "LEFT JOIN reviews r ON r.review_id = h.resolved_by_review "
        "WHERE h.run_id = ? AND h.step_id = ? ORDER BY h.created, h.rowid",
        (rc.run_id, step_id),
    ):
        ctx = json.loads(h["context_json"] or "{}")
        fact.holds.append(
            {
                "hold_id": h["hold_id"],
                "kind": h["kind"],
                "predicate": ctx.get("predicate"),
                "verdict": h["verdict"],
                "reviewer": h["reviewer"],
                "via": h["via"],
            }
        )
    if kind == "tool":
        module = rc.module_for(step_id)
        fact.controls = current_for(store, module, rc.env_digests.get(module.manifest.env))[
            "status"
        ]
    return fact


def lineage(rc: RunContext, artifact_id: str) -> list[StepFact]:
    """Every step between the declared inputs and `artifact_id`, nearest first, then the
    inputs it rests on as `input` facts. An artifact's step's latest action names its inputs
    by digest; a digest that is a declared input is a root, one that is a produced artifact of
    this run is walked. Reads: artifacts, steps, actions, executions, holds, reviews,
    predicate_results, controls_runs."""
    store = rc.store
    art = _artifact(store, rc.run_id, artifact_id)
    if art is None:
        raise ConfigError(f"no artifact {artifact_id} in run {rc.run_id}")
    inputs_by_digest = {i.blake3: i for i in rc.project.inputs.items}
    facts: list[StepFact] = []
    seen_steps: set[str] = set()
    seen_inputs: set[str] = set()
    frontier = [str(art["step_id"])]
    while frontier:
        sid = frontier.pop(0)
        if sid in seen_steps:
            continue
        seen_steps.add(sid)
        fact = _step_fact(rc, sid)
        facts.append(fact)
        action = store.one(
            "SELECT inputs_json FROM actions WHERE run_id = ? AND step_id = ? ORDER BY attempt DESC, rowid DESC LIMIT 1",
            (rc.run_id, sid),
        )
        if action is None:
            continue
        for digest in json.loads(action["inputs_json"] or "{}").values():
            bare = str(digest).removeprefix("blake3:")
            item = inputs_by_digest.get(bare)
            if item is not None:
                if item.name not in seen_inputs:
                    seen_inputs.add(item.name)
                    facts.append(
                        StepFact(
                            step_id=f"input:{item.name}",
                            kind="input",
                            input_name=item.name,
                            derived_from=item.derived_from.model_dump()
                            if item.derived_from
                            else None,
                        )
                    )
                continue
            producer = store.one(
                "SELECT step_id FROM artifacts WHERE run_id = ? AND hash = ? AND status = 'produced' "
                "ORDER BY rowid DESC LIMIT 1",
                (rc.run_id, bare),
            )
            if producer is not None:
                frontier.append(str(producer["step_id"]))
    return facts


def label_for(facts: list[StepFact]) -> str:
    """`trusted` when every step on the path is a tool or a declared step, engine-run, under a
    verified environment, with a current control (tools) and completed; else `untested`."""
    for f in facts:
        if f.kind == "input":
            continue
        if f.kind == "exec":
            return UNTESTED
        if f.status != "completed" or f.runner != "engine" or f.env_status != "verified":
            return UNTESTED
        if f.kind == "tool" and f.controls != "current":
            return UNTESTED
    return TRUSTED


_upstream_cache: dict[str, str] = {}


def upstream_status(rc: RunContext, facts: list[StepFact]) -> str:
    """`verified` when every completed step of every upstream run the inputs came from ran
    under a verified environment; `as reported (<steps>)` naming the ones that did not;
    `none` when no input is a delivery; `unknown` when an upstream trace cannot be read.
    Reads the upstream project's `prov/run.db` read-only."""
    roots = [f for f in facts if f.kind == "input" and f.derived_from]
    if not roots:
        return "none"
    as_reported: list[str] = []
    unknown = False
    for f in roots:
        d = f.derived_from or {}
        project, run_id = str(d.get("project") or ""), str(d.get("run_id") or "")
        key = f"{project}:{run_id}"
        if key in _upstream_cache:
            text = _upstream_cache[key]
        else:
            text = _read_upstream(Path(project), run_id)
            _upstream_cache[key] = text
        if text == "unknown":
            unknown = True
        elif text:
            as_reported += [f"{run_id[:8]}:{s}" for s in text.split(",")]
    if unknown:
        return "unknown"
    return f"as reported ({', '.join(as_reported)})" if as_reported else "verified"


def _read_upstream(project: Path, run_id: str) -> str:
    """The upstream run's completed steps not executed under a verified environment, comma
    separated; '' when all were; 'unknown' when the trace cannot be read."""
    db = project / "prov" / "run.db"
    if not project or not db.exists():
        return "unknown"
    try:
        with Store.open(db, create=False) as up:
            rows = up.all(
                "SELECT s.step_id, e.env_status FROM steps s JOIN actions a ON a.run_id = s.run_id "
                "AND a.step_id = s.step_id JOIN executions e ON e.action_id = a.action_id "
                "WHERE s.run_id = ? AND s.status = 'completed' AND e.rowid IN "
                "(SELECT MAX(rowid) FROM executions GROUP BY action_id)",
                (run_id,),
            )
    except Exception:  # noqa: BLE001  (an unreadable upstream is reported as unknown)
        return "unknown"
    return ",".join(sorted({r["step_id"] for r in rows if r["env_status"] != "verified"}))


def qualifier(rc: RunContext, facts: list[StepFact]) -> dict[str, str]:
    """The six fields of the qualifier line, each `none` when empty."""
    flags = [
        f"{f.step_id}:{(h.get('predicate') or h.get('kind') or '').split('@')[0]}"
        for f in facts
        for h in f.holds
        if h.get("kind") == "flag" and h.get("verdict") in ("accept", "override")
    ]
    ranges = [f"{f.step_id}.{x}" for f in facts for x in f.out_of_range]
    person = [
        f"{f.step_id}.{k}={f.params.get(k)}"
        for f in facts
        for k, src in f.param_sources.items()
        if src == "person"
    ]
    tools = [f for f in facts if f.kind == "tool"]
    if not tools:
        controls = "none"
    elif all(f.controls == "current" for f in tools):
        controls = "current"
    elif any(f.controls == "stale" for f in tools):
        controls = "under another environment"
    else:
        controls = "none"
    untested = [f.step_id for f in facts if f.kind == "exec"]
    return {
        "flags": ", ".join(flags) or "none",
        "ranges": ", ".join(ranges) or "none",
        "person": ", ".join(person) or "none",
        "upstream": upstream_status(rc, facts),
        "controls": controls,
        "untested": ", ".join(untested) or "none",
    }


def render_qualifier(fields: dict[str, str]) -> str:
    return QUALIFIER_LINE.format(**fields)


def label_sentence(label: str, facts: list[StepFact], matched: int, total: int) -> str:
    tools = [f for f in facts if f.kind in ("tool", "pipeline")]
    names = " and ".join(f"{f.title or f.step_id} ({f.module})" for f in tools) or "a tool"
    return LABEL_SENTENCES[label].format(tools=names, matched=matched, total=total)


def block_for(rc: RunContext, artifact_id: str) -> dict[str, Any]:
    """The provenance block of one artifact (backlog L35; `index.json` `files[].provenance`):
    its label, the steps on its path with what each contributed, and the qualifier fields."""
    facts = lineage(rc, artifact_id)
    return {
        "artifact_id": artifact_id,
        "label": label_for(facts),
        "lineage": [f.to_json() for f in facts],
        "qualifier": qualifier(rc, facts),
    }
