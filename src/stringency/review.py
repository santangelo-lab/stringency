"""Review (design 7.3 through 7.6): the hold queue, what a reviewer sees, verdicts and their
effects, binding, and reviewer identity.

Reads: holds, reviews, judgments, consensus, actions, steps (display: `review_render`). Writes: reviews, holds
(resolution), consensus, steps and step_events (through `machine.transition`), artifacts.
"""

from __future__ import annotations

import getpass
import json
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any

from stringency.artifacts import step_outputs
from stringency.clock import now_iso
from stringency.exit_codes import ConfigError, RefusedError
from stringency.ids import new_id
from stringency.machine import StepStatus, step_status, transition
from stringency.project import Project
from stringency.review_render import HoldView, render
from stringency.runs import RunContext, load_run
from stringency.schemas import validate

VERDICTS = ("accept", "override", "reject", "defer")


def detect_via() -> str | None:
    """`tty` when review runs attached to a terminal, else None (the caller must attest)."""
    try:
        return "tty" if os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno()) else None
    except (OSError, ValueError):
        return None


def current_user() -> str:
    return os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser()


def queue(project: Project, run_id: str | None = None) -> list[Any]:
    """Unresolved holds oldest first; the project-level confirm hold comes first when open."""
    if run_id:
        return project.store.all(
            "SELECT * FROM holds WHERE resolved_by_review IS NULL AND (run_id = ? OR run_id IS NULL) ORDER BY run_id IS NOT NULL, created, rowid",
            (run_id,),
        )
    return project.store.all(
        "SELECT * FROM holds WHERE resolved_by_review IS NULL ORDER BY run_id IS NOT NULL, created, rowid"
    )


def get_hold(project: Project, hold_id: str) -> Any:
    h = project.store.one("SELECT * FROM holds WHERE hold_id = ?", (hold_id,))
    if h is None:
        raise ConfigError(f"no hold {hold_id}")
    return h


def _replicates_for(project: Project, h: Any) -> list[dict[str, Any]]:
    rows = project.store.all(
        "SELECT * FROM judgments WHERE run_id = ? AND step_id = ? AND item_id = ? ORDER BY replicate",
        (h["run_id"], h["step_id"], h["item_id"]),
    )
    out = []
    for r in rows:
        out.append(
            {
                "replicate": r["replicate"],
                "label": r["label"],
                "ontology_id": r["ontology_id"],
                "confidence": r["confidence"],
                "abstain": bool(r["abstain"]),
                "supporting": json.loads(r["supporting_json"]),
                "contradicting": json.loads(r["contradicting_json"]),
                "rationale": project.store.message(r["rationale_ref"])
                if r["rationale_ref"]
                else "",
            }
        )
    return out


def show(project: Project, h: Any) -> HoldView:
    """What the reviewer sees (design 7.3); rendering lives in `review_render`."""
    return render(project, h)


@dataclass
class ReviewResult:
    review_id: str
    hold_id: str
    verdict: str
    via: str
    step_status: str | None
    run_status: str | None

    def to_json(self) -> dict[str, Any]:
        return {"schema": "stringency.review/1", **self.__dict__}


def record_review(
    project: Project,
    hold_id: str,
    verdict: str,
    *,
    reason: str | None = None,
    correction: dict[str, Any] | None = None,
    replicate: int | None = None,
    attest: bool = False,
    via_override: str | None = None,
    reason_code: str | None = None,
) -> ReviewResult:
    """Record one verdict and apply its effect (design 7.3, 7.5). Writes: reviews (with
    `operator_session_ref` and `operator_harness` from the environment), holds, consensus, steps,
    step_events, artifacts, run_events."""
    if verdict not in VERDICTS:
        raise ConfigError(f"verdict must be one of {', '.join(VERDICTS)}")
    h = get_hold(project, hold_id)
    if h["resolved_by_review"] is not None:
        raise RefusedError(f"hold {hold_id} is already resolved")
    profile = project.policy.profile(project.config.profile)
    via = via_override or ("relayed" if attest else detect_via())
    if via is None:
        raise RefusedError(
            "review needs a terminal, or --attest after the person confirmed in the conversation"
        )
    if via == "relayed" and not profile.relayed_review:
        raise RefusedError(
            f"profile {project.config.profile} does not accept relayed review (--attest); review at a terminal"
        )
    if via == "relayed" and not os.environ.get("STRINGENCY_SESSION_REF"):
        raise RefusedError(
            "--attest needs STRINGENCY_SESSION_REF set to the operator's session reference; "
            "a relayed verdict names the session it came from (design 7.5)"
        )
    user = current_user()
    role = h["waits_on_role"]
    allowed = (
        {project.config.roles.owner}
        if role == "owner"
        else {project.config.roles.reviewer, project.config.roles.owner}
    )
    if user not in allowed:
        raise RefusedError(
            f"hold {hold_id} waits on {role} ({', '.join(sorted(allowed))}); you are {user}"
        )

    is_item = h["item_id"] is not None
    if verdict in ("accept", "reject") and not is_item and not reason:
        raise ConfigError(f"{verdict} needs --reason")
    if verdict == "reject" and not reason:
        raise ConfigError("reject needs --reason")
    if verdict == "override":
        if not reason:
            raise ConfigError("override needs --reason")
        if not is_item:
            raise ConfigError("override applies to item holds; a flag is accepted or rejected")
        if not correction:
            raise ConfigError("override needs --correction '{\"label\": ...}'")
        _validate_correction(project, h, correction)
    replicates = _replicates_for(project, h) if is_item else []
    if verdict == "accept" and is_item:
        valid = [r for r in replicates if not r["abstain"]]
        if replicate is None:
            labels = {r["label"] for r in valid}
            if len(labels) != 1:
                raise ConfigError("accept on an item hold needs --replicate n to choose a call")
            replicate = valid[0]["replicate"]
        elif not any(r["replicate"] == replicate and not r["abstain"] for r in replicates):
            raise ConfigError(f"replicate {replicate} made no call for item {h['item_id']}")

    review_id = new_id()
    store = project.store
    with store.transaction():
        store.insert(
            "reviews",
            {
                "review_id": review_id,
                "hold_id": hold_id,
                "run_id": h["run_id"],
                "step_id": h["step_id"],
                "item_id": h["item_id"],
                "reviewer": user,
                "host": socket.gethostname(),
                "via": via,
                "operator_session_ref": os.environ.get("STRINGENCY_SESSION_REF"),
                "operator_harness": os.environ.get("STRINGENCY_OPERATOR"),
                "ts": now_iso(),
                "verdict": verdict,
                "correction_json": correction,
                "reason": reason,
                "reason_code": reason_code,
                "bound_module_version": h["bound_module_version"],
                "bound_input_digest": h["bound_input_digest"],
                "bound_params_hash": h["bound_params_hash"],
                "bound_item_evidence_digest": h["bound_item_evidence_digest"],
                "chosen_replicate": replicate,
            },
        )
        if reason:
            (project.root / "prov" / "justifications").mkdir(parents=True, exist_ok=True)
            (project.root / "prov" / "justifications" / f"{review_id}.md").write_text(reason + "\n")
        if verdict == "defer":
            return ReviewResult(review_id, hold_id, verdict, via, None, None)
        store.resolve_hold(hold_id, review_id, via)
        if h["kind"] == "confirm":
            return ReviewResult(review_id, hold_id, verdict, via, None, None)
        rc = load_run(project, h["run_id"])
        if is_item:
            _apply_item_verdict(project, h, verdict, review_id, replicate, correction, replicates)
        step_st = _settle_step(rc, h, verdict)
        run_st = rc.refresh_status()
    return ReviewResult(review_id, hold_id, verdict, via, str(step_st), run_st)


def _validate_correction(project: Project, h: Any, correction: dict[str, Any]) -> None:
    """A correction is validated against the module schema and vocabulary at entry (design 7.3)."""
    module = project.modules.get(h["bound_module_version"]) if h["bound_module_version"] else None
    if module is None:
        raise ConfigError(f"module {h['bound_module_version']} is not in the method repo")
    m = module.manifest
    if "label" not in correction:
        raise ConfigError("correction needs a label")
    if m.vocabulary:
        vocab = project.plugin.vocabulary(m.vocabulary) or ()
        if correction["label"] is not None and correction["label"] not in vocab:
            raise ConfigError(f"label {correction['label']!r} is not in vocabulary {m.vocabulary}")
    schema = module.output_schema
    if schema is not None:
        probe = {
            "item_id": str(h["item_id"]),
            "label": correction["label"],
            "ontology_id": correction.get("ontology_id"),
            "confidence": correction.get("confidence", "high"),
            "abstain": False,
            "supporting_evidence": correction.get("supporting_evidence", []),
            "contradicting_evidence": [],
            "rationale": correction.get("rationale", "reviewer correction"),
        }
        errors = validate(probe, schema)
        if errors:
            raise ConfigError("correction fails the module schema: " + "; ".join(errors))


def _apply_item_verdict(
    project: Project,
    h: Any,
    verdict: str,
    review_id: str,
    replicate: int | None,
    correction: dict[str, Any] | None,
    replicates: list[dict[str, Any]],
) -> None:
    """Writes: consensus for the item (design 8.4 `source`)."""
    store = project.store
    row = store.one(
        "SELECT * FROM consensus WHERE run_id=? AND step_id=? AND item_id=?",
        (h["run_id"], h["step_id"], h["item_id"]),
    )
    base = (
        dict(row)
        if row
        else {
            "run_id": h["run_id"],
            "step_id": h["step_id"],
            "item_id": h["item_id"],
            "replicate_labels_json": json.dumps([r["label"] for r in replicates]),
            "replicate_confidence_json": json.dumps([r["confidence"] for r in replicates]),
        }
    )
    if verdict == "accept":
        chosen = next(r for r in replicates if r["replicate"] == replicate)
        base.update(
            label=chosen["label"],
            ontology_id=chosen["ontology_id"],
            source="accepted",
            review_id=review_id,
        )
    elif verdict == "override":
        assert correction is not None
        base.update(
            label=correction["label"],
            ontology_id=correction.get("ontology_id"),
            source="override",
            review_id=review_id,
        )
    else:
        base.update(source="unresolved", review_id=review_id)
    store.set_consensus({k: v for k, v in base.items() if k in store.columns("consensus")})


def _settle_step(rc: RunContext, h: Any, verdict: str) -> StepStatus:
    """A hold's effect on its step (design 7.1): every hold accepted or overridden moves a
    pre-phase hold to admissible and a post-phase hold to completed; a reject closes the attempt.
    When the hold was the last item hold of a judgment step, the consensus output is rewritten
    from the decided consensus and the post-phase gates are evaluated on it
    (`judgment.resettle_after_item_holds`, design 8.4); the step completes only if nothing flags."""
    store = rc.store
    step_id = h["step_id"]
    ctx = json.loads(h["context_json"] or "{}")
    phase = ctx.get("phase", "post")
    current = step_status(store, rc.run_id, step_id)
    if current != StepStatus.HELD:
        return current
    if verdict == "reject":
        if phase == "pre":
            transition(
                store,
                rc.run_id,
                step_id,
                StepStatus.BLOCKED,
                payload={"review": h["resolved_by_review"]},
            )
            return StepStatus.BLOCKED
        for a in step_outputs(store, rc.run_id, step_id).values():
            store.set_artifact_flag(a["artifact_id"], "status", "rejected")
        transition(
            store,
            rc.run_id,
            step_id,
            StepStatus.REJECTED,
            payload={"review": h["resolved_by_review"]},
        )
        return StepStatus.REJECTED
    remaining = store.scalar(
        "SELECT COUNT(*) FROM holds WHERE run_id=? AND step_id=? AND resolved_by_review IS NULL",
        (rc.run_id, step_id),
    )
    if remaining:
        return StepStatus.HELD
    if phase == "pre":
        transition(store, rc.run_id, step_id, StepStatus.ADMISSIBLE)
        return StepStatus.ADMISSIBLE
    if h["item_id"] is not None:
        from stringency.judgment import resettle_after_item_holds

        return resettle_after_item_holds(rc, step_id).status
    transition(store, rc.run_id, step_id, StepStatus.COMPLETED)
    return StepStatus.COMPLETED
