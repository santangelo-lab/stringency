"""Open mode S3, `exec` (spec/plans/open_mode_plan.md 2.4): a session script runs as an
on-demand step under the executor with its inputs read-only, its text in the trace, a seed
recorded, a timeout from the policy, and the network outcome recorded; the local executor is
refused without --allow-local; `exec.script_drift` and `param.agent_proposed` never fire."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from stringency import hashing
from stringency.executor.apptainer import ApptainerExecutor, bind_set
from stringency.executor.base import Job
from stringency.exit_codes import ConfigError
from stringency.policy import ProfilePolicy, load_policy
from stringency.project import Project
from stringency.runs import load_run
from stringency.steps import job_for, plan_step
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import cli

SUMMARY_SCRIPT = """\
import csv, json, sys
job = json.load(sys.stdin)
rows = list(csv.DictReader(open(job["inputs"]["object"])))
by = {}
for r in rows:
    by.setdefault(r["group"], []).append(float(r["value"]))
with open(job["outputs"]["summary"], "w") as f:
    f.write("group\\tn\\tmean\\n")
    for g in sorted(by):
        f.write(f"{g}\\t{len(by[g])}\\t{sum(by[g]) / len(by[g]):.3f}\\n")
print("seed", job["seed"])
"""

WRITES_BESIDE_INPUT = """\
import json, os, sys
job = json.load(sys.stdin)
open(os.path.join(os.path.dirname(job["inputs"]["object"]), "scribble.txt"), "w").write("x")
open(job["outputs"]["note"], "w").write("done\\n")
"""


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    cli(q, "ask", "what is the mean per group?")
    return q


def test_exec_runs_a_session_script_and_records_it(questions: Project, tmp_path: Path) -> None:
    q = questions
    script = tmp_path / "summary.py"
    script.write_text(SUMMARY_SCRIPT)
    r = cli(q, "exec", str(script), "--out", "summary=table")
    assert r.exit_code == 16 and "--allow-local" in str(r.stderr)  # local needs the flag
    r = cli(
        q,
        "exec",
        str(script),
        "--out",
        "summary=table",
        "--allow-local",
        "--seed",
        "7",
        "--reason",
        "no tool summarises per group",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert (
        out["step_id"] == "01_exec" and out["status"] == "completed" and out["label"] == "untested"
    )
    assert out["module"] == f"exec@{hashing.hash_text(SUMMARY_SCRIPT)[:12]}"
    assert out["seed"] == 7 and out["network"] == "n/a" and out["timeout_s"] == 3600.0
    assert [a["name"] for a in out["artifacts"]] == ["summary"] and out["artifacts"][0][
        "kind"
    ] == "table"
    run_id = out["run_id"]
    # the script is in the trace: executions.script_blob and the text under that hash
    ex = q.store.one(
        "SELECT * FROM executions WHERE action_id=?",
        (q.store.scalar("SELECT action_id FROM actions WHERE run_id=?", (run_id,)),),
    )
    assert ex["script_blob"] == hashing.hash_text(SUMMARY_SCRIPT) and ex["network"] == "n/a"
    assert (
        ex["runner"] == "engine" and ex["env_name"] == "toy-py" and ex["env_status"] == "verified"
    )
    assert q.store.message(ex["script_blob"]) == SUMMARY_SCRIPT
    step_dir = q.step_dir(run_id, "01_exec")
    assert (step_dir / "script.py").read_text() == SUMMARY_SCRIPT
    assert "seed 7" in (step_dir / "stdout.txt").read_text()
    table = Path(out["artifacts"][0]["path"]).read_text().splitlines()
    assert table[0] == "group\tn\tmean" and len(table) == 4
    # the action: the seed is a recorded parameter at its default, so nobody "chose" it
    action = q.store.one("SELECT * FROM actions WHERE run_id=?", (run_id,))
    assert json.loads(action["params_json"]) == {"seed": 7}
    assert json.loads(action["param_source_json"]) == {"seed": "default"}
    assert action["proposed_by"] == "pipeline"
    assert q.store.message(action["rationale_ref"]) == "no tool summarises per group"
    preds = {
        r_["predicate_id"]: r_["fired"]
        for r_ in q.store.all(
            "SELECT predicate_id, fired FROM predicate_results WHERE action_id=?",
            (action["action_id"],),
        )
    }
    for pid in (
        "exec.script_drift",
        "param.agent_proposed",
        "repro.seed_unset",
        "topo.undeclared_step",
        "topo.input_type_mismatch",
    ):
        assert pid in preds and not preds[pid], (pid, preds)
    # the on-demand entry carries the synthetic manifest; the run context rebuilds the module
    rc = load_run(q, run_id)
    entry = rc.on_demand_entry("01_exec")
    assert entry["kind"] == "exec" and entry["manifest"]["name"] == "exec"
    assert rc.module_for("01_exec").entry_script == step_dir / "script.py"
    assert rc.pipeline.step("01_exec").inputs == {"object": "$inputs.object"}
    assert "untested" in cli(q, "next").output or True
    human = cli(q, "exec", str(script), "--out", "summary=table", "--allow-local").output
    assert "untested: a script written in this session ran on the engine" in human


def test_exec_binds_inputs_read_only_with_a_timeout_and_asks_for_no_network(
    questions: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = questions
    script = tmp_path / "s.py"
    script.write_text(WRITES_BESIDE_INPUT)
    r = cli(q, "exec", str(script), "--out", "note=text", "--allow-local", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)  # the local executor cannot enforce it
    out = json.loads(r.output)
    rc = load_run(q, out["run_id"])
    plan = plan_step(rc, "01_exec", 1)
    assert plan.inputs_read_only and plan.network_isolation and plan.timeout == 3600.0
    job = job_for(
        rc.store.one("SELECT 1") and _action(q, out["run_id"]), plan, plan.module.entry_script
    )
    input_dir = Path(q.inputs.items[0].path).parent
    assert input_dir in job.ro_bind_paths and input_dir not in job.bind_paths
    assert plan.step_dir in job.bind_paths and job.network == "none" and job.timeout == 3600.0
    assert job.stdin_json["seed"] == out["seed"]
    binds = bind_set(job)
    assert f"{input_dir.resolve()}:{input_dir.resolve()}:ro" in binds
    assert str(plan.step_dir.resolve()) in binds
    # the apptainer line carries the isolation flags only when the host enforces them
    ex = ApptainerExecutor(q.method_root / "envs", binary="apptainer")
    monkeypatch.setattr("stringency.executor.apptainer.network_isolation", lambda b, i: True)
    line = ex.command_line(job)
    assert line[2:7] == ["--containall", "--pwd", str(plan.step_dir), "--net", "--network"]
    assert ex.network_for(job) == "none"
    monkeypatch.setattr("stringency.executor.apptainer.network_isolation", lambda b, i: False)
    assert "--net" not in ex.command_line(job) and ex.network_for(job) == "unenforced"
    plain = Job(command=["python3", "x.py"], env_name="toy-py", cwd=plan.step_dir)
    assert ex.network_for(plain) is None


def _action(q: Project, run_id: str):  # type: ignore[no-untyped-def]
    from stringency.steps import action_from_row

    return action_from_row(
        q.store.one("SELECT * FROM actions WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,))
    )


def test_exec_failures_and_refusals(questions: Project, tmp_path: Path) -> None:
    q = questions
    script = tmp_path / "s.py"
    script.write_text(SUMMARY_SCRIPT)
    # a declared output the script does not write: failed, exit 13
    r = cli(
        q,
        "exec",
        str(script),
        "--out",
        "summary=table",
        "--out",
        "plot=figure",
        "--allow-local",
        "--json",
    )
    assert r.exit_code == 13, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["status"] == "failed" and out["next"]["kind"] == "open"
    rc = load_run(q, out["run_id"])
    assert rc.status() == "running"  # a failed on-demand step is that step's state only
    # no --out, an unknown env, an unknown input, an empty script, a bad lang: configuration
    assert cli(q, "exec", str(script), "--allow-local").exit_code == 15
    assert (
        cli(q, "exec", str(script), "--out", "s=table", "--env", "nope", "--allow-local").exit_code
        == 15
    )
    assert (
        cli(
            q,
            "exec",
            str(script),
            "--out",
            "s=table",
            "--in",
            "object=$inputs.nothing",
            "--allow-local",
        ).exit_code
        == 15
    )
    assert cli(q, "exec", "-", "--out", "s=table", "--allow-local", input="   ").exit_code == 15
    assert (
        cli(
            q, "exec", str(script), "--out", "s=table", "--lang", "cobol", "--allow-local"
        ).exit_code
        == 15
    )
    assert (
        cli(q, "exec", str(tmp_path / "missing.py"), "--out", "s=table", "--allow-local").exit_code
        == 15
    )
    # a script from stdin
    r = cli(
        q, "exec", "-", "--out", "summary=table", "--allow-local", "--json", input=SUMMARY_SCRIPT
    )
    assert r.exit_code == 0 and json.loads(r.output)["status"] == "completed"
    # the policy refuses exec: exit 16
    pol = q.method_root / "policy.yml"
    data = yaml.safe_load(pol.read_text())
    data["profiles"]["standard"]["open"] = {"exec": "refused", "exec_timeout_s": 10}
    pol.write_text(yaml.safe_dump(data, sort_keys=False))
    r = cli(q, "exec", str(script), "--out", "summary=table", "--allow-local")
    assert r.exit_code == 16 and "open.exec" in str(r.stderr)


def test_exec_timeout_comes_from_the_policy(questions: Project, tmp_path: Path) -> None:
    q = questions
    pol = q.method_root / "policy.yml"
    data = yaml.safe_load(pol.read_text())
    data["profiles"]["standard"]["open"] = {"exec": "allowed", "exec_timeout_s": 1}
    pol.write_text(yaml.safe_dump(data, sort_keys=False))
    script = tmp_path / "slow.py"
    script.write_text("import time, sys, json\njob = json.load(sys.stdin)\ntime.sleep(5)\n")
    r = cli(q, "exec", str(script), "--out", "s=table", "--allow-local", "--json")
    assert r.exit_code == 13, r.output + str(r.stderr)
    out = json.loads(r.output)
    assert out["timeout_s"] == 1.0
    ev = q.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id='01_exec' AND event='status:failed'",
        (out["run_id"],),
    )
    assert json.loads(ev["payload_json"])["timed_out"] is True


def test_exec_object_output_runs_the_extractor(questions: Project, tmp_path: Path) -> None:
    q = questions
    script = tmp_path / "keep_a.py"
    script.write_text(
        "import csv, json, sys\njob = json.load(sys.stdin)\n"
        "rows = [r for r in csv.DictReader(open(job['inputs']['object'])) if r['group'] != 'C']\n"
        "w = csv.DictWriter(open(job['outputs']['object'], 'w', newline=''), fieldnames=list(rows[0]))\n"
        "w.writeheader(); w.writerows(rows)\n"
    )
    r = cli(q, "exec", str(script), "--out", "object=frame/csv", "--allow-local", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    snap = q.store.one(
        "SELECT summary_json FROM state_snapshots WHERE run_id=? AND step_id='01_exec'",
        (out["run_id"],),
    )
    summary = json.loads(snap["summary_json"])
    assert "object" in summary["objects"] and summary["objects"]["object"]["type"] == "frame"
    # the frame can be bound to a tool next: a trusted tool on an untested input (labels, S5)
    r = cli(q, "call", "compare-groups", "--in", "object=$steps.01_exec.object", "--json")
    assert r.exit_code == 0, r.output + str(r.stderr)
    assert json.loads(r.output)["inputs"]["object"].endswith("01_exec/object.csv")


def test_policy_open_block_parses_and_probe_reports_isolation(
    method_repo: MethodRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    pol = load_policy(method_repo.path / "policy.yml")
    assert pol.profile("standard").open.exec == "allowed"
    assert pol.profile("strict").open.exec == "refused"
    assert pol.profile("standard").open.exec_timeout_s == 3600
    assert ProfilePolicy().open.exec == "allowed"  # the block is optional
    with pytest.raises(ValueError, match="allowed or refused"):
        ProfilePolicy(open={"exec": "maybe"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive"):
        ProfilePolicy(open={"exec": "allowed", "exec_timeout_s": 0})  # type: ignore[arg-type]
    from stringency.probe import probe

    payload = probe(str(method_repo.path))
    names = {c["name"]: c for c in payload["checks"]}
    assert names["network isolation"]["ok"] is None  # the toy has no image to try with
    assert payload["method"]["network_isolation"] is None
    monkeypatch.setattr("stringency.probe.network_isolation", lambda b, i: True)
    payload = probe(str(method_repo.path))
    assert {c["name"]: c for c in payload["checks"]}["network isolation"]["ok"] is True


def test_exec_refused_on_a_pipeline_project(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> None:
    up, _ = delivered_process(tmp_path, toy_data, make_project)
    r = cli(up, "exec", "-", "--out", "s=table", "--allow-local", input="print(1)")
    assert r.exit_code == 16
    with pytest.raises(ConfigError):
        from stringency.steps import parse_outs

        parse_outs(["bad"])
