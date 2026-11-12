"""L106: an admitted Action's values cannot change after it is built, through the caller's
proposal (an alias), a nested list, or a predicate holding the Action in its context, before
or after it is written; its parameters are checked against `params_hash` when written and
before a job is built."""

from __future__ import annotations

import copy
import json
import pickle
from dataclasses import replace
from typing import Any

import pytest

from stringency import hashing
from stringency.actions import Action, write_action
from stringency.exit_codes import StringencyError
from stringency.frozen import FrozenDict, FrozenList, freeze, thaw
from stringency.gate import run_predicate
from stringency.predicates import GateContext, registry
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.steps import action_from_row, job_for, plan_step, propose
from tests.conftest import InitFn
from tests.helpers import make_action, make_ctx
from tests.test_run import confirmed

STEP = "01_filter"


def _proposal() -> dict[str, Any]:
    # `groups` is undeclared: recorded, then blocked by the gate, which is all this needs
    return {"min_value": 12, "groups": ["A", "B"], "nested": {"cut": [1, 2]}}


def _job_params(project: Project, action: Action) -> dict[str, Any]:
    rc = open_or_resume(project)
    plan = plan_step(rc, STEP, 1)
    script = plan.module.entry_script
    assert script is not None
    return dict(job_for(action, plan, script).stdin_json or {})["params"]


def _refused(fn: Any) -> None:
    with pytest.raises(TypeError, match="read-only"):
        fn()


def test_the_callers_proposal_is_not_the_actions(project: Project) -> None:
    proposal = _proposal()
    action, _ = make_action(project, STEP, proposed=proposal)
    # make_action copies the outer mapping, as build_action's callers do; the nested values
    # were shared before L106
    proposal["groups"].append("C")
    proposal["nested"]["cut"][0] = 99
    assert action.parameters["groups"] == ["A", "B"]
    assert action.parameters["nested"] == {"cut": [1, 2]}
    assert action.params_hash == hashing.prefixed(hashing.hash_json(action.parameters))


def test_every_value_refuses_a_change_in_place(project: Project) -> None:
    action, _ = make_action(project, STEP, proposed=_proposal())
    params = action.parameters
    _refused(lambda: params.__setitem__("min_value", 0))
    _refused(lambda: params.pop("min_value"))
    _refused(lambda: params.update(min_value=0))
    _refused(lambda: params["groups"].append("C"))
    _refused(lambda: params["groups"].__setitem__(0, "Z"))
    _refused(lambda: params["groups"].sort())
    _refused(lambda: params["nested"]["cut"].extend([3]))
    _refused(lambda: action.param_source.__setitem__("min_value", "default"))
    _refused(lambda: action.inputs.clear())
    # still a dict and a list to every reader, and a copy is the caller's to change
    assert isinstance(params, dict) and isinstance(params["groups"], list)
    assert json.loads(json.dumps(params)) == thaw(params)
    assert params["nested"] == {"cut": [1, 2]}
    mine = copy.deepcopy(params)
    mine["groups"].append("C")
    assert params["groups"] == ["A", "B"]
    assert pickle.loads(pickle.dumps(params)) == params


def test_a_predicate_cannot_change_what_runs(confirmed_project: Project) -> None:
    project = confirmed_project
    action, _ = make_action(project, STEP, proposed={"min_value": 12, "groups": ["A"]})
    before = _job_params(project, action)

    def meddle(ctx: GateContext) -> Any:
        ctx.action.parameters["groups"].append("B")
        ctx.action.parameters["min_value"] = 0
        raise AssertionError("unreachable")

    spec = registry.get("param.undeclared")
    assert spec is not None
    ctx = make_ctx(project, STEP, action=action)
    verdict = run_predicate(replace(spec, fn=meddle), ctx)
    assert verdict.fired and "read-only" in (verdict.reason or "")
    assert ctx.action is action
    assert _job_params(project, action) == before
    assert before["min_value"] == 12 and before["groups"] == ["A"]


def test_after_persistence_the_row_is_read_back_read_only(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    rc = open_or_resume(p, new=True)
    proposal = {"min_value": 12}
    prop = propose(rc, STEP, proposal, rationale="twelve")
    proposal["min_value"] = 99
    row = p.store.one("SELECT * FROM actions WHERE action_id = ?", (prop.action.action_id,))
    assert row is not None and json.loads(row["params_json"])["min_value"] == 12
    back = action_from_row(row)
    assert isinstance(back.parameters, FrozenDict)
    _refused(lambda: back.parameters.__setitem__("min_value", 0))
    assert back.params_hash == prop.action.params_hash
    assert _job_params(p, back)["min_value"] == 12


def test_a_hash_that_no_longer_matches_is_refused(confirmed_project: Project) -> None:
    project = confirmed_project
    action, _ = make_action(project, STEP, proposed={"min_value": 12})
    # only a deliberate bypass of the read-only containers can do this
    dict.__setitem__(action.parameters, "min_value", 0)
    with pytest.raises(StringencyError, match="hash to"):
        write_action(project.store, action)
    assert (
        project.store.scalar(
            "SELECT COUNT(*) FROM actions WHERE action_id = ?", (action.action_id,)
        )
        == 0
    )
    with pytest.raises(StringencyError, match="before its job was built"):
        _job_params(project, action)


def test_freeze_and_thaw() -> None:
    value = {"a": [1, {"b": (2, 3)}], "c": "x"}
    frozen = freeze(value)
    assert isinstance(frozen["a"], FrozenList) and isinstance(frozen["a"][1], FrozenDict)
    assert frozen == {"a": [1, {"b": [2, 3]}], "c": "x"}
    assert freeze(frozen) is frozen
    plain = thaw(frozen)
    assert type(plain) is dict and type(plain["a"]) is list
    plain["a"].append(4)
    assert len(frozen["a"]) == 2
