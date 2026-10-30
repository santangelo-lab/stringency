"""The packet of a flag hold (PLAN L133): what a person reads to decide a hold a predicate opened.

Every packet has four parts, in this order: the question asked ("is this acceptable: ..."), the
rule in words with the facts filled from the verdict's evidence payload, the evidence scoped to
the item or row the predicate names, and what each verdict keeps or discards for this predicate.
The console's hold page and `present --hold` print the same packet.

Wording lives in a table, not on the predicates: `DEFAULT_SAYS` words any predicate from its
reason, its one-sentence summary (or docstring) and its evidence; `SAYS` holds the predicates that
need their own words, and a plugin adds its own with `register_says`. The predicate contract
(design 6.1, frozen) is unchanged: a `Says` reads the `Verdict` the predicate already returns.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

# the proposal's own tables, shown by the decision table rather than as facts
_DECISION_KEYS = ("proposed", "cited", "considered", "rationale_ref", "decision_points")


@dataclass(frozen=True)
class Facts:
    """What a packet is worded from: the hold's predicate and reason, what the predicate tests,
    its evidence payload, the policy's confidence bands, and the replicates' calls the evidence
    names (keyed by replicate and item). Built by `facts_for`; a test may build one by hand."""

    predicate: str
    reason: str
    check: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    criteria: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    calls: Mapping[tuple[int, str], Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class Says:
    """How a predicate's packet is worded. `question` and `rule` take the facts; `verdicts` maps
    a verdict to the sentence saying what it keeps or discards for this predicate (the engine's
    generic sentence otherwise); `correction` names the one field an override may correct on
    this flag (`review --verdict override --correction <field>=<value>`), with `correction_values`
    giving the values the policy allows."""

    question: Callable[[Facts], str] | None = None
    rule: Callable[[Facts], list[str]] | None = None
    verdicts: Mapping[str, str] = field(default_factory=dict)
    correction: str | None = None
    correction_values: Callable[[Mapping[str, Mapping[str, Any]]], list[str]] | None = None


def _plain(v: Any) -> str:
    if isinstance(v, bool) or v is None:
        return {True: "yes", False: "no", None: "none"}[v]
    if isinstance(v, float):
        return f"{v:g}" if abs(v) >= 1e-3 or v == 0 else f"{v:.3g}"
    if isinstance(v, dict):
        return ", ".join(f"{k}={_plain(x)}" for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(_plain(x) for x in v)
    return str(v)


def fact_lines(evidence: Mapping[str, Any]) -> list[str]:
    """The evidence payload as plain lines: `name: value` for a scalar or a list of scalars, one
    line per entry of a list of objects, `name.key: ...` one level into an object. The
    proposal's own tables are left to the decision table."""
    lines: list[str] = []
    for k, v in evidence.items():
        if k in _DECISION_KEYS:
            continue
        if isinstance(v, dict):
            for k2, v2 in v.items():
                lines.append(f"{k}.{k2}: {_plain(v2)}")
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            lines += [f"{k}: {_plain(x)}" for x in v]
        else:
            lines.append(f"{k}: {_plain(v)}")
    return lines


def default_question(f: Facts) -> str:
    return f"Is this acceptable: {f.reason.rstrip('. ')}?"


def default_rule(f: Facts) -> list[str]:
    lines = [f"The check: {f.check.rstrip('. ')}."] if f.check else []
    facts = fact_lines(f.evidence)
    lines += facts or ["The predicate recorded no facts beyond its reason."]
    return lines


DEFAULT_SAYS = Says(question=default_question, rule=default_rule)


# -- per-predicate words -----------------------------------------------------------------------


def flagged_pairs(evidence: Any) -> list[dict[str, Any]]:
    """Every (replicate, item) entry a judgment predicate reported, whatever key it used."""
    out: list[dict[str, Any]] = []
    if isinstance(evidence, Mapping):
        for v in evidence.values():
            if (
                isinstance(v, list)
                and v
                and all(isinstance(x, dict) and "replicate" in x and "item" in x for x in v)
            ):
                out += [dict(x) for x in v]
    return out


def _band_words(name: str, c: Mapping[str, Any]) -> str:
    least = c.get("min_supporting", 0)
    parts = [f"at least {least} supporting"]
    if c.get("max_contradicting") is not None:
        parts.append(f"at most {c['max_contradicting']} contradicting")
    noun = "citation" if len(parts) == 1 and least == 1 else "citations"
    return f"{name} needs " + " and ".join(parts) + f" {noun}"


def _ref(r: Any) -> str:
    if not isinstance(r, Mapping):
        return str(r)
    where = f"{r.get('table')}[{r.get('row')}].{r.get('column')}"
    return where + (f" = {_plain(r['value'])}" if "value" in r else "")


def _call_words(f: Facts, e: Mapping[str, Any]) -> str:
    rep, item = e.get("replicate"), e.get("item")
    call = f.calls.get((int(str(rep)), str(item))) if str(rep).isdigit() else None
    label = call.get("label") if call else None
    conf = e.get("confidence") or (call.get("confidence") if call else None)
    if label is not None:
        return f"reviewer {rep} called {item} {label} at {conf}"
    return f"reviewer {rep}'s call on {item} is at {conf}"


def _confidence_question(f: Facts) -> str:
    pairs = flagged_pairs(f.evidence)
    if len(pairs) == 1:
        return (
            f"Is this acceptable: {_call_words(f, pairs[0])} confidence, more than its "
            "citations support?"
        )
    return (
        f"Is this acceptable: {len(pairs)} calls declare a higher confidence than their "
        "citations support?"
    )


def _confidence_rule(f: Facts) -> list[str]:
    lines: list[str] = []
    for e in flagged_pairs(f.evidence):
        conf = str(e.get("confidence"))
        band = f.criteria.get(conf)
        head = _call_words(f, e)
        head = head[0].upper() + head[1:]
        cites = (
            f"this call cites {e.get('supporting')} supporting and "
            f"{e.get('contradicting')} contradicting"
        )
        lines.append(f"{head}; " + (f"{_band_words(conf, band)}; " if band else "") + cites + ".")
        call = (
            f.calls.get((int(e["replicate"]), str(e["item"])))
            if str(e.get("replicate")).isdigit()
            else None
        )
        against = list(call.get("contradicting") or []) if call else []
        if against:
            lines.append(
                "The contradicting citation"
                + ("s: " if len(against) > 1 else ": ")
                + "; ".join(_ref(r) for r in against)
                + "."
            )
    if f.criteria:
        lines.append(
            "The bands the policy sets: "
            + "; ".join(_band_words(k, v) for k, v in f.criteria.items())
            + "."
        )
    return lines or default_rule(f)


def _uncited_rule(f: Facts) -> list[str]:
    missing = f.evidence.get("uncited")
    if not isinstance(missing, list) or not missing:
        return default_rule(f)
    must = f.evidence.get("must_cite")
    lines = []
    if isinstance(must, list) and must:
        lines.append(
            "The module requires every judgment to cite, as support or contradiction: "
            + ", ".join(str(m) for m in must)
            + "."
        )
    for m in missing:
        if isinstance(m, Mapping):
            lines.append(
                f"Reviewer {m.get('replicate')}'s call on {m.get('item')} cites neither "
                f"{m.get('table')}[{m.get('item')}].{m.get('column')}."
            )
    return lines


def _proposal_question(f: Facts) -> str:
    proposed = f.evidence.get("proposed")
    names = [str(k) for k in proposed] if isinstance(proposed, Mapping) else []
    if not names:
        return default_question(f)
    return f"Is this acceptable: the operator's value for {', '.join(names)}?"


def _proposal_rule(f: Facts) -> list[str]:
    from stringency.console import _proposal_sentence

    lines = [f"The check: {f.check.rstrip('. ')}."] if f.check else []
    proposed = f.evidence.get("proposed")
    if isinstance(proposed, Mapping):
        for name, p in proposed.items():
            if isinstance(p, Mapping):
                lines.append(
                    f"{name}: default {_plain(p.get('default'))}, proposed "
                    f"{_plain(p.get('proposed'))}."
                )
    sentence = _proposal_sentence({"evidence": dict(f.evidence)})
    if sentence:
        lines.append(sentence.split(". The decision table")[0].rstrip(".") + ".")
    return lines or default_rule(f)


def _range_rule(f: Facts) -> list[str]:
    bad = f.evidence.get("out_of_range")
    if not isinstance(bad, Mapping) or not bad:
        return default_rule(f)
    lines = []
    for name, d in bad.items():
        if not isinstance(d, Mapping):
            continue
        allowed = (
            f"the range {_plain(d.get('range'))}"
            if d.get("range") is not None
            else f"the options {_plain(d.get('options'))}"
        )
        lines.append(
            f"{name}: proposed {_plain(d.get('proposed'))}, outside {allowed} the pipeline "
            "declares."
        )
    return lines


SAYS: dict[str, Says] = {
    "judg.confidence_consistent": Says(
        question=_confidence_question,
        rule=_confidence_rule,
        verdicts={
            "accept": "the calls stand at the confidence the reviewers declared; the hold "
            "clears and the step is completed",
            "override": "the labels stand and the confidence you name is recorded with your "
            "review for the flagged calls; the hold clears and the step is completed",
            "reject": "the attempt closes and its calls are discarded; a new attempt needs a "
            "change to the method or a fork",
        },
        correction="confidence",
        correction_values=lambda criteria: list(criteria),
    ),
    "judg.required_evidence_uncited": Says(
        rule=_uncited_rule,
        verdicts={
            "accept": "the calls stand without the required citation; the hold clears and the "
            "step is completed",
            "reject": "the attempt closes and its calls are discarded; a new attempt needs a "
            "change to the method or a fork",
        },
    ),
    "param.agent_proposed": Says(
        question=_proposal_question,
        rule=_proposal_rule,
        verdicts={"accept": "the step runs with the operator's values; the hold clears"},
    ),
    "param.out_of_range": Says(rule=_range_rule),
}


def criteria_of(policy: Any) -> dict[str, dict[str, Any]]:
    """The policy's confidence bands as plain mappings, for a packet's rule."""
    out: dict[str, dict[str, Any]] = {}
    for name, c in (getattr(policy, "confidence_criteria", None) or {}).items():
        out[str(name)] = {
            "min_supporting": c.min_supporting,
            "max_contradicting": c.max_contradicting,
        }
    return out


def register_says(predicate_id: str, says: Says) -> None:
    """A plugin's own words for one of its predicates; the engine's entry wins for its own."""
    if predicate_id in SAYS and predicate_id.split(".")[0] in _ENGINE_NAMESPACES:
        raise ValueError(f"{predicate_id} is an engine predicate; its words live in the engine")
    SAYS[predicate_id] = says


_ENGINE_NAMESPACES = ("topo", "repro", "param", "out", "judg", "exec", "obj", "prov", "init")


def says_for(predicate: str) -> Says:
    """The predicate's own words, or the default; `predicate` may carry `@version`."""
    return SAYS.get(predicate.split("@")[0], DEFAULT_SAYS)


def check_of(pred_id: str) -> str | None:
    """What a predicate tests, in one sentence: its registered `summary`, else the first
    sentence of its docstring; None for a predicate this engine has not registered."""
    from stringency.predicates.registry import registry

    spec = registry.get(pred_id)
    if spec is None:
        return None
    if spec.summary:
        return spec.summary
    from stringency.console import _first_sentence

    return _first_sentence(spec.fn.__doc__ or "") or None


def facts_for(
    h: Any,
    ctx: Mapping[str, Any],
    *,
    criteria: Mapping[str, Mapping[str, Any]] | None = None,
    store: Any = None,
) -> Facts:
    """The facts of a flag hold. Reads the hold's `reason` and `context_json` and, when `store`
    is given and the evidence names (replicate, item) pairs, the `judgments` rows of those calls
    (label, confidence, the cited cells). Writes nothing."""
    predicate = str(ctx.get("predicate") or "")
    pred_id = predicate.split("@")[0]
    reason = str(h["reason"] or "")
    if pred_id and reason.startswith(f"{pred_id}: "):
        reason = reason[len(pred_id) + 2 :]
    evidence = ctx.get("evidence")
    ev: Mapping[str, Any] = evidence if isinstance(evidence, Mapping) else {}
    calls: dict[tuple[int, str], dict[str, Any]] = {}
    pairs = flagged_pairs(ev)
    if store is not None and pairs and h["run_id"] and h["step_id"]:
        for r in store.all(
            "SELECT replicate, item_id, label, confidence, supporting_json, contradicting_json "
            "FROM judgments WHERE run_id = ? AND step_id = ? ORDER BY rowid",
            (h["run_id"], h["step_id"]),
        ):
            calls[(int(r["replicate"]), str(r["item_id"]))] = {
                "label": r["label"],
                "confidence": r["confidence"],
                "supporting": json.loads(r["supporting_json"] or "[]"),
                "contradicting": json.loads(r["contradicting_json"] or "[]"),
            }
    return Facts(
        predicate=pred_id,
        reason=reason,
        check=check_of(pred_id) if pred_id else None,
        evidence=ev,
        criteria=criteria or {},
        calls=calls,
    )


def scope_items(h: Any, ctx: Mapping[str, Any]) -> list[str]:
    """The items a hold is about: its own item, else the items its evidence names, in order."""
    if h["item_id"] is not None:
        return [str(h["item_id"])]
    out: list[str] = []
    for e in flagged_pairs(ctx.get("evidence")):
        if str(e["item"]) not in out:
            out.append(str(e["item"]))
    return out


def heading_of(h: Any, ctx: Mapping[str, Any]) -> str | None:
    """The item and replicate a hold is about, for the heading; None for a step-wide flag."""
    if h["item_id"] is not None:
        return f"item {h['item_id']}"
    pairs = flagged_pairs(ctx.get("evidence"))
    if not pairs:
        return None
    if len(pairs) == 1:
        return f"replicate {pairs[0]['replicate']}, item {pairs[0]['item']}"
    reps = sorted({str(p["replicate"]) for p in pairs})
    return f"replicates {', '.join(reps)}, items " + ", ".join(scope_items(h, ctx))


def flag_packet(
    h: Any,
    ctx: Mapping[str, Any],
    verdicts: list[dict[str, str]],
    *,
    criteria: Mapping[str, Mapping[str, Any]] | None = None,
    store: Any = None,
) -> dict[str, Any]:
    """The four parts of a flag hold's packet: `question`, `rule` (lines), `evidence` (the
    scope, `item` when the hold names items, else `step`, and the items), and `verdicts` (each
    with what it keeps or discards). `says` is `own` when the predicate has its own words and
    `default` otherwise. Reads what `facts_for` reads; writes nothing."""
    predicate = str(ctx.get("predicate") or "")
    pred_id = predicate.split("@")[0]
    facts = facts_for(h, ctx, criteria=criteria, store=store)
    says = says_for(pred_id)
    question = (says.question or default_question)(facts)
    rule = (says.rule or default_rule)(facts) or default_rule(facts)
    items = scope_items(h, ctx)
    return {
        "question": question,
        "rule": rule,
        "evidence": {"scope": "item" if items else "step", "items": items},
        "verdicts": verdicts,
        "heading": heading_of(h, ctx),
        "says": "own" if pred_id in SAYS else "default",
    }
