"""L106: an admitted Action's values cannot change after it is built, through the caller's
proposal (an alias), a nested list, or a predicate holding the Action in its context, before
or after it is written; its parameters are checked against `params_hash` when written and
before a job is built, and its inputs against what the plan resolves then."""

from __future__ import annotations

import copy
import json
import pickle
from dataclasses import replace
from typing import Any

import pytest
import yaml

from stringency import hashing
from stringency.actions import Action, build_action, write_action
from stringency.exit_codes import StringencyError
from stringency.frozen import FrozenDict, FrozenList, freeze, thaw
from stringency.gate import run_predicate
from stringency.predicates import GateContext, registry
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.steps import StepPlan, action_from_row, job_for, plan_step, propose
from tests.helpers import make_ctx

STEP = "01_filter"


def _plan(project: Project) -> tuple[Any, StepPlan]:
    rc = open_or_resume(project)
    return rc, plan_step(rc, STEP, 1)


def _action(project: Project, proposed: dict[str, Any]) -> Action:
    """An Action as `propose` builds it: the plan's input digests, the caller's proposal."""
    rc, plan = _plan(project)
    return build_action(
        run_id=rc.run_id,
        step=plan.step,
        module=plan.module,
        attempt=1,
        input_digests={k: v.digest for k, v in plan.inputs.items()},
        proposed=proposed,
    )


def _job_params(project: Project, action: Action) -> dict[str, Any]:
    _, plan = _plan(project)
    script = plan.module.entry_script
    assert script is not None
    return dict(job_for(action, plan, script).stdin_json or {})["params"]


def _proposal() -> dict[str, Any]:
    # `groups` and `nested` are undeclared: recorded, then blocked by the gate, which is all
    # this needs
    return {"min_value": 12, "groups": ["A", "B"], "nested": {"cut": [1, 2]}}


def _refused(fn: Any) -> None:
    with pytest.raises(TypeError, match="read-only"):
        fn()


def test_the_callers_proposal_is_not_the_actions(confirmed_project: Project) -> None:
    proposal = _proposal()
    action = _action(confirmed_project, proposal)
    # build_action copies the outer mapping; the nested values were shared before L106
    proposal["groups"].append("C")
    proposal["nested"]["cut"][0] = 99
    assert action.parameters["groups"] == ["A", "B"]
    assert action.parameters["nested"] == {"cut": [1, 2]}
    assert action.params_hash == hashing.prefixed(hashing.hash_json(action.parameters))


def test_every_value_refuses_a_change_in_place(confirmed_project: Project) -> None:
    action = _action(confirmed_project, _proposal())
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
    # calling __init__ again changes nothing, at the top or nested
    params.__init__(y=3)  # type: ignore[misc]
    params["groups"].__init__(["Z"])  # type: ignore[misc]
    assert "y" not in params and params["groups"] == ["A", "B"]
    assert isinstance(params, dict) and isinstance(params["groups"], list)
    assert json.loads(json.dumps(params)) == thaw(params)
    assert pickle.loads(pickle.dumps(params)) == params


def test_a_copy_to_change_is_thaw_and_copy_is_deep(confirmed_project: Project) -> None:
    params = _action(confirmed_project, _proposal()).parameters
    for mine in (thaw(params), params.copy(), copy.deepcopy(params), copy.copy(params)):
        mine["groups"].append("C")
        mine["nested"]["cut"].append(3)
        assert type(mine) is dict and type(mine["groups"]) is list
    # dict(x) is shallow, as for any dict: the nested values are still the Action's
    _refused(lambda: dict(params)["groups"].append("C"))
    assert params["groups"] == ["A", "B"] and params["nested"]["cut"] == [1, 2]


def test_a_deep_copy_of_the_action_is_the_action(confirmed_project: Project) -> None:
    action = _action(confirmed_project, _proposal())
    twin = copy.deepcopy(action)
    assert isinstance(twin.parameters, FrozenDict)
    _refused(lambda: twin.parameters["groups"].append("C"))


def test_yaml_dumps_a_frozen_value_as_plain(confirmed_project: Project) -> None:
    params = _action(confirmed_project, _proposal()).parameters
    assert yaml.safe_load(yaml.safe_dump(params)) == thaw(params)
    assert yaml.safe_dump(params) == yaml.safe_dump(thaw(params))


@pytest.mark.parametrize(
    "value",
    [
        {True: 1, False: 2},  # YAML 1.1 yes/no/on/off read as booleans
        {None: "tilde"},
        {1: "a", 2.5: "b"},
        {"é": "ünï", "日本": [1.0, 2.5e-10, -0.0]},
        {"b": 1, "a": {"y": 2, "x": 3}},
    ],
)
def test_keys_and_values_json_writes_differently_are_not_refused(
    confirmed_project: Project, value: dict[Any, Any]
) -> None:
    action = _action(confirmed_project, {"min_value": 12, "odd": value})
    write_action(confirmed_project.store, action)  # refused before the keys agreed
    assert _job_params(confirmed_project, action)["odd"] == json.loads(json.dumps(value))
    # the same mapping in another key order hashes the same
    again = _action(confirmed_project, {"odd": dict(reversed(value.items())), "min_value": 12})
    assert again.params_hash == action.params_hash


def test_a_predicate_cannot_change_what_runs(confirmed_project: Project) -> None:
    project = confirmed_project
    action = _action(project, {"min_value": 12, "groups": ["A"]})
    before = _job_params(project, action)

    def nested(ctx: GateContext) -> Any:
        ctx.action.parameters["groups"].append("B")

    def top(ctx: GateContext) -> Any:
        ctx.action.parameters["min_value"] = 0

    spec = registry.get("param.undeclared")
    assert spec is not None
    ctx = make_ctx(project, STEP, action=action)
    for meddle in (nested, top):
        verdict = run_predicate(replace(spec, fn=meddle), ctx)
        assert verdict.fired and "read-only" in (verdict.reason or ""), meddle.__name__
    assert ctx.action is action
    assert _job_params(project, action) == before
    assert before["min_value"] == 12 and before["groups"] == ["A"]


def test_after_persistence_the_row_is_what_was_proposed(confirmed_project: Project) -> None:
    p = confirmed_project
    rc = open_or_resume(p)
    proposal = {"min_value": 12, "nested": {"cut": [1, 2]}}
    prop = propose(rc, STEP, proposal, rationale="twelve")
    # a nested value of the caller's proposal: shared with the Action before L106
    proposal["nested"]["cut"].append(3)
    assert prop.action.parameters["nested"]["cut"] == [1, 2]
    row = p.store.one("SELECT * FROM actions WHERE action_id = ?", (prop.action.action_id,))
    assert row is not None and json.loads(row["params_json"])["nested"] == {"cut": [1, 2]}
    back = action_from_row(row)
    assert isinstance(back.parameters["nested"]["cut"], FrozenList)
    _refused(lambda: back.parameters["nested"]["cut"].append(3))
    assert back.params_hash == prop.action.params_hash
    assert _job_params(p, back)["nested"] == {"cut": [1, 2]}


def test_a_hash_that_no_longer_matches_is_refused(confirmed_project: Project) -> None:
    project = confirmed_project
    action = _action(project, {"min_value": 12})
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


def test_inputs_resolved_differently_from_the_admitted_ones_build_no_job(
    confirmed_project: Project,
) -> None:
    action = _action(confirmed_project, {"min_value": 12})
    assert _job_params(confirmed_project, action)["min_value"] == 12
    name = next(iter(action.inputs))
    other = Action(**{**action.__dict__, "inputs": {name: "blake3:" + "11" * 32}})
    with pytest.raises(StringencyError, match=f"inputs resolved now differ.*{name}"):
        _job_params(confirmed_project, other)


def test_freeze_and_thaw() -> None:
    value = {"a": [1, {"b": (2, 3)}], "c": "x"}
    frozen = freeze(value)
    assert isinstance(frozen["a"], FrozenList) and isinstance(frozen["a"][1], FrozenDict)
    assert frozen == {"a": [1, {"b": [2, 3]}], "c": "x"}
    assert freeze(frozen) is frozen
    # built directly, a frozen value is frozen all the way down
    direct = FrozenDict({"l": [1]})
    _refused(lambda: direct["l"].append(2))
    plain = thaw(frozen)
    assert type(plain) is dict and type(plain["a"]) is list
    plain["a"].append(4)
    assert len(frozen["a"]) == 2
