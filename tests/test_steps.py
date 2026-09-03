"""M5: deterministic module execution under both runners, evidence parsers."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from stringency.exit_codes import ConfigError
from stringency.machine import StepStatus
from stringency.operator_exec.evidence import parse_evidence
from stringency.operator_exec.submit import submit
from stringency.operator_exec.tickets import job_spec, render_job_spec
from stringency.project import Project
from stringency.runs import RunContext, open_or_resume
from stringency.steps import execute_engine, propose
from tests.conftest import InitFn, accept_hold

EVIDENCE = Path(__file__).parent / "fixtures" / "evidence"


@pytest.fixture
def engine_project(make_project: InitFn) -> Project:
    p = make_project(pipeline="toy-engine", execution="engine")
    h = p.confirm_hold()
    assert h is not None
    accept_hold(p.store, h["hold_id"])
    return p


@pytest.fixture
def rc(confirmed_project: Project) -> RunContext:
    return open_or_resume(confirmed_project)


@pytest.fixture
def erc(engine_project: Project) -> RunContext:
    return open_or_resume(engine_project)


def play_agent(
    spec: dict, log_name: str = "run.log", override_min: float | None = None
) -> tuple[dict[str, Path], Path]:
    """The test agent: run the module script itself from the job spec, capture its log."""
    step_dir = Path(spec["step_dir"])
    work = step_dir.parent / f"agent-{spec['step_id']}"
    work.mkdir(parents=True, exist_ok=True)
    outputs = {k: work / Path(v["suggested_path"]).name for k, v in spec["outputs"].items()}
    params = dict(spec["params"])
    if override_min is not None:
        params["min_value"] = override_min
    job = {
        "inputs": {k: v["path"] for k, v in spec["inputs"].items()},
        "params": params,
        "outputs": {k: str(v) for k, v in outputs.items()},
        "output_dir": str(work),
        "seed": spec["seed"],
    }
    log = work / log_name
    with open(log, "w") as f:
        subprocess.run(
            [sys.executable, spec["script"]],
            input=json.dumps(job),
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
        )
    return outputs, log


# -- engine runner ------------------------------------------------------------------------


def test_engine_runner_end_to_end(erc: RunContext) -> None:
    prop = propose(erc, "01_filter")
    assert prop.status == StepStatus.ADMISSIBLE
    out = execute_engine(erc, prop)
    assert out.status == StepStatus.COMPLETED, out.message
    snap = erc.store.one(
        "SELECT * FROM state_snapshots WHERE run_id=? AND step_id='01_filter'", (erc.run_id,)
    )
    assert snap is not None
    state = json.loads(snap["summary_json"])
    cpg = state["objects"]["object"]["summary"]["counts_per_group"]["group"]
    assert cpg["A"]["unit"] == 3 and cpg["B"]["unit"] == 3
    assert state["history"][0]["operation"] == "filter_rows"
    ex = erc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["runner"] == "engine" and ex["env_status"] == "verified" and ex["exit_code"] == 0
    art = erc.store.one(
        "SELECT * FROM artifacts WHERE run_id=? AND step_id='01_filter'", (erc.run_id,)
    )
    assert Path(art["sidecar_path"]).exists()
    sc = json.loads(Path(art["sidecar_path"]).read_text())
    assert sc["run_id"] == erc.run_id and sc["blake3"] == art["hash"]
    assert erc.run["status"] == "running"


def test_engine_runner_env_unpinned_blocks(engine_project: Project) -> None:
    from stringency import git

    (engine_project.method_root / "envs" / "toy-py" / "uv.lock").unlink()
    git.commit_all(engine_project.method_root, "drop lock")
    rc = open_or_resume(engine_project)
    prop = propose(rc, "01_filter")
    assert prop.status == StepStatus.BLOCKED
    assert [r.spec.id for r in prop.gate.blocked] == ["repro.env_unpinned"]
    assert rc.run["status"] == "blocked"


def test_engine_runner_feasibility_rejects_post(erc: RunContext) -> None:
    prop = propose(erc, "01_filter", {"min_value": 35})
    assert prop.status == StepStatus.ADMISSIBLE, [r.line() for r in prop.gate.blocked]
    out = execute_engine(erc, prop)
    assert out.status == StepStatus.REJECTED
    assert out.gate is not None and [r.spec.id for r in out.gate.blocked] == ["obj.feasibility"]
    assert (
        erc.store.scalar(
            "SELECT status FROM artifacts WHERE run_id=? AND step_id='01_filter'", (erc.run_id,)
        )
        == "rejected"
    )
    # a new attempt is possible after rejection
    prop2 = propose(erc, "01_filter", {"min_value": 10})
    assert prop2.action.attempt == 2 and prop2.status == StepStatus.ADMISSIBLE


def test_engine_runner_script_failure(erc: RunContext) -> None:
    script = erc.project.modules.require("filter-rows@0.1.0").entry_script
    assert script is not None
    script.write_text("import sys; sys.exit(3)\n")
    prop = propose(erc, "01_filter")
    out = execute_engine(erc, prop)
    assert out.status == StepStatus.FAILED
    assert erc.run["status"] == "failed"


# -- operator runner ----------------------------------------------------------------------


def test_propose_issues_ticket_and_job_spec(rc: RunContext) -> None:
    prop = propose(rc, "01_filter", {"min_value": 30}, rationale="values below 30 are noise here")
    assert prop.status == StepStatus.AWAITING_EXECUTION
    assert prop.ticket == prop.action.action_id
    spec = job_spec(prop, rc.env_digests["toy-py"])
    assert spec["params"] == {"min_value": 30} and spec["param_source"] == {"min_value": "agent"}
    assert spec["evidence"] == [{"kind": "job_log", "path": "run.log"}]
    text = render_job_spec(spec)
    assert "min_value = 30" in text and "stringency submit" in text
    assert (
        rc.store.scalar(
            "SELECT proposed_by FROM actions WHERE action_id=?", (prop.action.action_id,)
        )
        == "agent"
    )
    assert rc.store.message(prop.action.rationale_ref or "") == "values below 30 are noise here"


def test_submit_completes_with_engine_extraction(rc: RunContext) -> None:
    prop = propose(rc, "01_filter", {"min_value": 12})
    spec = job_spec(prop, None)
    outputs, log = play_agent(spec)
    out = submit(rc, prop.ticket or "", outputs, [log])
    assert out.status == StepStatus.COMPLETED, out.message
    snap = rc.store.one(
        "SELECT * FROM state_snapshots WHERE run_id=? AND step_id='01_filter'", (rc.run_id,)
    )
    state = json.loads(snap["summary_json"])
    # the engine extracted the state itself; the agent supplied only the file
    assert state["objects"]["object"]["summary"]["counts_per_group"]["group"]["B"]["unit"] == 3
    assert state["objects"]["object"]["summary"]["n_obs"] < 50
    assert snap["extractor"] == "toy.frame"
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["runner"] == "operator" and ex["env_status"] == "as_reported"
    obs = json.loads(ex["observed_params_json"])
    assert obs["params"] == {"min_value": 12}
    row = rc.store.one(
        "SELECT fired, effective_disposition FROM predicate_results WHERE action_id=? AND predicate_id='repro.env_unverified'",
        (prop.action.action_id,),
    )
    assert row["fired"] == 1 and row["effective_disposition"] == "log"


def test_submit_plan_drift_rejects(rc: RunContext) -> None:
    prop = propose(rc, "01_filter", {"min_value": 12})
    outputs, log = play_agent(job_spec(prop, None), override_min=40)
    out = submit(rc, prop.ticket or "", outputs, [log])
    assert out.status == StepStatus.REJECTED
    assert out.gate is not None and "exec.plan_drift" in [r.spec.id for r in out.gate.blocked]


def test_submit_without_ticket_refused(rc: RunContext, tmp_path: Path) -> None:
    f = tmp_path / "x.csv"
    f.write_text("row_id,group,unit,value\n")
    with pytest.raises(ConfigError, match="no ticket"):
        submit(rc, "NOPE", {"object": f}, [])


def test_submit_missing_output_refused(rc: RunContext) -> None:
    prop = propose(rc, "01_filter")
    with pytest.raises(ConfigError, match="not supplied"):
        submit(rc, prop.ticket or "", {}, [])


def test_env_unverified_holds_under_strict(make_project: InitFn) -> None:
    p = make_project(profile="strict")
    h = p.confirm_hold()
    accept_hold(p.store, h["hold_id"])
    rc = open_or_resume(p)
    prop = propose(rc, "01_filter")
    outputs, log = play_agent(job_spec(prop, None))
    out = submit(rc, prop.ticket or "", outputs, [log])
    assert out.status == StepStatus.HELD
    holds = rc.store.all(
        "SELECT * FROM holds WHERE run_id=? AND resolved_by_review IS NULL", (rc.run_id,)
    )
    assert (
        len(holds) == 1
        and holds[0]["kind"] == "flag"
        and "repro.env_unverified" in holds[0]["reason"]
    )
    assert rc.run["status"] == "held"


def test_run_open_captures(rc: RunContext) -> None:
    run = rc.run
    assert run["git_sha"] == rc.project.config.method.sha
    assert run["git_dirty"] == 0 and run["policy_digest"] == rc.policy_digest
    assert rc.store.scalar("SELECT COUNT(*) FROM steps WHERE run_id=?", (rc.run_id,)) == 5
    assert rc.store.scalar("SELECT COUNT(*) FROM policy_snapshots") == 1
    ids = {
        r["predicate_id"]
        for r in rc.store.all(
            "SELECT predicate_id FROM predicate_results WHERE run_id=? AND phase='run_open'",
            (rc.run_id,),
        )
    }
    assert ids == {"repro.dirty_tree", "repro.input_digest_mismatch"}


# -- evidence parsers ---------------------------------------------------------------------


def test_nextflow_trace_real_fixture() -> None:
    obs = parse_evidence("nextflow_trace", EVIDENCE / "nextflow_trace_real.txt")
    assert len(obs.processes) == 12
    assert obs.processes[0]["process"] == "CALC_SPLITS" and obs.processes[0]["status"] == "CACHED"
    assert set(obs.exit_codes) == {0}
    assert obs.containers == [] and "no container column" in obs.notes[0]


def test_nextflow_trace_with_containers() -> None:
    obs = parse_evidence("nextflow_trace", EVIDENCE / "nextflow_trace_containers.txt")
    assert [p["process"] for p in obs.processes] == ["QC", "NORMALIZE", "CLUSTER"]
    assert obs.exit_codes == [0, 0, 1]
    assert "/data/lab/env/sc-r-4.4.sif" in obs.containers
    assert obs.container_digest == "a" * 64


def test_nextflow_log_head() -> None:
    obs = parse_evidence("nextflow_log", EVIDENCE / "nextflow_log_head.txt")
    assert obs.params["input"] == "samplesheet.csv" and obs.params["runRanger"] is False
    assert any("nextflow 24.10.0" in n for n in obs.notes)


def test_job_log_and_apptainer_inspect(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text(
        "starting\nparams: min_value=30 method=bh\nseed: 7\ncontainer: docker://x/y@sha256:"
        + "b" * 64
        + "\nexit code: 0\n"
    )
    obs = parse_evidence("job_log", log)
    assert obs.params == {"min_value": 30, "method": "bh"} and obs.seed == 7
    assert obs.container_digest == "b" * 64 and obs.exit_codes == [0]
    insp = tmp_path / "inspect.json"
    insp.write_text(
        json.dumps(
            {
                "data": {
                    "attributes": {
                        "labels": {
                            "org.label-schema.usage.singularity.deffile.from": "ubuntu:22.04",
                            "image.digest": "sha256:" + "c" * 64,
                        }
                    }
                }
            }
        )
    )
    obs = parse_evidence("apptainer_inspect", insp)
    assert obs.container_digest == "c" * 64
