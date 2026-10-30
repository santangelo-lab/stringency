"""Labels and lineage for open mode (open_mode_plan.md 2.5, 2026-10-16).

An answer's label is never stored on an artifact: it is derived when the answer is filed and
again at delivery by walking the cited artifact's lineage through the run's trace. `trusted`
only when every step on the path is a tool or a declared pipeline step, run by the engine,
under a verified environment, with a current control, and completed. `trusted data, drawn by
session code` (L140, 2026-10-29) when the path is trusted but for `exec` steps that only drew
figures from trusted inputs: each such exec's bound inputs are all trusted by this same rule,
its outputs are figures and one `figure_drawn` table, and every numeric cell of
`figure_drawn` matches a cell of one of its tabular inputs (`drawing_check`). Anything else,
any other exec included, is `untested`. One fixed-structure qualifier line beside the label
names what the words would hide: flags accepted on the path, parameters outside their range,
parameters the person set, the upstream delivery's environment status, the state of the
tools' controls, the untested inputs (a drawing exec named with its script), and the numerals
not checked.

Reads: artifacts, steps, actions, executions, holds, reviews, predicate_results, controls_runs,
step_events (through `RunContext.on_demand`), the files of a drawing exec's `figure_drawn` and
of its tabular inputs, and the upstream project's `prov/run.db` (executions, steps) read-only
for the `upstream` qualifier. Writes nothing.
"""

from __future__ import annotations

import bisect
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency.controls import current_for
from stringency.db.store import Store
from stringency.echo import OPEN_SWITCH
from stringency.exit_codes import ConfigError
from stringency.predicates.engine.judg import numeral_matches
from stringency.runs import RunContext
from stringency.tables import is_tabular, numeric_texts

TRUSTED = "trusted"
UNTESTED = "untested"
# the two-part label (L140): the numbers are a trusted artifact's, the drawing is session code
DRAWN = "trusted data, drawn by session code"
LABELS = (TRUSTED, DRAWN, UNTESTED)
# what a drawing exec writes beside its figures: the numbers each figure draws, one per cell
DRAWN_TABLE = "figure_drawn"

# The label sentences (open_mode_plan.md 1, "The pinned sentences"): printed by `answer`,
# relayed by the operator as written, held identical to the skills' copies by a test. The label
# is one of three (`LABELS`); an untested answer whose path holds no code was produced by a tool
# that missed a condition of `trusted`, and its sentence says which (`{why}`), never "code".
# Code is "code written for this question" and its sentence never says fail (L139).
UNTESTED_TOOL = "untested, tool"
LABEL_SENTENCES = {
    TRUSTED: (
        "Label: trusted. Produced by {tools}, a tool shipped with the method, run by the "
        "engine on {data}. Numbers checked against the cited cells: {matched} of {total}. "
        "Everything else in this answer is the assistant's reading."
    ),
    UNTESTED: (
        "Label: untested. Produced by code written for this question, run and recorded by the "
        "engine on {data}; no test or control has checked it. Numbers checked against the "
        "cited cells: {matched} of {total}. Everything else in this answer is the assistant's "
        "reading."
    ),
    DRAWN: (
        "Label: trusted data, drawn by session code. The numbers are {tables}, trusted; the "
        "drawing is code written in this session, which nothing has checked. Numbers checked "
        "against the cited cells: {matched} of {total}. Everything else in this answer is the "
        "assistant's reading."
    ),
    UNTESTED_TOOL: (
        "Label: untested. Produced by {tools}, a tool shipped with the method, run by the "
        "engine on {data}; {why}. Numbers checked against the cited cells: {matched} of "
        "{total}. Everything else in this answer is the assistant's reading."
    ),
}
# `{data}` in the label sentences: what the answer's path rests on
DATA_DELIVERED = "the delivered data"
DATA_PIPELINE_INPUTS = "the pipeline's inputs"
DATA_BOTH = "the delivered data and the pipeline's inputs"
# `{why}` in the tool sentence, by the first condition of `trusted` the path missed
WHY_UNTESTED = {
    "controls none": "no passing control is on record for it",
    "controls failed": "its control failed",
    "controls stale": "its last passing control ran under another environment",
    "env": "its environment was not verified",
    "runner": "it was not run by the engine",
    "status": "it did not complete",
}
# What the two words mean, in the words the operator says when first relevant (the operator
# skill's 10.7 "what trusted means" / "what untested means"); `report.md` prints them too, so
# the three copies are held identical by a test (2026-10-19).
TRUSTED_MEANS = (
    "Trusted means the engine ran a tool the method ships, in a verified environment, with a "
    "passing control on record, on the delivered data; the words around the numbers are still "
    "mine."
)
UNTESTED_MEANS = (
    "Untested means the engine ran code I wrote in this session and recorded it, but nothing "
    "has checked that the code computes what it claims; or it ran a tool the method ships that "
    "missed a condition of trusted, which the label names."
)
DRAWN_MEANS = (
    "Trusted data, drawn by session code means the engine ran a tool the method ships for every "
    "number on the figure, and the drawing itself is code written in this session: the engine "
    "checked that every number the figure draws is a cell of those trusted tables, and nothing has "
    "checked the drawing code beyond that."
)
# Said once, when the first answer lands, and once when the person says they are done
# (open mode, the report; 2026-10-19). Pinned with the rest by the same test.
REPORT_SENTENCE = (
    "Everything you ask goes into the report, on disk beside the results as it is answered, "
    "with its figures. Tell me whenever an answer is an important finding: it then goes into "
    "the report in full, at the top."
)
FINDINGS_SENTENCE = (
    "Which of these answers are important findings? Each one you name goes into the report in "
    "full, at the top, with its tables and figures; the others stay in the report in short. "
    "Name them by number, say all, or say none. If you want them in an order of your own, "
    "under headings in your words, or opened by a paragraph you write, tell me and the report "
    "will follow it."
)
QUALIFIER_LINE = (
    "flags accepted on the path: {flags} | parameters outside range: {ranges} | "
    "person-set parameters: {person} | upstream: {upstream} | controls: {controls} | "
    "untested inputs: {untested} | numerals not checked: {numerals}"
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
    upstream_input: dict[str, Any] | None = None  # kind input: an input of the upstream pipeline
    drawn: dict[str, Any] | None = None  # kind exec: `drawing_check` (L140)

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
    this run is walked. An exec fact carries `drawing_check` as `drawn` (L140). Reads:
    artifacts, steps, actions, executions, holds, reviews, predicate_results, controls_runs,
    and what `drawing_check` reads."""
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
        if fact.kind == "exec":
            fact.drawn = drawing_check(rc, sid)
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
                            upstream_input=item.upstream_input.model_dump()
                            if item.upstream_input
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
    verified environment, with a current control (tools) and completed; `trusted data, drawn by
    session code` when the path is trusted but for exec steps that each pass `drawing_check`
    and were themselves completed by the engine under a verified environment (L140); else
    `untested`."""
    if untested_reason(facts) is not None:
        return UNTESTED
    return DRAWN if any(f.kind == "exec" for f in facts) else TRUSTED


def is_drawing(f: StepFact) -> bool:
    """An exec step that drew figures from trusted numbers (`drawing_check` passed) and ran to
    completion on the engine under a verified environment."""
    return (
        f.kind == "exec"
        and bool((f.drawn or {}).get("drawing"))
        and f.status == "completed"
        and f.runner == "engine"
        and f.env_status == "verified"
    )


def untested_reason(facts: list[StepFact]) -> str | None:
    """The first condition of `trusted` the path misses: `exec` when code that is not a drawing
    (`is_drawing`) is on it (code outranks every other reason), else a key of `WHY_UNTESTED`;
    None when trusted, or trusted data drawn by session code."""
    steps = [f for f in facts if f.kind != "input"]
    if any(f.kind == "exec" and not is_drawing(f) for f in steps):
        return "exec"
    for f in steps:
        if f.status != "completed":
            return "status"
        if f.runner != "engine":
            return "runner"
        if f.env_status != "verified":
            return "env"
        if f.kind == "tool" and f.controls != "current":
            return f"controls {f.controls or 'none'}"
    return None


_numbers_cache: dict[tuple[str, int, int], list[float]] = {}


def _numbers_of(path: Path) -> list[float]:
    """The numeric cells of a table, sorted, read once per file state in a process."""
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _numbers_cache:
        _numbers_cache[key] = sorted(float(v) for v in numeric_texts(path))
    return _numbers_cache[key]


def _matches_any(written: str, values: list[float]) -> bool:
    """`written` matches a value by `numeral_matches` (the tolerance the numeral checks use:
    the value rounded to the precision written); `values` sorted, searched near `written`."""
    fw = float(written)
    if "e" in written.lower():
        width = abs(fw) * 1e-5 + 1e-12
    else:
        decimals = len(written.split(".", 1)[1]) if "." in written else 0
        width = 10.0**-decimals
    lo = bisect.bisect_left(values, fw - width)
    hi = bisect.bisect_right(values, fw + width)
    return any(numeral_matches(written, v) for v in values[lo:hi])


def _bound_inputs(rc: RunContext, step_id: str) -> list[dict[str, Any]] | None:
    """Each input the step's latest action bound: name, path, kind, the words naming it, and
    its own label by the path rule (a declared input is trusted; a produced artifact carries
    the label of its lineage). None when the step has no action. Reads: actions, artifacts and
    what `lineage` reads."""
    store = rc.store
    action = store.one(
        "SELECT inputs_json FROM actions WHERE run_id = ? AND step_id = ? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    if action is None:
        return None
    by_digest = {i.blake3: i for i in rc.project.inputs.items}
    out: list[dict[str, Any]] = []
    for name, digest in json.loads(action["inputs_json"] or "{}").items():
        bare = str(digest).removeprefix("blake3:")
        item = by_digest.get(bare)
        if item is not None:
            p = Path(item.path)
            out.append(
                {
                    "input": name,
                    "path": p if p.is_absolute() else rc.project.root / p,
                    "kind": item.type,
                    "words": f"the pipeline's input {item.name}"
                    if item.upstream_input
                    else f"the delivered {item.name}",
                    "label": TRUSTED,
                }
            )
            continue
        art = store.one(
            "SELECT artifact_id, step_id, name, kind, path FROM artifacts WHERE run_id = ? AND "
            "hash = ? AND status = 'produced' ORDER BY rowid DESC LIMIT 1",
            (rc.run_id, bare),
        )
        if art is None:
            out.append({"input": name, "path": None, "kind": None, "words": name, "label": None})
            continue
        up = lineage(rc, str(art["artifact_id"]))
        title = next((f.title or f.module for f in up if f.step_id == art["step_id"]), None)
        module = next((f.module for f in up if f.step_id == art["step_id"]), None)
        out.append(
            {
                "input": name,
                "path": Path(str(art["path"])),
                "kind": str(art["kind"]),
                "words": f"{art['name']} from {title} ({module})",
                "label": label_for(up),
            }
        )
    return out


def drawing_check(rc: RunContext, step_id: str) -> dict[str, Any]:
    """Whether an exec step only drew figures from trusted numbers (L140): its produced outputs
    are figures (kind `figure`) and one `figure_drawn` table; every bound input is trusted by
    the path rule (each input's own label); and every numeric cell of `figure_drawn` matches a
    cell of one of its tabular inputs by `numeral_matches` (the inputs read smallest first,
    stopping when every cell has matched). Returns `{drawing, why, script, cells, matched,
    tables}`: `why` the first condition missed, `tables` the inputs whose cells matched, in
    words. Reads: artifacts, actions, the step's `figure_drawn` and its tabular inputs' files,
    and what `lineage` reads for each produced input."""
    store = rc.store
    script = next(
        (
            str(p.relative_to(rc.project.root))
            for p in sorted(rc.project.step_dir(rc.run_id, step_id).glob("script.*"))
        ),
        f"runs/{rc.run_id}/{step_id}/script",
    )
    out: dict[str, Any] = {
        "drawing": False,
        "why": None,
        "script": script,
        "cells": 0,
        "matched": 0,
        "tables": [],
    }
    arts = store.all(
        "SELECT name, kind, path FROM artifacts WHERE run_id = ? AND step_id = ? AND "
        "status = 'produced' ORDER BY rowid",
        (rc.run_id, step_id),
    )
    drawn = [a for a in arts if a["name"] == DRAWN_TABLE]
    other = [a for a in arts if a["name"] != DRAWN_TABLE]
    if not drawn or drawn[0]["kind"] != "table":
        out["why"] = f"it writes no {DRAWN_TABLE} table"
        return out
    not_figures = [f"{a['name']} ({a['kind']})" for a in other if a["kind"] != "figure"]
    if not_figures or not other:
        out["why"] = (
            f"it writes {', '.join(not_figures)}, not a figure"
            if not_figures
            else "it draws no figure"
        )
        return out
    inputs = _bound_inputs(rc, step_id)
    if inputs is None:
        out["why"] = "it has no recorded action"
        return out
    untrusted = [i["input"] for i in inputs if i["label"] != TRUSTED]
    if untrusted:
        out["why"] = f"its input {', '.join(untrusted)} is not trusted"
        return out
    try:
        wanted = numeric_texts(Path(str(drawn[0]["path"])))
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        out["why"] = f"{DRAWN_TABLE} cannot be read ({e})"
        return out
    out["cells"] = len(wanted)
    if not wanted:
        out["why"] = f"{DRAWN_TABLE} holds no number"
        return out
    tabular = [
        i
        for i in inputs
        if i["path"] is not None and i["path"].is_file() and is_tabular(i["kind"], i["path"])
    ]
    tabular.sort(key=lambda i: i["path"].stat().st_size)
    left = list(dict.fromkeys(wanted))
    for i in tabular:
        if not left:
            break
        try:
            values = _numbers_of(i["path"])
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
        hit = [w for w in left if _matches_any(w, values)]
        if hit:
            out["tables"].append(i["words"])
            left = [w for w in left if w not in hit]
    out["matched"] = sum(1 for w in wanted if w not in left)
    if left:
        out["why"] = (
            f"{len(left)} number(s) of {DRAWN_TABLE} match no cell of its inputs "
            f"({', '.join(left[:5])})"
        )
        return out
    out["drawing"] = True
    return out


def data_phrase(facts: list[StepFact]) -> str:
    """`{data}` of the label sentences: the delivered data, the upstream pipeline's own inputs
    (bound beside the delivery since 2026-10-19), or both."""
    roots = [f for f in facts if f.kind == "input"]
    delivered = any(f.derived_from for f in roots)
    before = any(f.upstream_input for f in roots)
    if before and delivered:
        return DATA_BOTH
    return DATA_PIPELINE_INPUTS if before else DATA_DELIVERED


_upstream_cache: dict[str, str] = {}


def upstream_status(rc: RunContext, facts: list[StepFact]) -> str:
    """`verified` when every completed step of every upstream run the inputs came from ran
    under a verified environment; `as reported (<steps>)` naming the ones that did not;
    `pipeline inputs` when the path rests only on the upstream pipeline's own inputs; `none`
    when no input is a delivery; `unknown` when an upstream trace cannot be read. Reads the
    upstream project's `prov/run.db` read-only."""
    roots = [f for f in facts if f.kind == "input" and f.derived_from]
    if not roots:
        before = any(f.kind == "input" and f.upstream_input for f in facts)
        return "pipeline inputs" if before else "none"
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
    """The six path fields of the qualifier line, each `none` when empty; an answer adds the
    seventh, `numerals` (L142)."""
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
    elif any(f.controls == "failed" for f in tools):
        controls = "failed"
    elif any(f.controls == "stale" for f in tools):
        controls = "under another environment"
    else:
        controls = "none"
    untested = [
        f"{f.step_id} (drawing: {(f.drawn or {}).get('script')})" if is_drawing(f) else f.step_id
        for f in facts
        if f.kind == "exec"
    ]
    return {
        "flags": ", ".join(flags) or "none",
        "ranges": ", ".join(ranges) or "none",
        "person": ", ".join(person) or "none",
        "upstream": upstream_status(rc, facts),
        "controls": controls,
        "untested": ", ".join(untested) or "none",
    }


def render_qualifier(fields: dict[str, str]) -> str:
    """The qualifier line of an answer; `numerals` (L142) is the numerals the check left
    unchecked as not measurements, `none` when the fields carry none."""
    return QUALIFIER_LINE.format(**{"numerals": "none", **fields})


def drawn_tables(facts: list[StepFact]) -> str:
    """`{tables}` of the drawn label's sentence: the trusted inputs whose cells the drawings
    match, `the cells of X and Y`."""
    names = list(
        dict.fromkeys(t for f in facts if is_drawing(f) for t in (f.drawn or {}).get("tables", []))
    )
    return "the cells of " + (" and ".join(names) or "its inputs")


def label_sentence(label: str, facts: list[StepFact], matched: int, total: int) -> str:
    tools = [f for f in facts if f.kind in ("tool", "pipeline")]
    names = " and ".join(f"{f.title or f.step_id} ({f.module})" for f in tools) or "a tool"
    data = data_phrase(facts)
    if label == TRUSTED:
        return LABEL_SENTENCES[TRUSTED].format(tools=names, data=data, matched=matched, total=total)
    if label == DRAWN:
        return LABEL_SENTENCES[DRAWN].format(
            tables=drawn_tables(facts), matched=matched, total=total
        )
    why = untested_reason(facts)
    if why is None or why == "exec":
        return LABEL_SENTENCES[UNTESTED].format(data=data, matched=matched, total=total)
    return LABEL_SENTENCES[UNTESTED_TOOL].format(
        tools=names, data=data, why=WHY_UNTESTED[why], matched=matched, total=total
    )


def fit_facts(rc: RunContext, q: dict[str, Any], steps: list[str]) -> dict[str, Any]:
    """The fit of an answer (L139): the question's `wants` beside the `gives` of the steps that
    produced the cited artifacts (distinct, in citation order, joined with `; `), the line that
    shows them side by side, and `differs`: True when both are said and the texts differ
    after trimming (the only rule; no reading of the words), None when either is not said.
    Reads: questions (the row given), step_events (`created`, through `on_demand`)."""
    wants = str(q.get("wants") or "").strip() or None
    said = []
    for sid in dict.fromkeys(steps):
        entry = rc.on_demand_entry(sid) or {}
        g = str(entry.get("gives") or "").strip()
        if g and g not in said:
            said.append(g)
    gives = "; ".join(said) or None
    return {
        "wants": wants,
        "gives": gives,
        "differs": None if wants is None or gives is None else wants != gives,
        "line": fit_line(wants, gives),
    }


def fit_line(wants: str | None, gives: str | None) -> str:
    """`wants: <quantity> | gives: <quantity>`, `not said` for either left unsaid."""
    return f"wants: {wants or 'not said'} | gives: {gives or 'not said'}"


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
