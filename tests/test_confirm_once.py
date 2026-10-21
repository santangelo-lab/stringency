"""Confirm once (`spec/plans/confirm-once.md`; backlog L67, L6, L5, L68, L69): a study's design
is accepted once; identical files, matched inputs and references inherit; the person is told
in advance; identical parameter flags batch and are accepted once."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stringency import hashing
from stringency.deliver import deliver
from stringency.exit_codes import ConfigError
from stringency.project import InitRequest, Project, check_declarations
from stringency.review_batch import batch_view, locate_holds, record_batch
from stringency.runs import load_run
from tests.conftest import InitFn, accept_hold, write_declarations
from tests.test_declare import PROCESS_OBJECTIVE
from tests.test_run import MOCK, cli


@pytest.fixture(autouse=True)
def _tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("stringency.review.detect_via", lambda: "tty")
    monkeypatch.setattr("stringency.review.current_user", lambda: "tester")


def other_data(tmp_path: Path, toy_data: Path, name: str = "data2") -> Path:
    other = tmp_path / name / "groups.csv"
    other.parent.mkdir()
    lines = toy_data.read_text().splitlines()
    other.write_text("\n".join(lines[:-1]) + "\n")
    return other


def inputs_for(path: Path, extra: list[dict] | None = None) -> dict:
    return {
        "inputs": 1,
        "items": [
            {
                "name": "groups",
                "path": str(path),
                "type": "frame",
                "blake3": hashing.hash_file(path),
                "source": "toy fixture",
            },
            *(extra or []),
        ],
    }


def test_a_study_sibling_inherits_the_design_acceptance(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    """L67: the first accepted confirm in a study speaks for every later project of the study
    with the same design and owner, whatever its inputs; no study, another owner or another
    design opens a hold, and the report says why."""
    fa = write_declarations(tmp_path / "a", toy_data)
    a = make_project(
        pipeline="toy-engine",
        execution="engine",
        study="lyons",
        objective=fa["objective.yml"],
        design=fa["design.yml"],
        inputs=fa["inputs.yml"],
    )
    assert a.config.study == "lyons"
    assert a.confirm_status() == "pending"
    assert a.inheritance_report().startswith(
        "confirmation not inherited: no confirmed sibling of study lyons"
    )
    accept_hold(a.store, a.confirm_hold()["hold_id"])

    other = other_data(tmp_path, toy_data)
    fb = write_declarations(tmp_path / "b", other, inputs=inputs_for(other))
    b = make_project(
        pipeline="toy-engine",
        execution="engine",
        study="lyons",
        objective=fb["objective.yml"],
        design=fb["design.yml"],
        inputs=fb["inputs.yml"],
    )
    assert b.confirm_status() == "accepted"
    h = b.confirm_hold()
    assert h["resolved_via"] == "inherited"
    rev = b.store.one("SELECT * FROM reviews WHERE review_id=?", (h["resolved_by_review"],))
    assert rev["via"] == "inherited" and rev["reviewer"] == "tester"
    assert rev["reason"].startswith("by rule `study`: inherited from " + str(a.root))
    echo = b.echo_path().read_text()
    assert (
        "confirmed for this study" in echo
        and "the accepted design does not cover this file" in echo
    )
    assert hashing.hash_file(other)[:12] in echo
    assert b.inheritance_report().startswith(
        "confirmation inherited by rule `study` from " + str(a.root)
    )
    r = cli(b, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output

    # no study: an ordinary hold, and the report says the project names none (c binds a third
    # file, so it re-declares nobody's files)
    third = other_data(tmp_path, toy_data, "data3")
    fc = write_declarations(tmp_path / "c", third, inputs=inputs_for(third))
    c = make_project(
        pipeline="toy-engine",
        execution="engine",
        objective=fc["objective.yml"],
        design=fc["design.yml"],
        inputs=fc["inputs.yml"],
    )
    assert c.confirm_status() == "pending" and "names no study" in c.inheritance_report()
    # another owner in the study: a hold
    fd = write_declarations(tmp_path / "d", other, inputs=inputs_for(other))
    d = make_project(
        pipeline="toy-engine",
        execution="engine",
        study="lyons",
        owner="someone",
        reviewer="someone",
        objective=fd["objective.yml"],
        design=fd["design.yml"],
        inputs=fd["inputs.yml"],
    )
    assert d.confirm_status() == "pending"


def test_a_re_declared_project_inherits(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    """L68: byte-identical declaration files beside a confirmed project, same owner and method,
    carry the acceptance over; one changed byte does not."""
    f = write_declarations(tmp_path / "decl", toy_data)
    a = make_project(
        pipeline="toy-engine",
        execution="engine",
        objective=f["objective.yml"],
        design=f["design.yml"],
        inputs=f["inputs.yml"],
    )
    assert a.confirm_status() == "pending"
    accept_hold(a.store, a.confirm_hold()["hold_id"])
    b = make_project(
        pipeline="toy-engine",
        execution="engine",
        objective=f["objective.yml"],
        design=f["design.yml"],
        inputs=f["inputs.yml"],
    )
    assert b.confirm_status() == "accepted"
    assert b.confirm_hold()["resolved_via"] == "inherited"
    assert "by rule `re-declared`" in b.store.scalar(
        "SELECT reason FROM reviews ORDER BY rowid DESC LIMIT 1"
    )
    assert "byte for byte" in b.echo_path().read_text()
    f2 = write_declarations(
        tmp_path / "decl2",
        toy_data,
        objective={
            "objective": 1,
            "id": "toy_ab_two",
            "question": "compare_groups",
            "contrasts": [["group", "A", "B"]],
            "replication_unit": "unit",
            "min_n_per_group": 2,
            "deliverables": ["comparison_table", "group_labels"],
            "domain": {},
        },
    )
    c = make_project(
        pipeline="toy-engine",
        execution="engine",
        objective=f2["objective.yml"],
        design=f2["design.yml"],
        inputs=f2["inputs.yml"],
    )
    assert c.confirm_status() == "pending"
    assert "no sibling re-declares these files" in c.inheritance_report()


def test_matched_raw_and_reference_inputs_inherit(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    """L5: a downstream project whose inputs are derived from a confirmed upstream, or raw and
    identical to one the upstream bound, or a reference, inherits; a raw input of a new hash
    does not, and the report names it."""
    layout = tmp_path / "layout.csv"
    layout.write_text(toy_data.read_text())
    extra = [
        {
            "name": "layout",
            "path": str(layout),
            "type": "frame",
            "blake3": hashing.hash_file(layout),
            "source": "the slide layout",
        }
    ]
    up_files = write_declarations(
        tmp_path / "up", toy_data, objective=PROCESS_OBJECTIVE, inputs=inputs_for(toy_data, extra)
    )
    up = make_project(
        pipeline="toy-process",
        execution="engine",
        objective=up_files["objective.yml"],
        design=up_files["design.yml"],
        inputs=up_files["inputs.yml"],
    )
    accept_hold(up.store, up.confirm_hold()["hold_id"])
    r = cli(up, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    d = deliver(load_run(up, run_id))
    delivered = d.path / "01_filter.object.csv"
    derived = {
        "name": "groups",
        "path": str(delivered),
        "type": "frame",
        "blake3": hashing.hash_file(delivered),
        "derived_from": {
            "run_id": run_id,
            "step_id": "01_filter",
            "output": "object",
            "project": str(up.root),
        },
    }

    def down(name: str, extra_item: dict) -> Project:
        files = write_declarations(
            tmp_path / name, toy_data, inputs={"inputs": 1, "items": [derived, extra_item]}
        )
        return make_project(
            pipeline="toy-engine",
            execution="engine",
            objective=files["objective.yml"],
            design=files["design.yml"],
            inputs=files["inputs.yml"],
        )

    same = down("down_same", extra[0])
    assert same.confirm_status() == "accepted"
    found = same.inherited_confirmation()
    assert found is not None and found["rule"] == "inputs matched"
    assert found["matched"] == {
        "groups": "derived",
        "layout": f"identical to the input {up.root} bound",
    }
    assert "is raw, identical to the input" in same.echo_path().read_text()

    ref = down("down_ref", {**extra[0], "name": "atlas", "role": "reference"})
    assert ref.confirm_status() == "accepted"
    assert ref.inherited_confirmation()["matched"]["atlas"] == "reference"  # type: ignore[index]

    other = other_data(tmp_path, toy_data, "data3")
    new = down(
        "down_new",
        {
            "name": "layout",
            "path": str(other),
            "type": "frame",
            "blake3": hashing.hash_file(other),
            "source": "another layout",
        },
    )
    assert new.confirm_status() == "pending"
    assert (
        new.inheritance_report()
        == "confirmation not inherited: input layout is raw and no confirmed upstream bound it"
    )


def test_declare_check_and_init_say_so_in_advance(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: object
) -> None:
    """L69: `declare --check` and `init` print which acceptance the confirmation would inherit
    and by which rule, or why not."""
    fa = write_declarations(tmp_path / "a", toy_data)
    a = make_project(
        pipeline="toy-engine",
        execution="engine",
        study="s1",
        objective=fa["objective.yml"],
        design=fa["design.yml"],
        inputs=fa["inputs.yml"],
    )
    accept_hold(a.store, a.confirm_hold()["hold_id"])
    other = other_data(tmp_path, toy_data)
    fb = write_declarations(tmp_path / "b-decl", other, inputs=inputs_for(other))
    req = InitRequest(
        path=tmp_path / "unused",
        method=method_repo.spec,
        pipeline="toy-engine",  # type: ignore[attr-defined]
        objective=fb["objective.yml"],
        design=fb["design.yml"],
        inputs=fb["inputs.yml"],
        owner="tester",
        reviewer="tester",
        judgment_harness="mock",
        execution="engine",
        executor="local",
        study="s1",
        siblings_root=tmp_path,
    )
    res = check_declarations(req)
    assert res.inheritance is not None and res.inheritance.startswith(
        "confirmation inherited by rule `study` from " + str(a.root)
    )
    assert res.to_json()["inheritance"] == res.inheritance
    res2 = check_declarations(InitRequest(**{**req.__dict__, "study": None}))
    assert res2.inheritance is not None and "names no study" in res2.inheritance
    r = cli(
        a,
        "declare",
        str(tmp_path / "b-decl"),
        "--check",
        "--method",
        method_repo.spec,  # type: ignore[attr-defined]
        "--pipeline",
        "toy-engine",
        "--judgment-harness",
        "mock",
        "--execution",
        "engine",
        "--executor",
        "local",
        "--study",
        "s1",
        "--json",
        env={
            "USER": "tester",
            "LOGNAME": "tester",
        },  # declare has no --owner; the user is the owner
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["inheritance"].startswith("confirmation inherited by rule `study`")
    r = cli(
        a,
        "init",
        str(tmp_path / "b"),
        "--method",
        method_repo.spec,
        "--pipeline",
        "toy-engine",  # type: ignore[attr-defined]
        "--objective",
        str(fb["objective.yml"]),
        "--design",
        str(fb["design.yml"]),
        "--inputs",
        str(fb["inputs.yml"]),
        "--owner",
        "tester",
        "--reviewer",
        "tester",
        "--judgment-harness",
        "mock",
        "--execution",
        "engine",
        "--executor",
        "local",
        "--study",
        "s1",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["inheritance"].startswith("confirmation inherited by rule `study`")
    assert Project(tmp_path / "b").confirm_status() == "accepted"


def test_identical_parameter_flags_batch_and_are_accepted_once(
    tmp_path: Path, toy_data: Path, make_project: InitFn
) -> None:
    """L6: identical `param.agent_proposed` holds across study siblings batch into one packet
    and one verdict; a later sibling's identical proposal is resolved by that acceptance; a
    differing packet refuses to batch."""

    def sibling(name: str) -> Project:
        f = write_declarations(tmp_path / name, toy_data)
        p = make_project(
            pipeline="toy-engine",
            execution="engine",
            study="lyons",
            objective=f["objective.yml"],
            design=f["design.yml"],
            inputs=f["inputs.yml"],
        )
        if p.confirm_status() == "pending":
            accept_hold(p.store, p.confirm_hold()["hold_id"])
        return p

    a, b, c, d = (sibling(n) for n in ("a", "b", "c", "d"))
    holds = {}
    for p in (a, b):
        r = cli(
            p,
            "propose",
            "01_filter",
            "--set",
            "min_value=12",
            "--reason",
            "the floor",
            "--json",
            env=MOCK,
        )
        assert r.exit_code == 10, r.output + str(r.stderr)
        holds[p.root.name] = p.store.one("SELECT * FROM holds WHERE kind='flag'")
    members = locate_holds([holds["proj1"]["hold_id"], holds["proj2"]["hold_id"]], [], tmp_path)
    view = batch_view(members)
    assert "2 parameter flag hold(s) on 2 project(s)" in view.text
    assert "min_value: default 10, proposed 12" in view.text
    assert "predicate param.agent_proposed  step 01_filter  module filter-rows@0.1.1" in view.text
    assert [v["verdict"] for v in view.verdicts] == ["accept", "reject"]
    with pytest.raises(ConfigError, match="needs --reason"):
        record_batch(members, "accept", reason=None, attest=False)
    results = record_batch(members, "accept", reason="the floor is right", attest=False)
    assert len(results) == 2
    for p in (a, b):
        assert (
            p.store.scalar(
                "SELECT reason_code FROM reviews WHERE verdict='accept' AND hold_id=?",
                (holds[p.root.name]["hold_id"],),
            )
            == "batch"
        )
    # accept once: the third sibling's identical proposal is resolved by the batch acceptance
    r = cli(
        c,
        "propose",
        "01_filter",
        "--set",
        "min_value=12",
        "--reason",
        "the floor",
        "--json",
        env=MOCK,
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    h = c.store.one("SELECT * FROM holds WHERE kind='flag'")
    assert h["resolved_via"] == "inherited"
    rev = c.store.one("SELECT * FROM reviews WHERE review_id=?", (h["resolved_by_review"],))
    assert rev["via"] == "inherited" and rev["reviewer"] == "tester"
    assert rev["reason"].startswith(
        "accept once (study lyons): the same values were accepted in " + str(a.root)
    )
    # a differing proposal does not inherit, and does not batch with the others
    r = cli(
        d,
        "propose",
        "01_filter",
        "--set",
        "min_value=15",
        "--reason",
        "another floor",
        "--json",
        env=MOCK,
    )
    assert r.exit_code == 10, r.output + str(r.stderr)
    hd = d.store.one("SELECT * FROM holds WHERE kind='flag'")
    assert hd["resolved_via"] is None
    r = cli(
        a,
        "propose",
        "04_compare",
        "--set",
        "correction=bonferroni",
        "--reason",
        "three groups",
        "--json",
        env=MOCK,
    )
    with pytest.raises(ConfigError, match="packets differ"):
        locate_holds([hd["hold_id"], holds["proj1"]["hold_id"]], [], tmp_path)
