"""The open project's delivery: `deliver/<run>/`, written as answers are filed (open mode, the
report; 2026-10-19, after the owner's second test drive).

Every admissible answer of the run is in the directory the moment it exists: its own file
(`q<NN>-<words>.md`), the files it cites with their sidecars, `coverage.md`, `methods.md`,
`index.json`, and `report.md`, the one file a person reads. The report leads with the
findings, the answers the person marked (`stringency finding`), in full, in the person's order
and under their headings when they gave any (L144), each with the figures attached to it and
their labels (L143); the other questions follow, each a short paragraph; the record closes it.
A paragraph the person wrote (`deliver --story`) opens the report, labelled as theirs. The directory is regenerated in place
from the trace after every answer and every mark and by `stringency deliver`; it is
deterministic, so a `deliveries` row is written only when its content changed.

Reads: answers, questions, messages, artifacts, steps, actions, findings, deliveries, run_events
(`finding_placed`, `story_recorded`), and everything coverage reads. Writes: artifacts.is_final, predicate_results (the deliver gate),
deliveries, run_events, and the files under `deliver/<run>/`.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from stringency import __version__, hashing
from stringency.artifacts import sidecar_path
from stringency.clock import now_iso
from stringency.coverage import coverage_data, render_coverage
from stringency.deliver import (
    Delivery,
    answer_artifacts,
    answer_file_name,
    answer_rerun_line,
    deliver_gate,
    rerun_counts,
)
from stringency.exit_codes import HeldError, RefusedError
from stringency.findings import current as current_findings
from stringency.findings import placements, story, story_numerals
from stringency.ids import new_id
from stringency.methods import methods_paragraph, number_word
from stringency.present import Site, _settled_lines, answer_sections, markdown_table
from stringency.provenance import DRAWN_MEANS, TRUSTED_MEANS, UNTESTED_MEANS, fit_line
from stringency.runs import RunContext, captured_plugins
from stringency.summary import NOT_CHECKED_OPEN

REPORT_FILE = "report.md"
READER_FILES = ("coverage.md", "methods.md", "coverage.json", REPORT_FILE, "index.json")

NO_FINDING_YET = (
    "No answer has been marked as a finding yet. Everything asked is below; mark one with "
    "`stringency finding <answer id>`, or by telling the assistant which answers the report "
    "should lead with."
)


def admissible_answers(rc: RunContext) -> list[dict[str, Any]]:
    """Every admissible answer of the run in question order, then filing order, each with its
    words, its question's words, origin and seq, and its file name (`q<NN>-<words>.md`; a
    question's second answer `-2`, by filing order, so a name never changes). Reads: answers,
    questions, messages."""
    store = rc.store
    out: list[dict[str, Any]] = []
    nth: dict[str, int] = {}
    for r in store.all(
        "SELECT a.*, q.seq, q.origin, q.text_ref AS q_ref FROM answers a JOIN questions q ON "
        "q.question_id = a.question_id WHERE a.run_id = ? AND a.status = 'admissible' "
        "ORDER BY q.seq, a.rowid",
        (rc.run_id,),
    ):
        qid = str(r["question_id"])
        nth[qid] = nth.get(qid, 0) + 1
        question = store.message(r["q_ref"]) or ""
        out.append(
            {
                **dict(r),
                "text": store.message(r["text_ref"]) or "",
                "cited": json.loads(r["cited_json"] or "[]"),
                "provenance": json.loads(r["provenance_json"] or "{}"),
                "question": question,
                "file": answer_file_name(int(r["seq"]), question, nth[qid]),
            }
        )
    return out


def unanswerable_questions(rc: RunContext) -> dict[str, str]:
    """Question id to reason for every question whose latest answer on the run is
    `unanswerable` and which has no admissible answer (backlog L60). Reads: answers, messages."""
    store = rc.store
    out: dict[str, str] = {}
    for r in store.all(
        "SELECT question_id, status, text_ref FROM answers WHERE run_id = ? ORDER BY rowid",
        (rc.run_id,),
    ):
        qid = str(r["question_id"])
        if r["status"] == "unanswerable":
            out[qid] = store.message(r["text_ref"]) or ""
        elif r["status"] == "admissible":
            out.pop(qid, None)
    return out


def _questions(rc: RunContext) -> list[dict[str, Any]]:
    store = rc.store
    return [
        {**dict(q), "text": store.message(q["text_ref"]) or ""}
        for q in store.all(
            "SELECT * FROM questions WHERE run_id = ? ORDER BY seq, rowid", (rc.run_id,)
        )
    ]


def _latest_delivery(rc: RunContext) -> Any:
    return rc.store.one(
        "SELECT * FROM deliveries WHERE run_id = ? ORDER BY ts DESC, rowid DESC LIMIT 1",
        (rc.run_id,),
    )


def _previous_names(dest: Path) -> set[str]:
    """What the last regeneration wrote, from its `index.json`: the only names this code may
    remove when they are no longer listed."""
    idx = dest / "index.json"
    if not idx.exists():
        return set()
    try:
        data = json.loads(idx.read_text())
    except json.JSONDecodeError:
        return set()
    names: set[str] = set()
    for f in data.get("files") or []:
        names.add(str(f.get("file")))
        if f.get("sidecar"):
            names.add(str(f["sidecar"]))
    for a in data.get("answers") or []:
        names.add(str(a.get("file")))
    return names


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _finding_fields(
    mark: dict[str, Any] | None, placed: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The finding fields of an answer's index entry: whether it is one, who marked it, when,
    why, and its place and heading in the report (L144; None when unset or not a finding)."""
    if mark is None:
        return {
            "finding": False,
            "finding_by": None,
            "finding_ts": None,
            "finding_reason": None,
            "finding_order": None,
            "finding_heading": None,
        }
    return {
        "finding": True,
        "finding_by": mark.get("marked_by"),
        "finding_ts": mark.get("ts"),
        "finding_reason": mark.get("reason"),
        "finding_order": (placed or {}).get("order"),
        "finding_heading": (placed or {}).get("heading"),
    }


def _marked_line(entry: dict[str, Any]) -> str:
    by, ts = entry.get("finding_by") or "the person", str(entry.get("finding_ts") or "")[:10]
    reason = entry.get("finding_reason")
    return f"Marked as a finding by {by} on {ts}" + (f': "{reason}".' if reason else ".")


def _answer_file_text(ans: dict[str, Any], entry: dict[str, Any], cited_files: list[str]) -> str:
    prov = ans["provenance"]
    asked = (
        "as a path the operator proposed"
        if ans["origin"] == "suggested"
        else "in the person's own words"
    )
    head = f"# Question {ans['seq']}: {ans['question']}"
    if entry["finding"]:
        head += " (finding)"
    lines = [
        head,
        "",
        f"Asked {asked}; answer {ans['answer_id']}.",
        "",
        prov.get("label_sentence", ""),
        prov.get("qualifier_line", ""),
        "",
        ans["text"].rstrip(),
        "",
        # the question's wants beside the cited steps' gives (L139); absent before 0.2.36
        *(
            [fit_line(prov["fit"].get("wants"), prov["fit"].get("gives"))]
            if isinstance(prov.get("fit"), dict)
            else []
        ),
        "Cited files: " + (", ".join(cited_files) or "none"),
        *[f"Figure: {f['file'] or f['name']}. {f['label_line']}" for f in entry["figures"]],
        f"Runs: {entry['runs']}",
    ]
    if entry["finding"]:
        lines.append(_marked_line(entry))
    return "\n".join(lines) + "\n"


def write_open_delivery(rc: RunContext) -> Delivery:
    """Regenerate `deliver/<run>/` from the trace. Refused on an abandoned run; held (exit 10)
    while the run has open holds. Returns the Delivery with `changed` set when a `deliveries`
    row was written (the content differs from the last regeneration). Writes: see the module
    docstring."""
    store, project = rc.store, rc.project
    if rc.status() == "held":
        raise HeldError(
            f"held: run {rc.run_id} has open holds; run `stringency review` in {project.root}"
        )
    if rc.run["status"] in ("abandoned",):
        raise RefusedError(f"run {rc.run_id} is abandoned; nothing to report")
    answers = admissible_answers(rc)
    marks = current_findings(store, rc.run_id)
    places = placements(store, rc.run_id)
    finals = answer_artifacts(rc, answers)
    deliver_gate(rc, finals)
    dest = project.root / "deliver" / rc.run_id
    dest.mkdir(parents=True, exist_ok=True)
    previous = _previous_names(dest)

    files: list[dict[str, Any]] = []
    by_artifact: dict[str, str] = {}
    by_path: dict[str, str] = {}
    for a in finals:
        src = Path(a["path"])
        target = dest / f"{a['step_id']}.{src.name}"
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, target)
        shutil.copyfile(sidecar_path(src), sidecar_path(target))
        if not a["is_final"]:
            store.set_artifact_flag(a["artifact_id"], "is_final", True)
        by_artifact[a["artifact_id"]] = target.name
        by_path[str(src)] = target.name
        files.append(
            {
                "file": target.name,
                "step_id": a["step_id"],
                "output": a["name"],
                "action_id": a["action_id"],
                "artifact_id": a["artifact_id"],
                "blake3": a["hash"],
                "kind": a["kind"],
                "sidecar": sidecar_path(target).name,
                "provenance": _provenance(rc, a["artifact_id"]),
            }
        )
    counts = rerun_counts(rc)
    entries: list[dict[str, Any]] = []
    for ans in answers:
        prov = ans["provenance"]
        cited_files = sorted(
            {by_artifact[c["artifact_id"]] for c in ans["cited"] if c["artifact_id"] in by_artifact}
        )
        entry = {
            "answer_id": ans["answer_id"],
            "question_id": ans["question_id"],
            "seq": ans["seq"],
            "question": ans["question"],
            "origin": ans["origin"],
            "file": ans["file"],
            "label": ans["label"],
            "label_sentence": prov.get("label_sentence"),
            "qualifier": prov.get("qualifier_line"),
            "cites": ans["cited"],
            "files": cited_files,
            "figures": [
                {
                    "artifact_id": f["artifact_id"],
                    "name": f["name"],
                    "file": by_artifact.get(str(f["artifact_id"])),
                    "label": f["label"],
                    "label_line": f["label_line"],
                }
                for f in prov.get("figures") or []
            ],
            "runs": answer_rerun_line(rc, ans, counts),
            **_finding_fields(marks.get(ans["answer_id"]), places.get(ans["answer_id"])),
        }
        entries.append(entry)
    finding_steps = {
        s
        for e, ans in zip(entries, answers, strict=True)
        if e["finding"]
        for s in [
            f["step_id"]
            for f in ans["provenance"].get("lineage", [])
            if f.get("kind") in ("tool", "exec")
        ]
    }
    cov = coverage_data(rc)
    cov["explored"] = {
        "rerun_counts": [
            {**e, "findings": sum(1 for s in e["steps"] if s in finding_steps)}
            for e in counts.values()
        ],
        "questions": {
            "person": store.scalar(
                "SELECT COUNT(*) FROM questions WHERE run_id=? AND origin='person'", (rc.run_id,)
            )
            or 0,
            "suggested": store.scalar(
                "SELECT COUNT(*) FROM questions WHERE run_id=? AND origin='suggested'",
                (rc.run_id,),
            )
            or 0,
            # outcomes (backlog L60): a question is answered when an admissible answer exists,
            # unanswerable when its latest answer says so
            "asked": store.scalar("SELECT COUNT(*) FROM questions WHERE run_id=?", (rc.run_id,))
            or 0,
            "answered": store.scalar(
                "SELECT COUNT(DISTINCT question_id) FROM answers WHERE run_id=? AND status='admissible'",
                (rc.run_id,),
            )
            or 0,
            "unanswerable": len(unanswerable_questions(rc)),
        },
        "answers": entries,
    }
    coverage_text = render_coverage(cov)
    methods_text = methods_paragraph(rc, cov)
    questions = _questions(rc)

    # deterministic content, so a row is written only when something changed: render with the
    # last delivery's stamp, compare the index, and only then stamp anew
    latest = _latest_delivery(rc)
    stamp = str(latest["ts"]) if latest is not None else now_iso()
    changed = True

    def render(written: str) -> tuple[str, str]:
        report_text = render_report(rc, answers, entries, questions, cov, by_path, written=written)
        index = {
            "stringency": 1,
            "run_id": rc.run_id,
            "project_id": project.config.project_id,
            "mode": project.config.mode,
            "answers": entries,
            "engine_version": __version__,
            "plugins": captured_plugins(store, rc.run_id),
            "written": written,
            "files": files,
            "coverage": {"file": "coverage.md", "blake3": hashing.hash_text(coverage_text)},
            "methods": {"file": "methods.md", "blake3": hashing.hash_text(methods_text)},
            "report": {"file": REPORT_FILE, "blake3": hashing.hash_text(report_text)},
        }
        return report_text, json.dumps(index, indent=2, sort_keys=True) + "\n"

    report_text, index_text = render(stamp)
    if latest is not None and hashing.hash_text(index_text) == latest["index_hash"]:
        changed = False
    elif latest is not None:
        stamp = now_iso()
        report_text, index_text = render(stamp)

    written_names: set[str] = set()
    for ans, entry in zip(answers, entries, strict=True):
        (dest / entry["file"]).write_text(_answer_file_text(ans, entry, entry["files"]))
        written_names.add(entry["file"])
    for f in files:
        written_names.add(f["file"])
        written_names.add(f["sidecar"])
    (dest / "coverage.md").write_text(coverage_text)
    (dest / "methods.md").write_text(methods_text)
    (dest / "coverage.json").write_text(
        json.dumps(cov, indent=2, sort_keys=True, default=str) + "\n"
    )
    _write_atomic(dest / REPORT_FILE, report_text)
    _write_atomic(dest / "index.json", index_text)
    for stale in previous - written_names:
        p = dest / stale
        if p.is_file():
            p.unlink()

    did = str(latest["delivery_id"]) if latest is not None and not changed else new_id()
    if changed:
        store.insert(
            "deliveries",
            {
                "delivery_id": did,
                "run_id": rc.run_id,
                "path": str(dest),
                "coverage_hash": hashing.hash_text(coverage_text),
                "methods_hash": hashing.hash_text(methods_text),
                "index_hash": hashing.hash_text(index_text),
                "ts": stamp,
            },
        )
        store.run_event(
            rc.run_id,
            "delivered",
            {
                "delivery_id": did,
                "path": str(dest),
                "files": len(files),
                "answers": [e["answer_id"] for e in entries],
                "findings": [e["answer_id"] for e in entries if e["finding"]],
            },
        )
    return Delivery(
        did, dest, files, coverage_text, methods_text, report_text, entries, changed=changed
    )


def _provenance(rc: RunContext, artifact_id: str) -> dict[str, Any]:
    from stringency.provenance import block_for

    return block_for(rc, artifact_id)


# -- the report ------------------------------------------------------------------------------


def _upstream(rc: RunContext) -> tuple[str | None, str | None]:
    """The upstream project and the run that delivered: the delivery directory's name when the
    first chained input sits under `deliver/<run>/` (a file's own `derived_from.run_id` may name
    an earlier run that produced it, 2026-10-20), else that input's `derived_from.run_id`."""
    for i in rc.project.inputs.items:
        if i.derived_from is not None:
            p = Path(i.path)
            if p.parent.parent.name == "deliver":
                return i.derived_from.project, p.parent.name
            return i.derived_from.project, i.derived_from.run_id
    return None, None


def _asked_by(origin: str) -> str:
    return "a path the assistant proposed" if origin == "suggested" else "the person"


def _route(prov: dict[str, Any]) -> str:
    if prov.get("route") == "code":
        return "code written in the session"
    tools = [str(t).split("@")[0] for t in prov.get("tools") or []]
    return "tool " + " and ".join(dict.fromkeys(tools)) if tools else "a tool"


def _section_lines(s: dict[str, Any], by_path: dict[str, str]) -> list[str]:
    out = [f"**{s['title']}**", ""]
    if "error" in s:
        out.append(f"(not shown: {s['error']})")
    elif s["kind"] == "table":
        out.append(markdown_table(s["columns"], s["rows"]))
    elif s["kind"] in ("figure", "file"):
        name = by_path.get(str(s.get("path")))
        if name:
            out.append(f"![{s['title']}]({name})" if s["kind"] == "figure" else f"`{name}`")
        else:
            out.append(f"(file: {s.get('path')})")
    elif s["kind"] == "text":
        out.append(str(s.get("text", "")).rstrip())
    return out


def _finding_lines(
    site: Site,
    rc: RunContext,
    ans: dict[str, Any],
    e: dict[str, Any],
    by_path: dict[str, str],
    level: str,
) -> list[str]:
    """One finding in full: the question, the text, the answer view's tables and figures, the
    figures attached to it with their labels (L143), the label sentence, the settled
    parameters, who marked it and the file."""
    lines = [
        f"{level} {ans['question']}",
        "",
        f"Question {ans['seq']}, asked by {_asked_by(ans['origin'])}.",
        "",
        ans["text"].rstrip(),
        "",
    ]
    sections, _ = answer_sections(site, rc.run_id, ans["provenance"], ans["cited"])
    shown: set[str] = set()
    for s in sections:
        lines += _section_lines(s, by_path)
        lines.append("")
        if s.get("kind") == "figure" and by_path.get(str(s.get("path"))):
            shown.add(by_path[str(s.get("path"))])
    lines += _figure_lines(e, shown)
    lines.append(str(e.get("label_sentence") or ""))
    lines += _settled_lines(ans["provenance"].get("decisions") or [])
    lines.append(_marked_line(e))
    lines.append(f"Full record: `{e['file']}`.")
    lines.append("")
    return lines


def _counts_words(cov: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for e in (cov.get("explored") or {}).get("rerun_counts", []):
        module = str(e["module"]).split("@")[0]
        runs, params, found = int(e["runs"]), int(e["distinct_params"]), int(e.get("findings", 0))
        cited = (
            "none of them is cited by a finding"
            if found == 0
            else f"{number_word(found)} of them {'is' if found == 1 else 'are'} cited by a finding"
        )
        lines.append(
            f"- {module} ran {number_word(runs)} time{'s' if runs != 1 else ''} on one set of "
            f"inputs with {number_word(params)} distinct parameter set{'s' if params != 1 else ''}; "
            f"{cited} (steps {', '.join(e['steps'])})."
        )
    return lines


def _story_lines(
    rc: RunContext, findings: list[tuple[dict[str, Any], dict[str, Any]]]
) -> list[str]:
    """The person's paragraph (`deliver --story`, L144) as a quotation, then the line saying
    whose it is; a number in it that a finding no longer cites (a finding unmarked since) is
    named. Reads: run_events, messages."""
    st = story(rc.store, rc.run_id)
    if st is None or not st["text"].strip():
        return []
    by, ts = st.get("by") or "the person", str(st.get("ts") or "")[:10]
    relayed = ", relayed by the assistant" if st.get("via") == "relayed" else ""
    out = [*(f"> {ln}".rstrip() for ln in st["text"].strip().splitlines()), ""]
    line = (
        f"The paragraph above is in the person's own words, recorded by {by} on {ts}{relayed}; "
        "the engine did not write it, and checked its numbers against the cells the findings cite."
    )
    failed = story_numerals(rc, st["text"], [a for a, _ in findings])["failed"]
    if failed:
        line += " No finding cites " + ", ".join(n["numeral"] for n in failed) + " any longer."
    return [*out, line, ""]


def _arranged(
    findings: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[tuple[str | None, list[tuple[dict[str, Any], dict[str, Any]]]]]:
    """The findings in the person's order (L144): those given a place first, by place, then the
    rest in question order; grouped under their headings in the order the groups first appear,
    the findings without a heading last. One group with no heading when none was given."""
    ordered = [
        f
        for _, f in sorted(
            enumerate(findings),
            key=lambda t: (
                t[1][1].get("finding_order") is None,
                t[1][1].get("finding_order") or 0,
                t[0],
            ),
        )
    ]
    if not any(e.get("finding_heading") for _, e in ordered):
        return [(None, ordered)]
    groups: dict[str | None, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for a, e in ordered:
        groups.setdefault(e.get("finding_heading") or None, []).append((a, e))
    headed = [(h, fs) for h, fs in groups.items() if h is not None]
    return headed + ([("Other findings", groups[None])] if None in groups else [])


def _figure_lines(entry: dict[str, Any], shown: set[str]) -> list[str]:
    """Each figure attached to an answer (L143) under it, with its own label; the image is
    left out when the answer's tables already show it (the figure was also cited)."""
    out: list[str] = []
    for f in entry.get("figures") or []:
        name = f.get("file")
        out.append(f"**Figure: {f['name']}**")
        out.append("")
        if name and name not in shown:
            out += [f"![{f['name']}]({name})", ""]
        out += [str(f["label_line"]), ""]
    return out


def render_report(
    rc: RunContext,
    answers: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    cov: dict[str, Any],
    by_path: dict[str, str],
    *,
    written: str,
) -> str:
    """`report.md`: the person's paragraph when they wrote one, the findings in full in their
    order and under their headings, the other questions in short, the record. Reads nothing the
    caller has not already read, except the tables and figures the answer view names (through
    `present.answer_sections`) and the story (run_events, messages)."""
    project = rc.project
    up_project, up_run = _upstream(rc)
    up_name = Path(up_project).name if up_project else None
    site = Site(root=project.root, config=project.config, store=rc.store, pipeline=project.pipeline)
    findings = [(a, e) for a, e in zip(answers, entries, strict=True) if e["finding"]]
    finding_questions = {e["question_id"] for _, e in findings}
    first_asked = str(questions[0]["ts"])[:10] if questions else None
    n_q, n_f = len(questions), len(findings)

    lines = [
        f"# Questions of {up_name}'s results"
        if up_name
        else "# Questions of the delivered results",
        "",
        *_story_lines(rc, findings),
        (
            f"What was asked of the results that `{up_project}` delivered (run {up_run}), "
            if up_project
            else "What was asked of the delivered results, "
        )
        + f"under method {project.config.method.tag}"
        + (f", from {first_asked} to {written[:10]}" if first_asked else "")
        + f": {number_word(n_q)} question{'s' if n_q != 1 else ''} asked, "
        + f"{'none' if n_f == 0 else number_word(n_f)} marked as "
        + f"{'a finding' if n_f == 1 else 'findings'}. The findings lead; "
        "everything else asked follows, in short, with its full answer in a file beside this one.",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append(NO_FINDING_YET)
    for heading, group in _arranged(findings):
        level = "###"
        if heading is not None:
            lines += [f"### {heading}", ""]
            level = "####"
        for ans, e in group:
            lines += _finding_lines(site, rc, ans, e, by_path, level)
    lines += ["## Other questions", ""]

    cannot = unanswerable_questions(rc)
    latest_by_q: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    earlier_by_q: dict[str, list[str]] = {}
    for ans, e in zip(answers, entries, strict=True):
        qid = str(ans["question_id"])
        if qid in latest_by_q:
            earlier_by_q.setdefault(qid, []).append(latest_by_q[qid][1]["file"])
        latest_by_q[qid] = (ans, e)
    others = 0
    for q in questions:
        qid = str(q["question_id"])
        if qid in finding_questions:
            continue
        others += 1
        head = f"**{q['seq']}. {q['text']}**"
        if qid not in latest_by_q:
            if qid in cannot:
                lines += [
                    f"{head}: could not be answered from the delivery. {cannot[qid].strip()}",
                    "",
                ]
            else:
                lines += [f"{head}: no admissible answer was filed.", ""]
            continue
        ans, e = latest_by_q[qid]
        lines.append(f"{head} ({_route(ans['provenance'])}; {e['label']}). {ans['text'].strip()}")
        more = f"Full answer with its tables: `{e['file']}`."
        for f in e.get("figures") or []:
            more += f" Figure `{f['file'] or f['name']}` ({f['label']})."
        if earlier_by_q.get(qid):
            more += " Earlier answers: " + ", ".join(f"`{f}`" for f in earlier_by_q[qid]) + "."
        lines += [more, ""]
    if not others:
        lines += ["Every question asked is a finding above.", ""]
    ex = cov.get("explored") or {}
    qs = ex.get("questions") or {}
    op = cov.get("open") or {}
    lines += [
        "## How to read the labels",
        "",
        TRUSTED_MEANS,
        "",
        DRAWN_MEANS,
        "",
        UNTESTED_MEANS,
        "",
        "## The record",
        "",
        f"- Questions: {number_word(int(qs.get('person', 0)))} in the person's own words, "
        f"{number_word(int(qs.get('suggested', 0)))} a path the assistant proposed; "
        f"{number_word(int(qs.get('answered', 0)))} answered"
        + (
            f", {number_word(int(qs.get('unanswerable', 0)))} could not be answered from the delivery."
            if qs.get("unanswerable")
            else "."
        ),
        *_counts_words(cov),
        "- Scripts written in the session: "
        + (", ".join(op.get("exec_steps") or []) or "none")
        + ".",
        "- Tools run without a current control: "
        + (", ".join(op.get("uncontrolled_tools") or []) or "none")
        + ".",
        f"- {NOT_CHECKED_OPEN}",
        "- `coverage.md`, `methods.md` and `index.json` beside this file hold the checks, the "
        "methods paragraph, and every file's hash and provenance. Each answer's file carries its "
        "label sentence, its qualifier line and the files it cites.",
        "",
    ]
    return "\n".join(lines)
