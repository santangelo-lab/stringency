"""A fixed policy's verdict is recorded as that (design 7.5, 2026-11-10; PLAN L162). The
benchmark's hold policy answered every hold with `review --attest`, so its verdicts sat in the
trace as `via: relayed` under the reviewer's own account, told from a person's only by a
session reference that began `policy:`. `review --policy <name>` records `via: policy`, and
no report words such a verdict as a person's review."""

from __future__ import annotations

import json

import pytest

from stringency.deliver import deliver
from stringency.project import Project
from stringency.review import policy_of
from stringency.review import queue as review_queue
from stringency.runs import load_run
from tests.conftest import InitFn, accept_hold
from tests.test_run import MOCK, cli

SESSION = {"STRINGENCY_SESSION_REF": "policy:observe:rep1"}


@pytest.fixture(autouse=True)
def _reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")
    monkeypatch.delenv("STRINGENCY_SESSION_REF", raising=False)


def _held(make_project: InitFn, **kw: object) -> tuple[Project, str]:
    p = make_project(pipeline="toy-engine", execution="engine", **kw)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "propose", "01_filter", "--set", "min_value=12", "--reason", "a floor", "--json")
    assert r.exit_code in (10, 11), r.output
    holds = review_queue(p)
    return p, (holds[0]["hold_id"] if holds else "")


def _review(p: Project, hold: str, *extra: str, env: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    return cli(p, "review", "--verdict", "accept", "--hold", hold, *extra, "--json", env=env)


def test_a_policy_s_verdict_is_recorded_via_policy_and_reported_as_no_person_s(
    make_project: InitFn,
) -> None:
    p, hold = _held(make_project)
    rule = "observe: every hold is accepted and recorded"
    r = _review(p, hold, "--policy", "observe", "--reason", rule, env=SESSION)
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["via"] == "policy"
    row = p.store.one("SELECT * FROM reviews WHERE hold_id=?", (hold,))
    assert (row["via"], row["operator_harness"], row["operator_session_ref"]) == (
        "policy",
        "policy:observe",
        "policy:observe:rep1",
    )
    assert policy_of(row) == "observe" and row["reason"] == rule
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    assert cli(p, "audit").exit_code == 0
    d = deliver(load_run(p, run_id))
    assert "verdicts recorded by a fixed policy, not by a person: 1 (observe)" in d.coverage
    cov = json.loads((d.path / "coverage.json").read_text())
    assert cov["gate"]["policy_verdicts"] == {"n": 1, "policies": ["observe"]}
    assert cov["gate"]["flags"][0]["policy"] == "observe"
    assert "accept by the fixed policy `observe`" in d.summary
    assert "no person reviewed it" in d.summary and "by tester via policy" not in d.summary


def test_a_policy_s_verdict_is_refused_without_its_own_reference_reason_or_name(
    make_project: InitFn,
) -> None:
    p, hold = _held(make_project)
    r = _review(p, hold, "--policy", "observe", "--reason", "rule")
    assert r.exit_code == 16 and "STRINGENCY_SESSION_REF" in r.output + str(r.stderr)
    r = _review(p, hold, "--policy", "observe", env=SESSION)
    assert r.exit_code == 15 and "the rule that decided" in r.output + str(r.stderr)
    r = _review(p, hold, "--policy", "ob serve", "--reason", "rule", env=SESSION)
    assert r.exit_code == 15 and "--policy names the policy" in r.output + str(r.stderr)
    r = _review(p, hold, "--policy", "observe", "--attest", "--reason", "rule", env=SESSION)
    assert r.exit_code == 15 and "not combined with --attest" in r.output + str(r.stderr)
    assert p.store.scalar("SELECT COUNT(*) FROM reviews WHERE hold_id=?", (hold,)) == 0
    # a person's relayed verdict is unchanged
    r = _review(p, hold, "--attest", "--reason", "the person said yes", env=SESSION)
    assert r.exit_code == 0 and json.loads(r.output)["via"] == "relayed"
    assert policy_of(p.store.one("SELECT * FROM reviews WHERE hold_id=?", (hold,))) is None


def test_a_profile_that_refuses_relayed_review_refuses_a_policy_too(
    make_project: InitFn,
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine", profile="strict")
    hold = p.confirm_hold()["hold_id"]
    r = _review(p, hold, "--policy", "observe", "--reason", "rule", env=SESSION)
    assert r.exit_code == 16, r.output
    assert "a fixed policy's verdict (--policy) is refused" in r.output + str(r.stderr)
