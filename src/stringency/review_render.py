"""The review display (design 7.3): what a reviewer sees for each hold kind.

Each hold asks one narrow question; the display answers it and nothing else. It states what
fired and what each verdict does. It does not recommend a verdict, and it never re-derives a
judgment or re-runs a predicate: every line comes from the trace or from the evidence tables the
step read.

Reads: holds (`context_json`), actions, steps, judgments, messages (rationales),
state_snapshots, executions; the step's evidence tables from disk. Writes nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from stringency.holds import open_holds
from stringency.predicates.context import EvidenceTable
from stringency.predicates.engine.judg import values_equal
from stringency.project import Project
from stringency.runs import RunContext, load_run
from stringency.state import State, latest_state
from stringency.steps import StepPlan, action_from_row, evidence_tables_for, plan_step


def tables_seen(plan: StepPlan) -> dict[str, EvidenceTable]:
    """The evidence tables the reviewers saw. A judgment module with a `pre.*` script shows
    what the script wrote under the step's `evidence/`, and a secondary table (a metric guide,
    a reference summary) is keyed by its own first column, so a citation into it resolves; the
    declared table inputs otherwise. Reads files under the step directory, nothing from the
    trace. (Lane A item 6: every citation printed "no such cell" on the outlier module.)"""
    if plan.module.manifest.judgment is not None:
        from stringency.exit_codes import ConfigError
        from stringency.judgment import evidence_tables_from_disk

        try:
            return evidence_tables_from_disk(plan)[0]
        except ConfigError:
            pass
    return evidence_tables_for(plan)


INDENT = "  "


@dataclass
class CitedCell:
    """One evidence reference, resolved against the table it names."""

    table: str
    row: str
    column: str
    cited: Any
    stored: Any
    resolves: bool
    matches: bool

    def line(self) -> str:
        where = f"{self.table}[{self.row}].{self.column}"
        if not self.resolves:
            return f"{where}: cited {_v(self.cited)} (no such cell)"
        if not self.matches:
            return f"{where}: cited {_v(self.cited)}, stored {_v(self.stored)}"
        return f"{where} = {_v(self.stored)}"

    def to_json(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ReplicateView:
    replicate: int
    label: str | None
    ontology_id: str | None
    confidence: str | None
    abstain: bool
    supporting: list[CitedCell]
    contradicting: list[CitedCell]
    rationale: str

    @property
    def call(self) -> str:
        return "abstain" if self.abstain else f"{self.label} ({self.confidence})"

    def to_json(self) -> dict[str, Any]:
        return {
            "replicate": self.replicate,
            "label": self.label,
            "ontology_id": self.ontology_id,
            "confidence": self.confidence,
            "abstain": self.abstain,
            "supporting": [c.to_json() for c in self.supporting],
            "contradicting": [c.to_json() for c in self.contradicting],
            "rationale": self.rationale,
        }


@dataclass
class HoldView:
    hold: Any
    text: str
    replicates: list[ReplicateView] = field(default_factory=list)
    module_ref: str | None = None
    evidence_rows: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    flagged: list[dict[str, Any]] = field(default_factory=list)
    verdicts: list[dict[str, str]] = field(default_factory=list)
    packet: Path | None = None  # the Markdown packet on disk, when one was written

    def to_json(self) -> dict[str, Any]:
        h = self.hold
        return {
            "hold_id": h["hold_id"],
            "kind": h["kind"],
            "run_id": h["run_id"],
            "step_id": h["step_id"],
            "item_id": h["item_id"],
            "reason": h["reason"],
            "waits_on": h["waits_on_role"],
            "created": h["created"],
            "resolved_by_review": h["resolved_by_review"],
            "resolved_via": h["resolved_via"],
            "context": json.loads(h["context_json"] or "{}"),
            "module": self.module_ref,
            "evidence_rows": self.evidence_rows,
            "replicates": [r.to_json() for r in self.replicates],
            "flagged": self.flagged,
            "verdicts": self.verdicts,
            "packet": str(self.packet) if self.packet else None,
            "text": self.text,
        }


# -- helpers ---------------------------------------------------------------------------------


def _v(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _kv(d: dict[str, Any], skip: tuple[str, ...] = ()) -> str:
    return "  ".join(f"{k}={_v(v)}" for k, v in d.items() if k not in skip)


def resolve_ref(tables: dict[str, EvidenceTable], ref: dict[str, Any]) -> CitedCell:
    """Reads nothing from the trace: resolves one `{table, row, column, value}` against the
    loaded evidence tables so the cited value can be shown beside the stored one."""
    table = str(ref.get("table"))
    row = str(ref.get("row"))
    column = str(ref.get("column"))
    cited = ref.get("value")
    t = tables.get(table)
    if t is None:
        return CitedCell(table, row, column, cited, None, False, False)
    ok, stored = t.cell(row, column)
    if not ok:
        return CitedCell(table, row, column, cited, None, False, False)
    return CitedCell(table, row, column, cited, stored, True, values_equal(stored, cited))


def who_waits(project: Project, h: Any) -> str:
    role = h["waits_on_role"]
    user = project.config.roles.owner if role == "owner" else project.config.roles.reviewer
    return f"{role} {user}"


def _latest_action(rc: RunContext, step_id: str) -> Any:
    row = rc.store.one(
        "SELECT * FROM actions WHERE run_id=? AND step_id=? ORDER BY attempt DESC, rowid DESC LIMIT 1",
        (rc.run_id, step_id),
    )
    return action_from_row(row) if row else None


def _replicates(
    project: Project, h: Any, attempt: int | None, tables: dict[str, EvidenceTable]
) -> list[ReplicateView]:
    """Reads: judgments and messages for the hold's step (and item when the hold names one)."""
    sql = "SELECT * FROM judgments WHERE run_id = ? AND step_id = ?"
    params: list[Any] = [h["run_id"], h["step_id"]]
    if h["item_id"] is not None:
        sql += " AND item_id = ?"
        params.append(h["item_id"])
    if attempt is not None:
        sql += " AND attempt = ?"
        params.append(attempt)
    sql += " ORDER BY replicate, rowid"
    return [_replicate_view(project, r, tables) for r in project.store.all(sql, tuple(params))]


def _item_judgments(project: Project, h: Any, attempt: int | None) -> dict[tuple[int, str], Any]:
    """Reads: judgments for the step keyed by (replicate, item)."""
    sql = "SELECT * FROM judgments WHERE run_id = ? AND step_id = ?"
    params: list[Any] = [h["run_id"], h["step_id"]]
    if attempt is not None:
        sql += " AND attempt = ?"
        params.append(attempt)
    return {(r["replicate"], str(r["item_id"])): r for r in project.store.all(sql, tuple(params))}


def _replicate_view(project: Project, r: Any, tables: dict[str, EvidenceTable]) -> ReplicateView:
    return ReplicateView(
        replicate=r["replicate"],
        label=r["label"],
        ontology_id=r["ontology_id"],
        confidence=r["confidence"],
        abstain=bool(r["abstain"]),
        supporting=[resolve_ref(tables, x) for x in json.loads(r["supporting_json"])],
        contradicting=[resolve_ref(tables, x) for x in json.loads(r["contradicting_json"])],
        rationale=(project.store.message(r["rationale_ref"]) or "") if r["rationale_ref"] else "",
    )


def _replicate_lines(r: ReplicateView, indent: str) -> list[str]:
    lines = [f"{indent}supporting:"]
    lines += [f"{indent}{INDENT}{c.line()}" for c in r.supporting] or [f"{indent}{INDENT}none"]
    lines.append(f"{indent}contradicting:")
    lines += [f"{indent}{INDENT}{c.line()}" for c in r.contradicting] or [f"{indent}{INDENT}none"]
    lines.append(f'{indent}rationale: "{r.rationale}"')
    return lines


def _table_rows(
    tables: dict[str, EvidenceTable], wanted: set[tuple[str, str]]
) -> dict[str, dict[str, dict[str, Any]]]:
    """The slice of each evidence table the display shows: the rows in `wanted`."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for name, t in tables.items():
        rows = {k: dict(v) for k, v in t.rows.items() if (name, k) in wanted}
        if rows:
            out[name] = rows
    return out


def _table_lines(slice_: dict[str, dict[str, dict[str, Any]]], title: str) -> list[str]:
    lines: list[str] = []
    for name, rows in slice_.items():
        lines.append(f"{title} {name}:")
        for key in sorted(rows):
            lines.append(f"{INDENT}{_kv(rows[key])}")
    return lines


def _evidence_lines(ev: Any, indent: str = INDENT) -> list[str]:
    """A predicate's evidence rendered one entry per line rather than as raw JSON."""
    lines: list[str] = []
    if isinstance(ev, dict):
        for k, v in ev.items():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                lines.append(f"{indent}{k}:")
                lines += [f"{indent}{INDENT}{_kv(x)}" for x in v]
            elif isinstance(v, dict) and v:
                lines.append(f"{indent}{k}:")
                lines += [f"{indent}{INDENT}{kk}: {_v(vv)}" for kk, vv in v.items()]
            else:
                lines.append(f"{indent}{k}: {_v(v)}")
    elif ev not in (None, {}, []):
        lines.append(f"{indent}{_v(ev)}")
    return lines


def _state_lines(state: State | None, step_id: str) -> list[str]:
    if state is None:
        return []
    after = state.after_step or "run open"
    lines = [f"state the gate read (after {after}):"]
    for name, obj in state.objects.items():
        lines.append(f"{INDENT}object {name} ({obj.type}) {obj.digest}")
    for rec in state.history:
        if rec.step == step_id:
            lines.append(
                f"{INDENT}history {rec.step}: {rec.operation} params {_v(rec.params)} "
                f"outputs {_v(rec.output_digests)}"
            )
    return lines


def _execution_lines(rc: RunContext, action_id: str) -> list[str]:
    row = rc.store.one("SELECT * FROM executions WHERE action_id = ?", (action_id,))
    if row is None:
        return []
    parts = [f"runner={row['runner']}", f"env={row['env_name']}", f"env_status={row['env_status']}"]
    if row["env_digest"]:
        parts.append(f"env_digest={row['env_digest']}")
    elif row["expected_env_digest"]:
        parts.append(f"expected_env_digest={row['expected_env_digest']}")
    if row["exit_code"] is not None:
        parts.append(f"exit={row['exit_code']}")
    return ["execution: " + "  ".join(parts)]


def _verdict_lines(verdicts: list[dict[str, str]]) -> list[str]:
    lines = ["verdicts:"]
    for v in verdicts:
        lines.append(f"{INDENT}{v['verdict']}: {v['effect']}")
        lines.append(f"{INDENT}{INDENT}{v['command']}")
    return lines


def verdicts_for(kind: str, hold_id: str, phase: str | None) -> list[dict[str, str]]:
    """The verdicts a hold kind admits and what each does (design 7.2, 7.3)."""
    base = f"stringency review --verdict {{verdict}} --hold {hold_id}"
    if kind == "confirm":
        return [
            {
                "verdict": "accept",
                "effect": "the engine's reading matches the experiment; runs may open",
                "command": base.format(verdict="accept") + ' --reason "<why>"',
            },
            {
                "verdict": "reject",
                "effect": "the reading is wrong; the project cannot run until the declarations "
                "change and a new echo-back is accepted",
                "command": base.format(verdict="reject") + ' --reason "<why>"',
            },
        ]
    if kind == "flag":
        proceeds = "the step proceeds to execution" if phase == "pre" else "the step is completed"
        return [
            {
                "verdict": "accept",
                "effect": f"the flagged condition is acceptable here; the hold clears and {proceeds}",
                "command": base.format(verdict="accept") + ' --reason "<why>"',
            },
            {
                "verdict": "reject",
                "effect": "the attempt closes; a new attempt needs a change to the method or a fork",
                "command": base.format(verdict="reject") + ' --reason "<why>"',
            },
            {
                "verdict": "defer",
                "effect": "the hold stays; the deferral is recorded so the queue shows it was seen",
                "command": base.format(verdict="defer"),
            },
        ]
    return [
        {
            "verdict": "accept",
            "effect": "consensus takes replicate n's label, recorded as source accepted",
            "command": base.format(verdict="accept") + " --replicate <n>",
        },
        {
            "verdict": "override",
            "effect": "consensus takes the correction, checked against the module schema and "
            "vocabulary, recorded as source override",
            "command": base.format(verdict="override")
            + ' --correction \'{"label": "<label>"}\' --reason "<why>"',
        },
        {
            "verdict": "reject",
            "effect": "the attempt closes; a new attempt needs a change to the method or a fork",
            "command": base.format(verdict="reject") + ' --reason "<why>"',
        },
        {
            "verdict": "defer",
            "effect": "the hold stays; the deferral is recorded so the queue shows it was seen",
            "command": base.format(verdict="defer"),
        },
    ]


def _resolution_lines(h: Any) -> list[str]:
    if h["resolved_by_review"] is None:
        return []
    return [f"resolved by review {h['resolved_by_review']} via {h['resolved_via']}"]


# -- per hold kind -----------------------------------------------------------------------------


def render_confirm(project: Project, h: Any) -> HoldView:
    """Reads: holds.context_json (the declaration digests) and `echo.md` on disk."""
    ctx = json.loads(h["context_json"] or "{}")
    lines = [
        f"hold {h['hold_id']}  kind confirm  waits on {who_waits(project, h)}",
        f"created {h['created']}",
        "",
        "question: does the engine's reading of the declarations match the experiment",
        "",
    ]
    echo = project.echo_path()
    if echo.exists():
        lines.append(echo.read_text().rstrip())  # ends with the bound digests
    else:
        lines.append("echo-back missing on disk; the hold was bound to:")
        hashes = ctx.get("hashes") or {}
        lines += [f"{INDENT}{name}: {digest}" for name, digest in sorted(hashes.items())]
    verdicts = verdicts_for("confirm", h["hold_id"], None)
    lines += ["", *_verdict_lines(verdicts), *_resolution_lines(h)]
    return HoldView(h, "\n".join(lines), verdicts=verdicts)


def _header(project: Project, h: Any, action: Any, module_ref: str | None) -> list[str]:
    attempt = action.attempt if action else "?"
    return [
        f"hold {h['hold_id']}  kind {h['kind']}  waits on {who_waits(project, h)}",
        f"step {h['step_id']}  module {module_ref}  attempt {attempt}  created {h['created']}",
    ]


def render_flag(
    project: Project, rc: RunContext, h: Any, action: Any, plan: StepPlan | None
) -> HoldView:
    """A flag hold: the predicate's reason and evidence, the parameters, and what the gate
    read. When the predicate is a judgment check (`judg.*`) the flagged replicates and items
    are shown with their cited cells resolved against the evidence table.

    Reads: actions, judgments, messages, state_snapshots, executions."""
    ctx = json.loads(h["context_json"] or "{}")
    predicate = str(ctx.get("predicate", ""))
    phase = str(ctx.get("phase", "post"))
    evidence = ctx.get("evidence", {})
    module_ref = plan.module.ref if plan else (action.module if action else None)
    lines = _header(project, h, action, module_ref)
    lines += [
        "",
        "question: is the flagged condition acceptable here",
        "",
        f"predicate {predicate}  phase {phase}",
        f"reason: {h['reason']}",
    ]
    view = HoldView(h, "", module_ref=module_ref)
    if action:
        lines.append("parameters: " + (_kv(action.parameters) or "none"))
    judg = predicate.startswith("judg.") and plan is not None
    if judg:
        assert plan is not None
        tables = tables_seen(plan)
        flagged = _flagged_pairs(evidence)
        by_key = _item_judgments(project, h, action.attempt if action else None)
        cited: set[tuple[str, str]] = set()
        lines += ["", "flagged replicates and items:"]
        for entry in flagged:
            rep, item = int(entry["replicate"]), str(entry["item"])
            row = by_key.get((rep, item))
            rv = _replicate_view(project, row, tables) if row else None
            detail = _kv(entry, skip=("replicate", "item"))
            call = rv.call if rv else "no judgment row"
            lines.append(f"{INDENT}replicate {rep}, item {item}: {call}")
            if detail:
                lines.append(f"{INDENT}{INDENT}fired on: {detail}")
            crit = _criterion_line(project, predicate, entry)
            if crit:
                lines.append(f"{INDENT}{INDENT}{crit}")
            if rv:
                lines += _replicate_lines(rv, INDENT + INDENT)
                cited |= {(c.table, c.row) for c in rv.supporting + rv.contradicting}
                view.replicates.append(rv)
            view.flagged.append({**entry, "call": call})
        view.evidence_rows = _table_rows(tables, cited)
        if view.evidence_rows:
            lines += ["", *_table_lines(view.evidence_rows, "evidence table (rows cited)")]
        leftovers = {k: v for k, v in evidence.items() if not _is_pair_list(v)}
        if leftovers:
            lines += ["", "other evidence:", *_evidence_lines(leftovers)]
    else:
        lines += ["evidence:", *(_evidence_lines(evidence) or [f"{INDENT}none"])]
        if action:
            lines += [""]
            lines += _state_lines(
                latest_state(rc.store, rc.run_id, h["step_id"])
                if phase == "post"
                else latest_state(rc.store, rc.run_id, completed_only=True),
                h["step_id"],
            )
            if phase == "post":
                lines += _execution_lines(rc, action.action_id)
    view.verdicts = verdicts_for("flag", h["hold_id"], phase)
    lines += ["", *_verdict_lines(view.verdicts), *_resolution_lines(h)]
    view.text = "\n".join(lines)
    return view


def _is_pair_list(v: Any) -> bool:
    return (
        isinstance(v, list)
        and bool(v)
        and all(isinstance(x, dict) and "replicate" in x and "item" in x for x in v)
    )


def _flagged_pairs(evidence: Any) -> list[dict[str, Any]]:
    """Every (replicate, item) entry a judgment predicate reported, whatever key it used."""
    out: list[dict[str, Any]] = []
    if isinstance(evidence, dict):
        for v in evidence.values():
            if _is_pair_list(v):
                out += [dict(x) for x in v]
    return out


def _criterion_line(project: Project, predicate: str, entry: dict[str, Any]) -> str | None:
    """For `judg.confidence_consistent`, the policy criterion the declared confidence failed."""
    if not predicate.startswith("judg.confidence_consistent"):
        return None
    conf = entry.get("confidence")
    c = project.policy.confidence_criteria.get(str(conf))
    if c is None:
        return None
    parts = [f"at least {c.min_supporting} supporting"]
    if c.max_contradicting is not None:
        parts.append(f"at most {c.max_contradicting} contradicting")
    return f"criterion for {conf}: {', '.join(parts)}"


def render_item(
    project: Project, rc: RunContext, h: Any, action: Any, plan: StepPlan | None
) -> HoldView:
    """An item hold (`self_uncertain`, `run_disagreement`): the evidence rows for the item,
    each replicate's call with its cited cells resolved and its rationale quoted; a
    disagreement is also grouped by label.

    Reads: actions, judgments, messages; the evidence tables from disk."""
    module_ref = plan.module.ref if plan else (action.module if action else None)
    tables = tables_seen(plan) if plan else {}
    item = str(h["item_id"])
    question = (
        "which replicate's call stands for this item, or none"
        if h["kind"] == "self_uncertain"
        else "the replicates split on this item: which call stands, or none"
    )
    lines = _header(project, h, action, module_ref)
    lines += ["", f"item {item}", f"question: {question}", f"reason: {h['reason']}", ""]
    view = HoldView(h, "", module_ref=module_ref)
    view.evidence_rows = _table_rows(tables, {(name, item) for name in tables})
    lines += _table_lines(view.evidence_rows, "evidence row in") or ["evidence row: none"]
    view.replicates = _replicates(project, h, action.attempt if action else None, tables)
    if h["kind"] == "run_disagreement":
        groups: dict[str, list[int]] = {}
        for r in view.replicates:
            groups.setdefault("abstain" if r.abstain else str(r.label), []).append(r.replicate)
        lines += ["", "calls by label:"]
        lines += [
            f"{INDENT}{label}: replicate {', '.join(str(n) for n in reps)}"
            for label, reps in groups.items()
        ]
    lines += ["", "replicates:"]
    for r in view.replicates:
        lines.append(f"{INDENT}replicate {r.replicate}: {r.call}")
        lines += _replicate_lines(r, INDENT + INDENT)
    view.verdicts = verdicts_for(h["kind"], h["hold_id"], None)
    lines += ["", *_verdict_lines(view.verdicts), *_resolution_lines(h)]
    view.text = "\n".join(lines)
    return view


def render(project: Project, h: Any) -> HoldView:
    """Render one hold for the reviewer (design 7.3). Reads: see the module docstring."""
    if h["kind"] == "confirm":
        return render_confirm(project, h)
    rc = load_run(project, h["run_id"])
    action = _latest_action(rc, h["step_id"])
    plan = plan_step(rc, h["step_id"], action.attempt) if action else None
    view = (
        render_item(project, rc, h, action, plan)
        if h["item_id"] is not None
        else render_flag(project, rc, h, action, plan)
    )
    paths = packet_paths(project, h)
    if paths is not None and paths[0].exists():
        view.packet = paths[0]
    return view


# -- the review packet on disk (review-ux layer 2) ---------------------------------------------

PACKET_HTML = Environment(undefined=StrictUndefined, autoescape=True).from_string(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>stringency hold {{ hold_id }}</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; color: #222; }
h1 { font-size: 1.2em; font-weight: 600; }
pre { white-space: pre-wrap; word-break: break-word; background: #f6f6f6; padding: 1em; border: 1px solid #ddd; }
p.note { color: #555; font-size: 0.9em; }
</style>
</head>
<body>
<h1>Hold {{ hold_id }} ({{ kind }}){% if step_id %} on step {{ step_id }}{% endif %}{% if item_id %}, item {{ item_id }}{% endif %}</h1>
<p class="note">Written by stringency when the hold opened. The verdict is given at a terminal with the command shown at the end; this page records nothing.</p>
<pre>{{ text }}</pre>
</body>
</html>
"""
)


def packet_dir(project: Project, h: Any) -> Path | None:
    """`runs/<run>/<step>/review/` for a step hold; the project confirm hold has no packet
    (its echo-back is the packet)."""
    if h["run_id"] is None or h["step_id"] is None:
        return None
    return project.step_dir(h["run_id"], h["step_id"]) / "review"


def packet_paths(project: Project, h: Any) -> tuple[Path, Path] | None:
    d = packet_dir(project, h)
    if d is None:
        return None
    return d / f"{h['hold_id']}.md", d / f"{h['hold_id']}.html"


def write_packet(project: Project, h: Any) -> tuple[Path, Path] | None:
    """Write the hold's review packet, Markdown and HTML with the same content as `review`
    prints (review-ux layer 2). Writes: `runs/<run>/<step>/review/<hold_id>.{md,html}`; no
    sidecar (a derived view, not an output). Reads: what `render` reads."""
    paths = packet_paths(project, h)
    if paths is None:
        return None
    view = render(project, h)
    md, page = paths
    md.parent.mkdir(parents=True, exist_ok=True)
    where = f" on step {h['step_id']}" + (f", item {h['item_id']}" if h["item_id"] else "")
    md.write_text(
        f"# Hold {h['hold_id']} ({h['kind']}){where}\n\n"
        "Written by stringency when the hold opened. The verdict is given at a terminal with the "
        "command shown at the end; this file records nothing.\n\n"
        "```\n" + view.text + "\n```\n"
    )
    page.write_text(
        PACKET_HTML.render(
            hold_id=h["hold_id"],
            kind=h["kind"],
            step_id=h["step_id"],
            item_id=h["item_id"],
            text=view.text,
        )
    )
    return md, page


def write_step_packets(project: Project, run_id: str, step_id: str) -> list[Path]:
    """Packets for every open hold of a step, written when the step is held. Returns the
    Markdown paths."""
    out: list[Path] = []
    for h in open_holds(project.store, run_id, step_id):
        paths = write_packet(project, h)
        if paths is not None:
            out.append(paths[0])
    return out
