"""L130: a step's CPU and memory allocation. The min rule and its sources, the policy's cap,
the step's started event, `job.json`, the local executor's environment, the apptainer line,
and the lint warning on a script that takes the host's core count."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from stringency import git
from stringency.executor.apptainer import ApptainerExecutor
from stringency.executor.base import Job
from stringency.executor.local import LocalExecutor, interpreter_for
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.modules import Resources
from stringency.policy import load_policy
from stringency.project import Project
from stringency.resources import (
    THREAD_VARS,
    Override,
    allocate,
    env_for,
    host_core_reads,
    parse_duration_s,
    parse_memory_gb,
)
from stringency_toy import METHOD_TEMPLATE
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_open_init import delivered_process, open_project
from tests.test_run import MOCK, cli, confirmed

MODULE = Resources(cpus=4, memory="64GB", timeout="2h")


# -- parsing -------------------------------------------------------------------------------


def test_memory_and_duration_parse_the_forms_methods_write() -> None:
    assert parse_memory_gb("64GB") == 64 and parse_memory_gb("2GB") == 2
    assert parse_memory_gb("64G") == 64 and parse_memory_gb("64") == 64
    assert parse_memory_gb("512MB") == 0.5 and parse_memory_gb("1TB") == 1024
    assert parse_memory_gb(None) is None
    assert parse_duration_s("30min") == 1800 and parse_duration_s("30m") == 1800
    assert parse_duration_s("12h") == 43200 and parse_duration_s("90s") == 90
    assert parse_duration_s(None) is None
    for bad in ("lots", "0GB", "-2"):
        with pytest.raises(ConfigError):
            parse_memory_gb(bad)
    with pytest.raises(ConfigError):
        parse_duration_s("a while")


def test_override_from_the_cli_options() -> None:
    assert Override.from_options(None, None) is None
    assert Override.from_options(8, "64") == Override(cpus=8, memory_gb=64)
    assert Override.from_options(None, "96GB") == Override(memory_gb=96)
    with pytest.raises(ConfigError, match="--cpus"):
        Override.from_options(0, None)
    with pytest.raises(ConfigError, match="--memory"):
        Override.from_options(None, "much")


# -- the min rule --------------------------------------------------------------------------


def test_the_module_value_with_no_override_and_no_cap() -> None:
    a = allocate(MODULE)
    assert a.job_value() == {"cpus": 4, "memory_gb": 64, "timeout_s": 7200}
    assert a.source == {"cpus": "module", "memory_gb": "module", "timeout_s": "module"}


def test_the_override_raises_or_lowers_the_module_value() -> None:
    up = allocate(MODULE, override=Override(cpus=8, memory_gb=128))
    assert (up.cpus, up.memory_gb) == (8, 128)
    assert up.source["cpus"] == "override" and up.source["memory_gb"] == "override"
    down = allocate(MODULE, override=Override(cpus=2))
    assert (down.cpus, down.memory_gb) == (2, 64)
    assert down.source["cpus"] == "override" and down.source["memory_gb"] == "module"


def test_the_policy_cap_bounds_the_module_and_the_override() -> None:
    a = allocate(MODULE, override=Override(cpus=40), max_cpus=24, max_memory_gb=32)
    assert (a.cpus, a.memory_gb) == (24, 32)
    assert a.source["cpus"] == "policy" and a.source["memory_gb"] == "policy"
    under = allocate(MODULE, override=Override(cpus=16), max_cpus=24, max_memory_gb=200)
    assert (under.cpus, under.memory_gb) == (16, 64)
    assert under.source == {"cpus": "override", "memory_gb": "module", "timeout_s": "module"}


def test_a_module_without_resources_takes_the_cap_or_nothing() -> None:
    assert allocate(Resources()).job_value() == {"cpus": None, "memory_gb": None, "timeout_s": None}
    a = allocate(Resources(), max_cpus=24)
    assert a.cpus == 24 and a.source["cpus"] == "policy" and a.memory_gb is None


def test_an_exec_timeout_replaces_the_module_timeout() -> None:
    a = allocate(MODULE, timeout_s=3600.0)
    assert a.timeout_s == 3600 and a.source["timeout_s"] == "policy"


# -- the policy ----------------------------------------------------------------------------


def _policy_with(tmp_path: Path, block: object) -> Path:
    data = yaml.safe_load((METHOD_TEMPLATE / "policy.yml").read_text())
    if block is not None:
        data["resources"] = block
    p = tmp_path / "policy.yml"
    p.write_text(yaml.safe_dump(data, sort_keys=False))
    return p


def test_policy_parses_the_resources_cap(tmp_path: Path) -> None:
    assert load_policy(_policy_with(tmp_path, None)).resources is None
    cap = load_policy(_policy_with(tmp_path, {"max_cpus": 24, "max_memory_gb": 200})).resources
    assert cap is not None and (cap.max_cpus, cap.max_memory_gb) == (24, 200)
    only = load_policy(_policy_with(tmp_path, {"max_cpus": 24})).resources
    assert only is not None and only.max_memory_gb is None
    for bad in ({"max_cpus": 0}, {"max_memory_gb": -1}, {"max_gpus": 1}):
        with pytest.raises(ConfigError):
            load_policy(_policy_with(tmp_path, bad))


# -- the run: the event and job.json -------------------------------------------------------


def _cap_method(method_repo: MethodRepo, cap: dict[str, object]) -> None:
    """Give the toy method's policy a `resources` cap and tag it, so a project binds it."""
    path = method_repo.path / "policy.yml"
    data = yaml.safe_load(path.read_text())
    data["resources"] = cap
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    method_repo.sha = method_repo.commit("policy: a resources cap")
    git.tag(method_repo.path, "v0.1.1")
    method_repo.tag = "v0.1.1"


def _started(p: Project, run_id: str, step_id: str, status: str) -> dict:
    row = p.store.one(
        "SELECT payload_json FROM step_events WHERE run_id=? AND step_id=? AND event=? "
        "ORDER BY seq DESC LIMIT 1",
        (run_id, step_id, f"status:{status}"),
    )
    assert row is not None
    return json.loads(row["payload_json"])


def test_run_records_the_allocation_and_its_sources_in_the_started_event(
    make_project: InitFn, method_repo: MethodRepo
) -> None:
    _cap_method(method_repo, {"max_cpus": 2, "max_memory_gb": 64})
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "run", "--json", "--cpus", "3", "--memory", "4", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    # filter-rows declares {cpus: 1, memory: 1GB, timeout: 5min}: --cpus 3 is capped at 2,
    # --memory 4 is under the cap, the timeout is the module's
    ev = _started(p, run_id, "01_filter", "running")
    assert ev["resources"] == {"cpus": 2, "memory_gb": 4, "timeout_s": 300}
    assert ev["resources_source"] == {
        "cpus": "policy",
        "memory_gb": "override",
        "timeout_s": "module",
    }
    assert ev["cgroups"] == "not_used"  # the local executor enforces no limit
    # a second invocation without options: the module's values, under the cap
    r2 = cli(p, "run", "--new", "--json", env=MOCK)
    assert r2.exit_code == 0, r2.output
    ev2 = _started(p, json.loads(r2.output)["run_id"], "01_filter", "running")
    assert ev2["resources"] == {"cpus": 1, "memory_gb": 1, "timeout_s": 300}
    assert set(ev2["resources_source"].values()) == {"module"}


def test_an_operator_step_writes_the_allocation_to_job_json(make_project: InitFn) -> None:
    p = confirmed(make_project)
    r = cli(p, "run", "--json", "--cpus", "6", env=MOCK)
    assert r.exit_code == 21, r.output
    out = json.loads(r.output)
    job = json.loads((p.step_dir(out["run_id"], "01_filter") / "job.json").read_text())
    assert job["resources"] == {"cpus": 6, "memory_gb": 1, "timeout_s": 300}
    assert list(job)[-1] == "resources"  # added after the keys scripts already read
    ev = _started(p, out["run_id"], "01_filter", "awaiting_execution")
    assert ev["resources"] == job["resources"]
    assert ev["resources_source"]["cpus"] == "override"


def test_run_refuses_a_bad_option_before_opening_a_run(make_project: InitFn) -> None:
    p = confirmed(make_project, pipeline="toy-engine", execution="engine")
    r = cli(p, "run", "--memory", "plenty", env=MOCK)
    assert r.exit_code == 15, r.output
    assert p.store.scalar("SELECT COUNT(*) FROM runs") == 0


# -- the executors -------------------------------------------------------------------------


def test_the_local_executor_sets_the_allocation_in_the_environment(tmp_path: Path) -> None:
    names = ["STRINGENCY_CPUS", "STRINGENCY_MEMORY_GB", *THREAD_VARS]
    script = tmp_path / "env.py"
    script.write_text(
        "import os\nprint(' '.join(os.environ.get(k, '-') for k in " + repr(names) + "))\n"
    )
    res = LocalExecutor(tmp_path / "envs").run(
        Job(
            command=interpreter_for(script),
            env_name="e1",
            cwd=tmp_path / "w",
            resources={"cpus": 3, "memory_gb": 12, "timeout_s": None},
        )
    )
    assert res.exit_code == 0, res.stderr()
    assert res.stdout().split() == ["3", "12", "3", "3", "3", "3"]
    assert env_for({"cpus": None, "memory_gb": None}) == {}


def _apptainer(tmp_path: Path) -> tuple[ApptainerExecutor, Job]:
    envs = tmp_path / "envs"
    envs.mkdir()
    image = tmp_path / "img.sif"
    image.write_text("not an image")
    (envs / "manifest.yml").write_text(
        yaml.safe_dump({"environments": {"e1": {"image": str(image)}}})
    )
    job = Job(
        command=["python3", "x.py"],
        env_name="e1",
        cwd=tmp_path / "w",
        resources={"cpus": 4, "memory_gb": 64, "timeout_s": 7200},
    )
    return ApptainerExecutor(envs, binary="apptainer"), job


def test_the_apptainer_line_carries_the_environment_and_limits_where_the_host_takes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ex, job = _apptainer(tmp_path)
    monkeypatch.setattr("stringency.executor.apptainer.cgroup_limits", lambda b, i: True)
    line = ex.command_line(job)
    assert line[line.index("STRINGENCY_CPUS=4") - 1 :][:2] == ["--env", "STRINGENCY_CPUS=4"]
    assert "OMP_NUM_THREADS=4" in line and "STRINGENCY_MEMORY_GB=64" in line
    assert line[line.index("--cpus") + 1] == "4" and line[line.index("--memory") + 1] == "64G"
    assert ex.limits_for(job) == "applied"
    # a host without cgroup delegation: the environment still, no limit flags, never a failure
    monkeypatch.setattr("stringency.executor.apptainer.cgroup_limits", lambda b, i: False)
    line = ex.command_line(job)
    assert "--cpus" not in line and "--memory" not in line and "STRINGENCY_CPUS=4" in line
    assert ex.limits_for(job) == "unavailable"
    # nothing allocated: nothing asked
    bare = Job(command=["python3", "x.py"], env_name="e1", cwd=tmp_path / "w")
    assert ex.limits_for(bare) == "not_used" and "--env" not in ex.command_line(bare)


# -- lint ----------------------------------------------------------------------------------


@pytest.fixture
def method_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "method"
    shutil.copytree(METHOD_TEMPLATE, dest)
    return dest


def test_lint_warns_on_a_script_that_takes_the_host_core_count(method_copy: Path) -> None:
    mod = method_copy / "modules" / "filter-rows"
    helper = mod / "workers.py"
    # a comment line is not a read; the word in a trailing comment is not reading the job
    helper.write_text(
        "import os\n# not this: os.cpu_count()\nn = min(8, os.cpu_count() or 1)\n"
        "N = 8  # the module's resources block says 8 cpus\n"
    )
    rscript = mod / "workers.R"
    rscript.write_text("workers <- as.integer(min(8L, parallel::detectCores()))\n")
    report = lint_path(method_copy)
    assert report.ok, report.render()
    hits = [w for w in report.warnings if "core count" in w]
    assert any("workers.py reads the host's core count (line 3)" in w for w in hits), hits
    assert any("workers.R reads the host's core count (line 1)" in w for w in hits), hits
    assert host_core_reads(helper) == [(3, "n = min(8, os.cpu_count() or 1)")]
    # a script that reads the job's allocation as well passes
    helper.write_text(
        "import json, os, sys\njob = json.load(sys.stdin)\n"
        "n = (job.get('resources') or {}).get('cpus') or os.cpu_count()\n"
    )
    rscript.write_text("n <- Sys.getenv('STRINGENCY_CPUS', unset = parallel::detectCores())\n")
    report = lint_path(method_copy)
    assert not [w for w in report.warnings if "core count" in w], report.warnings


def test_lint_warns_on_a_resources_value_it_cannot_read(method_copy: Path) -> None:
    path = method_copy / "modules" / "filter-rows" / "module.yml"
    data = yaml.safe_load(path.read_text())
    data["resources"] = {"cpus": 1, "memory": "a lot", "timeout": "5min"}
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    report = lint_path(method_copy)
    assert any("resources.memory" in w for w in report.warnings), report.warnings
    # the engine allocates nothing for it rather than refusing the step
    assert allocate(Resources(cpus=1, memory="a lot")).memory_gb is None


ENV_SCRIPT = """\
import json, os, sys
job = json.load(sys.stdin)
with open(job["outputs"]["note"], "w") as f:
    f.write(json.dumps([job["resources"], os.environ.get("STRINGENCY_CPUS")]) + "\\n")
"""


@pytest.fixture
def questions(
    tmp_path: Path, toy_data: Path, make_project: InitFn, method_repo: MethodRepo
) -> Project:
    """An open project with one question, as `test_open_exec` builds it."""
    _, delivery = delivered_process(tmp_path, toy_data, make_project)
    q = open_project(tmp_path, method_repo, delivery)
    accept_hold(q.store, q.confirm_hold()["hold_id"], reason="yes to the switch")
    cli(q, "ask", "what is the mean per group?")
    return q


def test_exec_takes_the_options_and_the_script_sees_the_allocation(
    questions: Project, tmp_path: Path
) -> None:
    script = tmp_path / "env.py"
    script.write_text(ENV_SCRIPT)
    r = cli(
        questions,
        "exec",
        str(script),
        "--out",
        "note=text",
        "--allow-local",
        "--cpus",
        "2",
        "--memory",
        "3GB",
        "--json",
    )
    assert r.exit_code == 0, r.output + str(r.stderr)
    out = json.loads(r.output)
    note = questions.store.one(
        "SELECT path FROM artifacts WHERE run_id=? AND step_id=? AND name='note'",
        (out["run_id"], out["step_id"]),
    )
    seen = json.loads(Path(note["path"]).read_text())
    assert seen == [{"cpus": 2, "memory_gb": 3, "timeout_s": 3600}, "2"]
    ev = _started(questions, out["run_id"], out["step_id"], "running")
    assert ev["resources_source"] == {
        "cpus": "override",
        "memory_gb": "override",
        "timeout_s": "policy",
    }
