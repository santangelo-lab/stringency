"""Answers (open_mode_plan.md 2.5, 2026-10-16): the operator's reply text, filed against the
artifacts and cells it cites, gated before it is recorded.

`file_answer` resolves every `--cite` against this run's produced artifacts of completed
steps, loads the cited tables, takes the cited rows and columns (else every cell) as the
numerals the text may use (a row by its key, the key columns' values joined with `|` as
`present` prints it, L138; a numeral that is not a measurement is left unchecked and named in
the qualifier, L142), builds a synthetic `answer` action and an `OutputBundle` whose prose
is the text, evaluates the `ans.*` predicates (invariant: a cited id that does not exist, a
numeral matching no cited cell, the label written by the operator), derives the label from the
cited artifacts' lineage, and writes the `answers` row, admissible or blocked. A blocked answer
is kept, as a rejected proposal is. A figure attached with `--figure` (L143) is stored in the
answer's `provenance_json` under `figures`, each with its own label derived from its own
lineage; it does not enter the answer's label or the numeral check.

Reads: artifacts, steps, questions, and everything `provenance.lineage` reads. Writes:
messages (the text), predicate_results (the `ans.*` verdicts, action id = the answer id),
answers, run_events (`answer_recorded`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stringency import hashing
from stringency.actions import Action
from stringency.clock import now_iso
from stringency.exit_codes import ConfigError, RefusedError
from stringency.gate import GateResult, evaluate
from stringency.ids import new_id
from stringency.predicates import registry
from stringency.predicates.context import EvidenceTable, OutputBundle
from stringency.predicates.engine.ans import classify_numerals, numeral_sources
from stringency.provenance import (
    TRUSTED,
    WHY_UNTESTED,
    data_phrase,
    label_for,
    label_sentence,
    lineage,
    qualifier,
    render_qualifier,
    untested_reason,
)
from stringency.questions import question
from stringency.runs import RunContext
from stringency.tables import KEY_SEP, is_tabular, key_form, load_table, nearest_keys

# `<artifact id>[:<row key>[:<column>]]`; a row key is its key columns' values joined with `|`
# (`1|domain_4`), so `|` is part of the row and only `:` separates (L138)
CITE = re.compile(r"^(?P<id>[0-9A-HJKMNP-TV-Z]{26})(?::(?P<row>[^:]*))?(?::(?P<col>.*))?$")
CITE_FORM = "<artifact id>[:<k1>|<k2>[:<column>]]"


@dataclass
class Cite:
    artifact_id: str
    row: str | None = None
    column: str | None = None

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {"artifact_id": self.artifact_id}
        if self.row is not None:
            d["row"] = self.row
        if self.column is not None:
            d["column"] = self.column
        return d


@dataclass
class AnswerResult:
    answer_id: str
    question_id: str
    status: str  # admissible | blocked
    label: str
    sentence: str
    qualifier: str
    gate: GateResult
    cited: list[dict[str, Any]]
    cells: dict[str, dict[str, dict[str, Any]]]  # artifact id -> row -> {column: value}
    missing: list[str]
    matched: int
    total: int
    provenance: dict[str, Any]
    cite_help: list[dict[str, Any]]
    not_checked: list[dict[str, str]]
    failed: list[dict[str, str]]
    figures: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "stringency.answer/1",
            "answer_id": self.answer_id,
            "question_id": self.question_id,
            "status": self.status,
            "label": self.label,
            "label_sentence": self.sentence,
            "qualifier": self.qualifier,
            "cited": self.cited,
            "cells": self.cells,
            "missing": self.missing,
            "numerals": {
                "matched": self.matched,
                "total": self.total,
                "not_checked": self.not_checked,
                "failed": self.failed,
            },
            "blocked": [r.line() for r in self.gate.blocked],
            **({"cite_help": self.cite_help} if self.cite_help else {}),
            "figures": self.figures,
            "provenance": self.provenance,
        }


def parse_cite(text: str) -> Cite:
    m = CITE.match(text.strip())
    if not m:
        raise ConfigError(
            f"--cite expects {CITE_FORM}, the row by its key columns' values joined with "
            f"{KEY_SEP} as present prints it, got {text!r}"
        )
    return Cite(m.group("id"), m.group("row") or None, m.group("col") or None)


def _citable(rc: RunContext, cite: Cite) -> Any:
    """The artifact row when it is a produced output of a completed step of this run."""
    return rc.store.one(
        "SELECT a.* FROM artifacts a JOIN steps s ON s.run_id = a.run_id AND s.step_id = a.step_id "
        "WHERE a.run_id = ? AND a.artifact_id = ? AND a.status = 'produced' AND s.status = 'completed'",
        (rc.run_id, cite.artifact_id),
    )


@dataclass
class Cited:
    """What the citations of one answer resolve to."""

    tables: dict[str, EvidenceTable]  # artifact id -> the cited cells as an evidence table
    cells: dict[str, dict[str, dict[str, Any]]]  # artifact id -> row key -> {column: value}
    missing: list[str]
    help: list[dict[str, Any]]  # per missed row or column: the key form and the nearest keys
    keys: dict[str, str]  # artifact id -> the key columns' names joined with `|`
    key_values: list[str]  # every key column's value of the cited rows
    steps: dict[str, str]  # artifact id -> the step that produced it


def declared_key(rc: RunContext, step_id: str, output: str) -> list[str] | None:
    """The key the producing module declares for an output (`outputs.<name>.key`), if any."""
    try:
        spec = rc.module_for(step_id).manifest.outputs.get(output)
    except Exception:  # noqa: BLE001  (a step with no module resolves by the prefix rule)
        return None
    return list(spec.key) if spec is not None and spec.key else None


def cited_cells(rc: RunContext, cites: list[Cite]) -> Cited:
    """The cited cells by artifact id, as evidence tables and as plain values, with the
    citations that resolve to nothing. A non-table artifact is citable and contributes no
    cells; a row or column that is not in the table counts as missing, and its help names the
    key form of the table and up to five keys nearest the miss. A citation without a row takes
    every row. Reads: artifacts, steps; the cited files."""
    out = Cited({}, {}, [], [], {}, [], {})
    for c in cites:
        art = _citable(rc, c)
        if art is None:
            out.missing.append(c.artifact_id)
            continue
        aid = c.artifact_id
        out.steps[aid] = str(art["step_id"])
        if not is_tabular(str(art["kind"]), str(art["path"])):
            if c.row is not None or c.column is not None:
                out.missing.append(f"{aid}:{c.row or ''}:{c.column or ''}")
            continue
        key = declared_key(rc, str(art["step_id"]), str(art["name"]))
        try:
            full = load_table(Path(art["path"]), str(art["name"]), key=key)
        except ConfigError:  # a declared key the table lacks: the prefix rule
            full = load_table(Path(art["path"]), str(art["name"]))
        out.keys[aid] = full.key_column
        rows = full.rows if c.row is None else {c.row: full.rows.get(c.row)}
        picked: dict[str, dict[str, Any]] = {}
        for k, row in rows.items():
            if row is None:
                out.missing.append(f"{aid}:{k}")
                out.help.append(_help(full, f"{aid}:{k}", k))
                continue
            out.key_values += [str(row[col]) for col in full.key_columns if col in row]
            if c.column is None:
                picked[k] = dict(row)
            elif c.column in row:
                picked[k] = {c.column: row[c.column]}
            else:
                out.missing.append(f"{aid}:{k}:{c.column}")
                out.help.append(
                    {**_help(full, f"{aid}:{k}:{c.column}", None), "columns": list(full.columns)}
                )
        prior = out.cells.get(aid, {})
        for k, row in picked.items():
            prior.setdefault(k, {}).update(row)
        out.cells[aid] = prior
        out.tables[aid] = EvidenceTable(
            name=str(art["name"]),
            key_column=full.key_column,
            columns=full.columns,
            rows=prior,
            key_columns=full.key_columns,
        )
    return out


def _help(table: EvidenceTable, cite: str, miss: str | None) -> dict[str, Any]:
    """How a row of `table` is cited, and its keys nearest `miss` (none for a column miss)."""
    return {
        "cite": cite,
        "table": table.name,
        "key_columns": list(table.key_columns),
        "form": f"<id>:{key_form(table)}[:<column>]",
        "near": nearest_keys(list(table.rows), miss) if miss is not None else [],
    }


def figure_line(label: str, facts: list[Any]) -> str:
    """The sentence beside an attached figure (L143): its own label word and what drew it, in
    the label sentences' terms, without the numeral count (a figure's numbers are not checked)."""
    tools = [f for f in facts if f.kind in ("tool", "pipeline")]
    names = " and ".join(f"{f.title or f.step_id} ({f.module})" for f in tools) or "a tool"
    data = data_phrase(facts)
    if label == TRUSTED:
        return (
            f"Figure label: trusted. Drawn by {names}, a tool shipped with the method, run by "
            f"the engine on {data}."
        )
    why = untested_reason(facts)
    if why is None or why == "exec":
        return (
            "Figure label: untested. Drawn by code written in this session, run and recorded "
            f"by the engine on {data}; no test or control has checked it."
        )
    return (
        f"Figure label: untested. Drawn by {names}, a tool shipped with the method, run by the "
        f"engine on {data}; {WHY_UNTESTED[why]}."
    )


def attached_figures(rc: RunContext, figure_ids: list[str]) -> list[dict[str, Any]]:
    """The figures `answer --figure` attaches (L143), each a produced figure of a completed
    step of this run (exit 15 otherwise), with its own label from its own lineage
    (`provenance.label_for`), never the answer's. Reads: artifacts, steps, and everything
    `provenance.lineage` reads."""
    out: list[dict[str, Any]] = []
    for fid in dict.fromkeys(f.strip() for f in figure_ids):
        art = _citable(rc, Cite(fid))
        if art is None:
            raise ConfigError(
                f"--figure {fid}: not a produced artifact of a completed step of run {rc.run_id}"
            )
        if str(art["kind"]) != "figure":
            raise ConfigError(
                f"--figure {fid}: {art['name']} is a {art['kind']}, not a figure; cite it with --cite"
            )
        facts = lineage(rc, fid)
        label = label_for(facts)
        out.append(
            {
                "artifact_id": fid,
                "name": str(art["name"]),
                "step_id": str(art["step_id"]),
                "path": str(art["path"]),
                "label": label,
                "label_line": figure_line(label, facts),
                "lineage": [f.to_json() for f in facts],
            }
        )
    return out


def file_answer(
    rc: RunContext,
    question_id: str,
    text: str,
    cites: list[Cite],
    figures: list[str] | None = None,
) -> AnswerResult:
    """File one answer, with the figures `--figure` attaches (L143) stored in the answer's
    `provenance_json` under `figures`. Writes: messages, predicate_results, answers,
    run_events."""
    if not rc.open_ended:
        raise ConfigError("answers are filed on an open project's run only")
    q = question(rc, question_id)  # must be a question of this run
    words = text.strip()
    if not words:
        raise ConfigError("an answer needs text")
    if not cites:
        raise ConfigError("an answer cites at least one artifact (--cite <artifact id>)")
    attached = attached_figures(rc, list(figures or []))
    store = rc.store
    cited = cited_cells(rc, cites)
    tables, cells, missing = cited.tables, cited.cells, cited.missing
    present_ids = [c.artifact_id for c in cites if c.artifact_id not in missing]
    facts = []
    seen: set[str] = set()
    for aid in dict.fromkeys(present_ids):
        for f in lineage(rc, aid):
            if f.step_id not in seen:
                seen.add(f.step_id)
                facts.append(f)
    label = label_for(facts) if present_ids else "untested"
    quals = qualifier(rc, facts)
    producing = set(cited.steps.values())
    src = {
        "key": cited.key_values,
        "param": [str(v) for f in facts if f.step_id in producing for v in f.params.values()],
        "question": str(q["text"] or ""),
    }
    values = [v for rows in cells.values() for row in rows.values() for v in row.values()]
    classes = classify_numerals(
        words, values, numeral_sources(rc.project.design, {"numeral_sources": src})
    )
    matched = len(classes["matched"])
    total = matched + len(classes["failed"])
    not_checked = classes["exempt"]
    quals["numerals"] = ", ".join(n["numeral"] for n in not_checked) or "none"
    answer_id = new_id()
    action = Action(
        action_id=answer_id,
        run_id=rc.run_id,
        step_id="answer",
        attempt=0,
        operation="answer",
        module="answer",
        parameters={},
        param_source={},
        inputs={},
        input_digest=hashing.prefixed(hashing.hash_json([c.to_json() for c in cites])),
        params_hash=hashing.prefixed(hashing.hash_json({})),
        proposed_by="agent",
    )
    bundle = OutputBundle(
        outputs={},
        prose=words,
        evidence_tables=tables,
        observed={
            "cited": [c.to_json() for c in cites],
            "missing": missing,
            "cite_help": cited.help,
            "numeral_sources": src,
            "label": label,
            "qualifier": quals,
        },
    )
    gate = evaluate(
        rc.gate_context("post", action, rc.current_state(), bundle),
        registry=registry,
        store=store,
        policy_digest=rc.policy_digest,
        module=None,
        runner=None,
        only=[s for s in registry.all() if s.id.startswith("ans.")],
    )
    status = "blocked" if gate.blocked else "admissible"
    sentence = label_sentence(label, facts, matched, total)
    provenance = {
        "label": label,
        "label_sentence": sentence,
        "qualifier": quals,
        "qualifier_line": render_qualifier(quals),
        "lineage": [f.to_json() for f in facts],
        "cited": [c.to_json() for c in cites],
        "cells": cells,
        "keys": cited.keys,
        "numerals": {"matched": matched, "total": total, "not_checked": not_checked},
        "route": "code" if any(f.kind == "exec" for f in facts) else "tool",
        "tools": [f.module for f in facts if f.kind == "tool"],
        "decisions": [
            {"step": f.step_id, "param": k, "value": f.params.get(k), "source": src}
            for f in facts
            if f.kind in ("tool", "exec")
            for k, src in f.param_sources.items()
        ],
        "figures": attached,
    }
    ref = hashing.hash_text(words)
    store.store_message(ref, words)
    store.insert(
        "answers",
        {
            "answer_id": answer_id,
            "run_id": rc.run_id,
            "question_id": question_id,
            "text_ref": ref,
            "cited_json": [c.to_json() for c in cites],
            "label": label if status == "admissible" else None,
            "provenance_json": provenance,
            "status": status,
            "ts": now_iso(),
        },
    )
    store.run_event(
        rc.run_id,
        "answer_recorded",
        {"answer_id": answer_id, "question_id": question_id, "status": status, "label": label},
    )
    return AnswerResult(
        answer_id=answer_id,
        question_id=question_id,
        status=status,
        label=label,
        sentence=sentence,
        qualifier=render_qualifier(quals),
        gate=gate,
        cited=[c.to_json() for c in cites],
        cells=cells,
        missing=missing,
        matched=matched,
        total=total,
        provenance=provenance,
        cite_help=cited.help,
        not_checked=not_checked,
        failed=classes["failed"],
        figures=attached,
    )


def file_unanswerable(rc: RunContext, question_id: str, reason: str) -> dict[str, Any]:
    """`answer --cannot` (backlog L60): the operator cannot answer the question from the
    delivery. Writes one `answers` row with `status: unanswerable`, no label, no citation, the
    reason as its text (stored in `messages`), and an `answer_recorded` run event; no predicate
    runs. Refused when the question is not this run's or the reason is empty."""
    store = rc.store
    if not reason.strip():
        raise ConfigError("--cannot needs --reason with a sentence")
    q = store.one(
        "SELECT question_id FROM questions WHERE run_id = ? AND question_id = ?",
        (rc.run_id, question_id),
    )
    if q is None:
        raise RefusedError(f"question {question_id} is not on run {rc.run_id}")
    answer_id = new_id()
    ref = hashing.hash_text(reason)
    store.store_message(ref, reason)
    store.insert(
        "answers",
        {
            "answer_id": answer_id,
            "run_id": rc.run_id,
            "question_id": question_id,
            "text_ref": ref,
            "cited_json": [],
            "label": None,
            "provenance_json": {"route": "none", "reason": reason},
            "status": "unanswerable",
            "ts": now_iso(),
        },
    )
    store.run_event(
        rc.run_id,
        "answer_recorded",
        {
            "answer_id": answer_id,
            "question_id": question_id,
            "status": "unanswerable",
            "label": None,
        },
    )
    return {
        "answer_id": answer_id,
        "question_id": question_id,
        "status": "unanswerable",
        "label": None,
        "reason": reason,
    }


def answer_row(rc: RunContext, answer_id: str) -> dict[str, Any]:
    """Reads: answers, questions, messages."""
    row = rc.store.one(
        "SELECT * FROM answers WHERE run_id = ? AND answer_id = ?", (rc.run_id, answer_id)
    )
    if row is None:
        raise ConfigError(f"no answer {answer_id} in run {rc.run_id}")
    q = question(rc, row["question_id"])
    return {
        **dict(row),
        "text": rc.store.message(row["text_ref"]) or "",
        "cited": json.loads(row["cited_json"] or "[]"),
        "provenance": json.loads(row["provenance_json"] or "{}"),
        "question": q["text"],
        "origin": q["origin"],
        "seq": q["seq"],
    }
