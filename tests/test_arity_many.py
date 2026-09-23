"""`arity: many` (module contract amendment, owner 2026-09-23): a pipeline binds a list of
references or a `$inputs.<glob>`; the script receives a list of paths; the action records one
digest for the input; lint guards the wiring."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from stringency import git, hashing
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.pipelines import Ref
from stringency.project import Project
from stringency.runs import open_or_resume
from stringency.steps import plan_step
from stringency_toy import METHOD_TEMPLATE
from tests.conftest import InitFn, MethodRepo, accept_hold, write_declarations
from tests.test_declare import PROCESS_OBJECTIVE
from tests.test_run import MOCK, cli

CONCAT = '''#!/usr/bin/env python3
"""concat_frames: append every input frame, in the order given, into one frame."""
import csv, json, sys
job = json.load(sys.stdin)
paths = job["inputs"]["frames"]
assert isinstance(paths, list), type(paths)
rows, fields = [], None
for p in paths:
    with open(p, newline="") as f:
        r = csv.DictReader(f)
        fields = fields or r.fieldnames
        rows += list(r)
with open(job["outputs"]["object"], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print(f"concatenated {len(paths)} frame(s), {len(rows)} rows")
'''

MODULE = {
    "contract": 1,
    "name": "concat-frames",
    "version": "0.1.0",
    "kind": "deterministic",
    "operation": "filter_rows",
    "domain": "stringency-toy",
    "modes": ["pipeline"],
    "env": "toy-py",
    "runner": "engine",
    "inputs": {"frames": {"type": "frame", "format": "csv", "hash": True, "arity": "many"}},
    "outputs": {"object": {"type": "frame", "format": "csv"}},
    "decision_points": [],
    "stochastic": False,
    "gates": [],
    "resources": {"cpus": 1, "memory": "1GB", "timeout": "5min"},
}

PIPELINE = {
    "pipeline": 1,
    "name": "toy-many",
    "version": "0.1.0",
    "domain": "stringency-toy",
    "answers": ["process_rows"],
    "steps": [
        {
            "id": "01_concat",
            "title": "Concatenate the regions",
            "module": "concat-frames@0.1.0",
            "inputs": {"frames": "$inputs.groups_*"},
            "runner": "engine",
        }
    ],
}


@pytest.fixture
def many_method(tmp_path: Path) -> MethodRepo:
    """The toy method plus a `concat-frames` module with a many input and a `toy-many` pipeline."""
    dest = tmp_path / "method-many"
    shutil.copytree(METHOD_TEMPLATE, dest)
    mod = dest / "modules" / "concat-frames"
    mod.mkdir()
    (mod / "module.yml").write_text(yaml.safe_dump(MODULE, sort_keys=False))
    (mod / "pre.py").write_text(CONCAT)
    (mod / "params.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "additionalProperties": False})
    )
    (dest / "pipelines" / "toy-many.yml").write_text(yaml.safe_dump(PIPELINE, sort_keys=False))
    rep = lint_path(dest)
    assert rep.ok, rep.render()
    git.init_repo(dest)
    sha = git.commit_all(dest, "toy method with a many input")
    git.tag(dest, "v0.1.0")
    return MethodRepo(dest, "v0.1.0", sha)


def two_regions(tmp_path: Path, toy_data: Path) -> dict[str, Path]:
    b = tmp_path / "data_b" / "groups.csv"
    b.parent.mkdir()
    lines = toy_data.read_text().splitlines()
    b.write_text("\n".join([lines[0], *lines[1:11]]) + "\n")  # ten rows, a different hash
    items = []
    for name, path in (("groups_a", toy_data), ("groups_b", b), ("other", toy_data)):
        items.append(
            {
                "name": name,
                "path": str(path),
                "type": "frame",
                "blake3": hashing.hash_file(path),
                "source": "toy fixture",
            }
        )
    return write_declarations(
        tmp_path / "decl-many",
        toy_data,
        objective=PROCESS_OBJECTIVE,
        inputs={"inputs": 1, "items": items},
    )


def test_ref_glob_only_for_inputs() -> None:
    assert Ref.parse("$inputs.groups_*").pattern
    assert not Ref.parse("$inputs.groups").pattern
    with pytest.raises(ConfigError, match="glob binds"):
        Ref.parse("$steps.01_*.object")


def test_glob_binds_matching_inputs_in_name_order_and_the_job_gets_a_list(
    tmp_path: Path, toy_data: Path, many_method: MethodRepo, make_project: InitFn
) -> None:
    files = two_regions(tmp_path, toy_data)
    p: Project = make_project(
        method=many_method.spec,
        pipeline="toy-many",
        execution="engine",
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    plan = plan_step(rc, "01_concat", 1)
    ri = plan.inputs["frames"]
    assert ri.many and [Path(x).parent.name for x in ri.paths] == ["data", "data_b"]  # name order
    assert ri.digest == hashing.hash_json(list(ri.digests))
    with pytest.raises(ConfigError, match="arity many"):
        _ = ri.path
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    action = p.store.one("SELECT * FROM actions WHERE run_id=? AND step_id='01_concat'", (run_id,))
    inputs = json.loads(action["inputs_json"])
    assert inputs["frames"] == "blake3:" + hashing.hash_json(list(ri.digests))
    out = p.store.one(
        "SELECT path FROM artifacts WHERE run_id=? AND step_id='01_concat' AND name='object'",
        (run_id,),
    )
    rows = Path(out["path"]).read_text().splitlines()
    assert len(rows) - 1 == 50 + 10  # both regions, not `other`


def test_lint_refuses_a_list_on_a_one_input_and_many_evidence(tmp_path: Path) -> None:
    dest = tmp_path / "method-bad"
    shutil.copytree(METHOD_TEMPLATE, dest)
    pipe = dest / "pipelines" / "toy-engine.yml"
    doc = yaml.safe_load(pipe.read_text())
    doc["steps"][0]["inputs"]["object"] = ["$inputs.groups", "$inputs.groups"]
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    rep = lint_path(dest)
    assert any("not `arity: many`" in e for e in rep.errors), rep.render()
    # a glob on a one-arity input is refused the same way
    doc["steps"][0]["inputs"]["object"] = "$inputs.gro*"
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert any("not `arity: many`" in e for e in lint_path(dest).errors)
    # judgment evidence may not be many
    mod = dest / "modules" / "label-groups" / "module.yml"
    m = yaml.safe_load(mod.read_text())
    m["inputs"]["summary"]["arity"] = "many"
    mod.write_text(yaml.safe_dump(m, sort_keys=False))
    doc["steps"][0]["inputs"]["object"] = "$inputs.groups"
    pipe.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert any("cannot have arity many" in e for e in lint_path(dest).errors)


def test_glob_matching_nothing_is_refused(
    tmp_path: Path, toy_data: Path, many_method: MethodRepo, make_project: InitFn
) -> None:
    files = write_declarations(tmp_path / "decl-none", toy_data, objective=PROCESS_OBJECTIVE)
    p: Project = make_project(
        method=many_method.spec,
        pipeline="toy-many",
        execution="engine",
        objective=files["objective.yml"],
        design=files["design.yml"],
        inputs=files["inputs.yml"],
    )
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    with pytest.raises(ConfigError, match="resolved to nothing"):
        plan_step(rc, "01_concat", 1)
