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
from tests.conftest import InitFn, MethodRepo, accept_hold, admit

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
    prop = admit(erc, propose(erc, "01_filter", {"min_value": 35}))
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
    script = erc.project.modules.require("filter-rows@0.1.1").entry_script
    assert script is not None
    script.write_text("import sys; sys.exit(3)\n")
    prop = propose(erc, "01_filter")
    out = execute_engine(erc, prop)
    assert out.status == StepStatus.FAILED
    assert erc.run["status"] == "failed"


# -- operator runner ----------------------------------------------------------------------


def test_propose_issues_ticket_and_job_spec(rc: RunContext) -> None:
    prop = admit(
        rc, propose(rc, "01_filter", {"min_value": 30}, rationale="values below 30 are noise here")
    )
    assert prop.status == StepStatus.AWAITING_EXECUTION
    assert prop.ticket == prop.action.action_id
    spec = job_spec(prop, rc.env_digests["toy-py"])
    assert spec["params"] == {"min_value": 30} and spec["param_source"] == {"min_value": "agent"}
    assert spec["evidence"] == [
        {"kind": "job_log", "path": "run.log"},
        {"kind": "apptainer_inspect", "path": "inspect.json"},
    ]
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
    prop = admit(rc, propose(rc, "01_filter", {"min_value": 12}))
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
    prop = admit(rc, propose(rc, "01_filter", {"min_value": 12}))
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


# -- improvements B1, C1, C2 (2026-09-08) -----------------------------------------------------


def test_ticket_writes_job_json_and_prints_exec_and_submit(rc: RunContext) -> None:
    """B1: at ticket time the step directory exists, job.json is there, and the spec carries
    the exact exec line and the submit line (with --command) for `next --json` and `propose`."""
    from stringency.steps import job_for

    prop = admit(rc, propose(rc, "01_filter", {"min_value": 30}))
    assert prop.status == StepStatus.AWAITING_EXECUTION
    step_dir = prop.plan.step_dir
    job_json = step_dir / "job.json"
    assert job_json.exists()
    assert prop.plan.module.entry_script is not None
    expected = dict(job_for(prop.action, prop.plan, prop.plan.module.entry_script).stdin_json or {})
    assert json.loads(job_json.read_text()) == expected
    assert expected["params"] == {"min_value": 30} and expected["output_dir"] == str(step_dir)
    spec = job_spec(prop, None, rc.executor)
    assert spec["job_json"] == str(job_json) and spec["log"] == str(step_dir / "run.log")
    assert spec["exec"] is not None
    assert spec["exec"].startswith("python3 ") and spec["exec"].endswith(
        f" < {job_json} > {step_dir / 'run.log'} 2>&1"
    )
    assert f"--outputs object={step_dir / 'object.csv'}" in spec["submit"]
    assert f"--evidence {step_dir / 'run.log'}" in spec["submit"]
    assert "--command '" in spec["submit"] and spec["exec"] in spec["submit"].replace(
        "'\"'\"'", "'"
    )
    text = render_job_spec(spec)
    assert f"job.json written: {job_json}" in text and f"run: {spec['exec']}" in text
    # a spec without an executor carries no exec line and a submit without --command
    plain = job_spec(prop, None)
    assert plain["exec"] is None and "--command" not in plain["submit"]
    # job.json carries no sidecar: it is a ticket artifact, not an output
    assert not (step_dir / "job.json.stringency.json").exists()


def test_operator_can_run_the_printed_lines(rc: RunContext) -> None:
    """The exec line from the ticket, run as printed, produces outputs `submit` accepts."""
    import subprocess

    prop = admit(rc, propose(rc, "01_filter", {"min_value": 12}))
    spec = job_spec(prop, None, rc.executor)
    assert spec["exec"] is not None
    subprocess.run(spec["exec"], shell=True, check=True, executable="/bin/bash")
    assert Path(spec["log"]).exists()
    outputs = {k: Path(v["suggested_path"]) for k, v in spec["outputs"].items()}
    assert all(p.exists() for p in outputs.values())
    out = submit(rc, prop.ticket or "", outputs, [Path(spec["log"])], command=spec["exec"])
    assert out.status == StepStatus.COMPLETED, out.message
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["command"] == spec["exec"]  # C2: the operator's account, recorded as reported
    assert ex["runner"] == "operator"


def test_apptainer_ticket_exec_line(tmp_path: Path) -> None:
    from stringency.executor.apptainer import ApptainerExecutor
    from stringency.executor.base import Job

    envs = tmp_path / "envs"
    envs.mkdir()
    sif = tmp_path / "toy.sif"
    sif.write_bytes(b"not really a sif")
    (envs / "manifest.yml").write_text(
        f"environments:\n  toy-py:\n    image: {sif}\n    sha256: {'0' * 64}\n"
    )
    step = tmp_path / "runs" / "R" / "01"
    step.mkdir(parents=True)
    script = tmp_path / "tools" / "filter.py"
    script.parent.mkdir()
    script.write_text("")
    job = Job(command=["python3", str(script)], env_name="toy-py", cwd=step, bind_paths=[step])
    argv = ApptainerExecutor(envs, binary="apptainer").command_line(job)
    assert argv[:5] == ["apptainer", "exec", "--containall", "--pwd", str(step)]
    assert "--bind" in argv and str(sif) in argv and argv[-2:] == ["python3", str(script)]


def test_execution_digest_columns(rc: RunContext, erc: RunContext) -> None:
    """C1: operator rows keep the expected digest apart and leave env_digest null; engine rows
    that verified the environment carry both."""
    prop = admit(rc, propose(rc, "01_filter", {"min_value": 12}))
    outputs, log = play_agent(job_spec(prop, None))
    submit(rc, prop.ticket or "", outputs, [log])
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["env_status"] == "as_reported" and ex["env_digest"] is None
    assert ex["expected_env_digest"] == rc.env_digests["toy-py"]
    assert ex["command"] is None  # nothing reported
    eprop = propose(erc, "01_filter")
    execute_engine(erc, eprop)
    eex = erc.store.one("SELECT * FROM executions WHERE action_id=?", (eprop.action.action_id,))
    assert eex["env_status"] == "verified"
    assert eex["env_digest"] == eex["expected_env_digest"] == erc.env_digests["toy-py"]
    assert eex["command"]  # the engine's own command line


# -- improvement C3 (2026-09-08): env verification on operator steps -------------------------


def test_apptainer_inspect_with_checksum_line(tmp_path: Path) -> None:
    labels = {"org.label-schema.usage.singularity.deffile.from": "python:3.12-slim"}
    text = (
        json.dumps({"data": {"attributes": {"labels": labels}}, "type": "container"}, indent=1)
        + "\n"
        + "a" * 64
        + "  /home/x/envs/toy-py.sif\n"
    )
    f = tmp_path / "inspect.json"
    f.write_text(text)
    obs = parse_evidence("apptainer_inspect", f)
    assert obs.container_digest == "a" * 64 and obs.containers == ["/home/x/envs/toy-py.sif"]
    assert obs.processes[0]["labels"] == labels
    # a bare JSON document, as before, still parses and reports no digest
    f.write_text(json.dumps({"data": {"attributes": {"labels": labels}}}))
    obs = parse_evidence("apptainer_inspect", f)
    assert obs.container_digest is None and obs.processes[0]["labels"] == labels


FAKE_APPTAINER = """#!/bin/bash
# A stand-in for apptainer in tests: `inspect --json <image>` prints a label stub;
# `exec [--containall] [--pwd D] [--bind B]... <image> <cmd...>` runs <cmd> on the host, with
# python3 resolved to the test interpreter so the toy scripts see the same Python.
if [ "$1" = inspect ]; then
  echo '{"data": {"attributes": {"labels": {"org.label-schema.usage.singularity.deffile.from": "python:3.12-slim"}}}, "type": "container"}'
  exit 0
fi
shift
while [ $# -gt 0 ]; do
  case "$1" in
    --containall) shift ;;
    --pwd|--bind) shift 2 ;;
    *) break ;;
  esac
done
shift  # the image
if [ "$1" = python3 ]; then shift; set -- "$STRINGENCY_TEST_PYTHON" "$@"; fi
exec "$@"
"""


def _pinned_method(tmp_path: Path, method_repo: MethodRepo) -> tuple[str, Path, str]:
    """A method spec whose manifest names a (fake) image and its sha256, tagged for init."""
    import hashlib

    from stringency import git

    sif = tmp_path / "envs" / "toy-py.sif"
    sif.parent.mkdir(exist_ok=True)
    sif.write_bytes(b"not a real sif")
    sha = hashlib.sha256(sif.read_bytes()).hexdigest()
    manifest = method_repo.path / "envs" / "manifest.yml"
    manifest.write_text(
        manifest.read_text()
        .replace("image: null", f"image: {sif}")
        .replace("sha256: null", f"sha256: {sha}")
    )
    git.commit_all(method_repo.path, "pin the toy image")
    git.tag(method_repo.path, "v0.1.0-pinned")
    return f"{method_repo.path}@v0.1.0-pinned", sif, sha


def test_operator_env_verified_through_inspect_evidence(
    tmp_path: Path, make_project: InitFn, method_repo: MethodRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strict profile, apptainer project: the operator runs the ticket's evidence command as
    printed; the execution is verified and repro.env_unverified does not hold. A checksum that
    disagrees with the manifest is plan drift and is rejected."""
    import os
    import subprocess

    fake = tmp_path / "bin" / "apptainer"
    fake.parent.mkdir()
    fake.write_text(FAKE_APPTAINER)
    fake.chmod(0o755)
    monkeypatch.setenv("STRINGENCY_APPTAINER_BIN", str(fake))
    monkeypatch.setenv("STRINGENCY_TEST_PYTHON", sys.executable)
    spec_ref, sif, sha = _pinned_method(tmp_path, method_repo)
    p = make_project(profile="strict", executor="apptainer", method=spec_ref)
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    rc = open_or_resume(p)
    assert rc.env_digests["toy-py"] == sha  # the executor verified the pinned image
    prop = propose(rc, "01_filter")
    spec = job_spec(prop, rc.env_digests["toy-py"], rc.executor)
    ev = {e["kind"]: e for e in spec["evidence_commands"]}
    insp = prop.plan.step_dir / "inspect.json"
    assert ev["apptainer_inspect"]["command"] == (
        f"{{ {fake} inspect --json {sif}; sha256sum {sif}; }} > {insp}"
    )
    assert ev["job_log"]["command"] is None
    assert f"--evidence {prop.plan.step_dir / 'run.log'} --evidence {insp}" in spec["submit"]
    assert spec["exec"] is not None and spec["exec"].startswith(f"{fake} exec --containall --pwd ")
    # the operator runs the three printed lines: exec, the evidence command, submit
    env = {**os.environ, "STRINGENCY_TEST_PYTHON": sys.executable}
    subprocess.run(spec["exec"], shell=True, check=True, executable="/bin/bash", env=env)
    subprocess.run(
        ev["apptainer_inspect"]["command"], shell=True, check=True, executable="/bin/bash", env=env
    )
    assert insp.read_text().splitlines()[-1].split()[0] == sha
    outputs = {k: Path(v["suggested_path"]) for k, v in spec["outputs"].items()}
    out = submit(rc, prop.ticket or "", outputs, [Path(spec["log"]), insp], command=spec["exec"])
    assert out.status == StepStatus.COMPLETED, out.message
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["env_status"] == "verified" and ex["command"] == spec["exec"]
    assert ex["env_digest"] == ex["expected_env_digest"] == sha
    fired = rc.store.scalar(
        "SELECT fired FROM predicate_results WHERE action_id=? AND predicate_id='repro.env_unverified'",
        (prop.action.action_id,),
    )
    assert fired == 0
    # a checksum that does not match the manifest: not verified, and exec.plan_drift rejects
    prop2 = propose(rc, "02_summarize")
    spec2 = job_spec(prop2, None, rc.executor)
    assert spec2["exec"] is not None
    subprocess.run(spec2["exec"], shell=True, check=True, executable="/bin/bash", env=env)
    insp2 = prop2.plan.step_dir / "inspect.json"
    insp2.write_text("{}\n" + "f" * 64 + f"  {sif}\n")
    outputs2 = {k: Path(v["suggested_path"]) for k, v in spec2["outputs"].items()}
    out2 = submit(rc, prop2.ticket or "", outputs2, [Path(spec2["log"]), insp2])
    assert out2.status == StepStatus.REJECTED
    assert out2.gate is not None and "exec.plan_drift" in [r.spec.id for r in out2.gate.blocked]
    ex2 = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop2.action.action_id,))
    assert ex2["env_status"] == "as_reported" and ex2["env_digest"] is None
    assert ex2["expected_env_digest"] == sha


def test_apptainer_ticket_names_the_evidence_command(tmp_path: Path) -> None:
    import hashlib

    from stringency.executor.apptainer import ApptainerExecutor
    from stringency.operator_exec.tickets import evidence_command

    envs = tmp_path / "envs"
    envs.mkdir()
    sif = tmp_path / "toy.sif"
    sif.write_bytes(b"sif")
    (envs / "manifest.yml").write_text(
        f"environments:\n  toy-py:\n    image: {sif}\n    sha256: {hashlib.sha256(b'sif').hexdigest()}\n"
    )
    ex = ApptainerExecutor(envs, binary="apptainer")
    e = evidence_command("apptainer_inspect", tmp_path / "step" / "inspect.json", ex, "toy-py")
    assert (
        e["command"]
        == f"{{ apptainer inspect --json {sif}; sha256sum {sif}; }} > {tmp_path / 'step' / 'inspect.json'}"
    )
    assert evidence_command("job_log", tmp_path / "run.log", ex, "toy-py")["command"] is None
    assert evidence_command("nextflow_trace", tmp_path / "t.txt", ex, "toy-py")["note"].startswith(
        "produced by"
    )
    assert (
        evidence_command("apptainer_inspect", tmp_path / "i.json", ex, "no-such-env")["command"]
        is None
    )


# -- exec.script_drift (2026-09-09): the code that ran is the code present at run open ---------


def test_operator_step_with_edited_script_is_rejected(rc: RunContext) -> None:
    """The run opened clean; the script is edited after the ticket; submit hashes it and
    exec.script_drift blocks. The executions row keeps the hash of what ran."""
    from stringency import hashing

    prop = admit(rc, propose(rc, "01_filter", {"min_value": 12}))
    spec = job_spec(prop, None, rc.executor)
    script = prop.plan.module.entry_script
    assert script is not None
    at_open = rc.script_blobs["filter-rows@0.1.1"]
    assert spec["script_blob"] == at_open == hashing.hash_file(script)
    script.write_text(script.read_text() + "\n# edited after the ticket was issued\n")
    outputs, log = play_agent(spec)
    out = submit(rc, prop.ticket or "", outputs, [log])
    assert out.status == StepStatus.REJECTED
    assert out.gate is not None
    fired = {r.spec.id: r for r in out.gate.blocked}
    assert "exec.script_drift" in fired
    ev = fired["exec.script_drift"].verdict.evidence
    assert ev["at_open"] == at_open and ev["at_execution"] == hashing.hash_file(script)
    assert ev["path"] == "modules/filter-rows/pre.py"
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["script_blob"] == hashing.hash_file(script)


def test_engine_step_with_edited_script_is_rejected(erc: RunContext) -> None:
    script = erc.project.modules.require("filter-rows@0.1.1").entry_script
    assert script is not None
    script.write_text(script.read_text() + "\n# edited after run open\n")
    prop = propose(erc, "01_filter")
    out = execute_engine(erc, prop)
    assert out.status == StepStatus.REJECTED, out.message
    assert out.gate is not None and "exec.script_drift" in [r.spec.id for r in out.gate.blocked]


def test_unedited_scripts_pass_and_dirty_run_measures_from_open(make_project: InitFn) -> None:
    """Must-pass: a clean run records equal hashes. A run opened with --allow-dirty compares
    against the tree at open, so the uncommitted edit it declared is not drift."""
    from stringency import hashing

    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    script = p.modules.require("filter-rows@0.1.1").entry_script
    assert script is not None
    script.write_text(script.read_text() + "\n# uncommitted edit before open\n")
    rc = open_or_resume(p, allow_dirty="testing an edit before committing it")
    assert rc.git_dirty and rc.script_blobs["filter-rows@0.1.1"] == hashing.hash_file(script)
    prop = propose(rc, "01_filter")
    out = execute_engine(rc, prop)
    assert out.status == StepStatus.COMPLETED, out.message
    ex = rc.store.one("SELECT * FROM executions WHERE action_id=?", (prop.action.action_id,))
    assert ex["script_blob"] == rc.script_blobs["filter-rows@0.1.1"]
    # a resumed context reads the same blobs back from the captures event
    rc2 = open_or_resume(p)
    assert rc2.run_id == rc.run_id and rc2.script_blobs == rc.script_blobs
    assert set(rc.script_blobs) == {
        "filter-rows@0.1.1",
        "summarize-groups@0.1.1",
        "compare-groups@0.1.0",
        "toy-report@0.1.1",
    }  # label-groups is a judgment module with no script: nothing to hash, nothing to drift


def test_job_carries_design_and_objective(rc: RunContext) -> None:
    """E1: a module script learns the bound design and objective from the job it is fed."""
    from stringency.steps import job_for

    prop = propose(rc, "01_filter")
    script = prop.plan.module.entry_script
    assert script is not None
    job = job_for(prop.action, prop.plan, script).stdin_json or {}
    assert job["design"] == rc.project.design.model_dump()
    assert job["objective"] == rc.project.objective.model_dump()
    assert set(job) >= {"inputs", "params", "outputs", "output_dir", "seed", "design", "objective"}


def test_ticket_step_dir_holds_tmp(rc: RunContext) -> None:
    """K8: the printed apptainer line binds <step dir>/tmp; the ticket creates it."""
    prop = propose(rc, "01_filter")
    assert prop.status == StepStatus.AWAITING_EXECUTION
    assert (prop.plan.step_dir / "tmp").is_dir()
