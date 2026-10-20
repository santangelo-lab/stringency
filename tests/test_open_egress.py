"""Open mode against the egress ceiling (backlog L40, L41): the upstream's ceiling is inherited
by `init --from-delivery`, a session script is a component of the assessment, and under the
local executor it is class 4 and refused over the ceiling before it runs."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from stringency.egress import assess
from tests.conftest import InitFn, MethodRepo
from tests.test_open_init import delivered_process
from tests.test_run import cli


def test_exec_is_a_component_by_enforcement() -> None:
    a = assess(
        steps=[],
        modules={},
        harness="mock",
        execution="engine",
        max_class=3,
        operator="none",
        exec_allowed=True,
        executor="apptainer",
    )
    comp = {c.key: c for c in a.components}
    assert comp["exec"].cls == 0 and comp["exec"].basis == "by enforcement" and a.within
    b = assess(
        steps=[],
        modules={},
        harness="mock",
        execution="engine",
        max_class=3,
        operator="none",
        exec_allowed=True,
        executor="local",
    )
    assert {c.key: c.cls for c in b.components}["exec"] == 4 and b.within is False
    c = assess(
        steps=[],
        modules={},
        harness="mock",
        execution="engine",
        max_class=3,
        operator="none",
        exec_allowed=False,
        executor="local",
    )
    assert "exec" not in {x.key for x in c.components}


def test_open_project_inherits_the_upstream_ceiling_and_exec_is_blocked_over_it(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, delivery = delivered_process(tmp_path, toy_data, make_project)
    cfg_path = up.root / "stringency.yml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["egress"] = {"max_class": 2, "operator": "none"}
    cfg_path.write_text(yaml.safe_dump(cfg))
    common = [
        "--method",
        method_repo.spec,
        "--mode",
        "open",
        "--from-delivery",
        str(delivery),
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--execution",
        "engine",
        "--operator-model",
        "none",
        "--owner",
        "tester",
        "--reviewer",
        "tester",
    ]
    r = cli(up, "init", str(tmp_path / "q"), *common, "--json")
    assert r.exit_code in (10, 15), r.output + str(r.stderr)
    q_cfg = (
        yaml.safe_load((tmp_path / "q" / "stringency.yml").read_text())
        if (tmp_path / "q" / "stringency.yml").exists()
        else None
    )
    if r.exit_code == 15:
        # the inherited ceiling 2 is below the open setup's class under the local executor (4):
        # init refuses, naming the session scripts
        assert "init.egress_exceeds_ceiling" in (r.output + str(r.stderr))
        assert "session scripts" in (r.output + str(r.stderr))
        return
    assert q_cfg and q_cfg["egress"]["max_class"] == 2
    data = json.loads(r.output)
    assert data.get("confirm_hold")
