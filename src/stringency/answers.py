"""Answers (open_mode_plan.md 2.5, 2026-10-16): the operator's reply text, filed against the
artifacts and cells it cites, gated before it is recorded.

`file_answer` resolves every `--cite` against this run's produced artifacts of completed
steps, loads the cited tables, takes the cited rows and columns (else every cell) as the
numerals the text may use, builds a synthetic `answer` action and an `OutputBundle` whose prose
is the text, evaluates the `ans.*` predicates (invariant: a cited id that does not exist, a
numeral matching no cited cell, the label written by the operator), derives the label from the
cited artifacts' lineage, and writes the `answers` row, admissible or blocked. A blocked answer
is kept, as a rejected proposal is.

Reads: artifacts, steps, questions, and everything `provenance.lineage` reads. Writes:
messages (the text), predicate_results (the `ans.*` verdicts, action id = the answer id),
answers, run_events (`answer_recorded`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
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
from stringency.predicates.engine.judg import NUMERAL, numeral_matches
from stringency.provenance import (
    label_for,
    label_sentence,
    lineage,
    qualifier,
    render_qualifier,
)
from stringency.questions import question
from stringency.runs import RunContext
from stringency.tables import is_tabular, load_table

CITE = re.compile(r"^(?P<id>[0-9A-HJKMNP-TV-Z]{26})(?::(?P<row>[^:]*))?(?::(?P<col>.*))?$")


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
            "numerals": {"matched": self.matched, "total": self.total},
            "blocked": [r.line() for r in self.gate.blocked],
            "provenance": self.provenance,
        }


def parse_cite(text: str) -> Cite:
    m = CITE.match(text.strip())
    if not m:
        raise ConfigError(f"--cite expects <artifact id>[:<row>[:<column>]], got {text!r}")
    return Cite(m.group("id"), m.group("row") or None, m.group("col") or None)


def _citable(rc: RunContext, cite: Cite) -> Any:
    """The artifact row when it is a produced output of a completed step of this run."""
    return rc.store.one(
        "SELECT a.* FROM artifacts a JOIN steps s ON s.run_id = a.run_id AND s.step_id = a.step_id "
        "WHERE a.run_id = ? AND a.artifact_id = ? AND a.status = 'produced' AND s.status = 'completed'",
        (rc.run_id, cite.artifact_id),
    )


def cited_cells(
    rc: RunContext, cites: list[Cite]
) -> tuple[dict[str, EvidenceTable], dict[str, dict[str, dict[str, Any]]], list[str]]:
    """(evidence tables of the cited cells by artifact id, the same cells as plain values, the
    citations that resolve to nothing). A non-table artifact is citable and contributes no
    cells; a row or column that is not in the table counts as missing."""
    tables: dict[str, EvidenceTable] = {}
    cells: dict[str, dict[str, dict[str, Any]]] = {}
    missing: list[str] = []
    for c in cites:
        art = _citable(rc, c)
        if art is None:
            missing.append(c.artifact_id)
            continue
        if not is_tabular(str(art["kind"]), str(art["path"])):
            if c.row is not None or c.column is not None:
                missing.append(f"{c.artifact_id}:{c.row or ''}:{c.column or ''}")
            continue
        full = load_table(Path(art["path"]), str(art["name"]))
        rows = full.rows if c.row is None else {c.row: full.rows.get(c.row)}
        picked: dict[str, dict[str, Any]] = {}
        for key, row in rows.items():
            if row is None:
                missing.append(f"{c.artifact_id}:{key}")
                continue
            if c.column is None:
                picked[key] = dict(row)
            elif c.column in row:
                picked[key] = {c.column: row[c.column]}
            else:
                missing.append(f"{c.artifact_id}:{key}:{c.column}")
        prior = cells.get(c.artifact_id, {})
        for key, row in picked.items():
            prior.setdefault(key, {}).update(row)
        cells[c.artifact_id] = prior
        tables[c.artifact_id] = EvidenceTable(
            name=str(art["name"]), key_column=full.key_column, columns=full.columns, rows=prior
        )
    return tables, cells, missing


def count_numerals(text: str, cells: dict[str, dict[str, dict[str, Any]]]) -> tuple[int, int]:
    values = [v for rows in cells.values() for row in rows.values() for v in row.values()]
    found = NUMERAL.findall(text)
    matched = sum(1 for n in found if any(numeral_matches(n, v) for v in values))
    return matched, len(found)


def file_answer(rc: RunContext, question_id: str, text: str, cites: list[Cite]) -> AnswerResult:
    """File one answer. Writes: messages, predicate_results, answers, run_events."""
    if not rc.open_ended:
        raise ConfigError("answers are filed on an open project's run only")
    question(rc, question_id)  # must be a question of this run
    words = text.strip()
    if not words:
        raise ConfigError("an answer needs text")
    if not cites:
        raise ConfigError("an answer cites at least one artifact (--cite <artifact id>)")
    store = rc.store
    tables, cells, missing = cited_cells(rc, cites)
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
    matched, total = count_numerals(words, cells)
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
        "numerals": {"matched": matched, "total": total},
        "route": "code" if any(f.kind == "exec" for f in facts) else "tool",
        "tools": [f.module for f in facts if f.kind == "tool"],
        "decisions": [
            {"step": f.step_id, "param": k, "value": f.params.get(k), "source": src}
            for f in facts
            if f.kind in ("tool", "exec")
            for k, src in f.param_sources.items()
        ],
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
