"""Cross-repository compatibility (backlog L28 to L31, engine 0.2.19): version specs, a
method's `requires`, the plugins recorded in provenance, image resolution, and `probe`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from stringency import __version__, git
from stringency.cli.app import app
from stringency.deliver import deliver
from stringency.executor.apptainer import resolve_image
from stringency.exit_codes import ConfigError
from stringency.lint import lint_path
from stringency.probe import probe
from stringency.project import InitRequest, init_project
from stringency.runs import captured_plugins, load_run, open_run
from stringency.versions import Requires, check_requires, compare, parse_version, satisfies
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_deliver import completed_project

runner = CliRunner()


def test_versions_compare_and_satisfy() -> None:
    assert parse_version("v0.6.0-rc13") == ((0, 6, 0), (0, 13))
    assert parse_version("0.2.19") == ((0, 2, 19), (1, 0))
    assert parse_version("0.1.0+optin3") == ((0, 1, 0), (1, 0))
    assert compare("0.2.19", "0.2.9") > 0 and compare("0.2", "0.2.0") == 0
    assert compare("0.6.0-rc13", "0.6.0") < 0 and compare("0.6.0rc2", "0.6.0-rc13") < 0
    assert satisfies("0.2.19", ">=0.2.15") and not satisfies("0.2.14", ">=0.2.15")
    assert satisfies("0.5.1", ">=0.5.0, <0.6") and not satisfies("0.6.0", ">=0.5.0, <0.6")
    assert satisfies("0.6.0-rc13", "==0.6.0-rc13") and satisfies("0.5.1", "!=0.5.0")
    with pytest.raises(ConfigError, match="operator"):
        satisfies("0.2.19", "0.2.19")
    with pytest.raises(ConfigError, match="not a version"):
        parse_version("latest")
    req = Requires(engine=">=0.2.19", plugins={"stringency-toy": ">=0.1.2", "other": ">=1"})
    assert check_requires(req, "0.2.19", {"stringency-toy": "0.1.2"}) == [
        "plugin other >=1 required; not installed"
    ]
    assert check_requires(req, "0.2.18", {"stringency-toy": "0.1.1", "other": "1.0"}) == [
        "engine >=0.2.19 required; installed 0.2.18",
        "plugin stringency-toy >=0.1.2 required; installed 0.1.1",
    ]


def _set_requires(method_dir: Path, requires: dict) -> None:  # type: ignore[type-arg]
    pol = method_dir / "policy.yml"
    data = yaml.safe_load(pol.read_text())
    data["requires"] = requires
    pol.write_text(yaml.safe_dump(data, sort_keys=False))


def test_requires_is_checked_by_lint_init_and_run_open(
    make_project: InitFn, method_repo: MethodRepo, tmp_path: Path, declarations: dict[str, Path]
) -> None:
    # the toy template satisfies its own requires: lint is clean of requires lines
    report = lint_path(method_repo.path)
    assert not [e for e in report.errors if "requires" in e]
    assert not [w for w in report.warnings if "requires" in w]
    # a method that needs a newer engine: lint names both versions; init and declare refuse
    _set_requires(method_repo.path, {"engine": ">=99.0", "plugins": {"stringency-toy": ">=0.1.2"}})
    report = lint_path(method_repo.path)
    assert any(
        f"requires: engine >=99.0 required; installed {__version__}" in e for e in report.errors
    )
    git.commit_all(method_repo.path, "needs a future engine")
    git.tag(method_repo.path, "v0.1.1")
    req = InitRequest(
        path=tmp_path / "future",
        method=f"{method_repo.path}@v0.1.1",
        pipeline="toy-engine",
        objective=declarations["objective.yml"],
        design=declarations["design.yml"],
        inputs=declarations["inputs.yml"],
        owner="tester",
        reviewer="tester",
        judgment_harness="mock",
        execution="engine",
        executor="local",
    )
    with pytest.raises(
        ConfigError, match=f"requires: engine >=99.0 required; installed {__version__}"
    ):
        init_project(req)
    assert not (tmp_path / "future").exists()
    # a project initialised when the method was satisfied, run under an install that no longer
    # satisfies it (the method's policy edited in place stands in for a changed install)
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    _set_requires(p.method_root, {"plugins": {"stringency-toy": "<0.1"}})
    from stringency.project import Project

    p2 = Project.load(p.root)
    with pytest.raises(ConfigError, match="plugin stringency-toy <0.1 required; installed 0.1.2"):
        open_run(p2, allow_dirty="test")
    # a missing requires is a lint warning, not an error
    data = yaml.safe_load((p.method_root / "policy.yml").read_text())
    del data["requires"]
    (p.method_root / "policy.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    report = lint_path(p.method_root)
    assert report.ok and any("no `requires`" in w for w in report.warnings)


def test_plugins_are_recorded_at_init_at_run_open_and_in_the_delivery(make_project: InitFn) -> None:
    p, run_id = completed_project(make_project)
    assert p.config.plugins.get("stringency-toy") == "0.1.2"
    assert (
        yaml.safe_load((p.root / "stringency.yml").read_text())["plugins"]["stringency-toy"]
        == "0.1.2"
    )
    assert captured_plugins(p.store, run_id)["stringency-toy"] == "0.1.2"
    d = deliver(load_run(p, run_id))
    index = json.loads((d.path / "index.json").read_text())
    assert index["plugins"]["stringency-toy"] == "0.1.2"
    coverage = (d.path / "coverage.md").read_text()
    assert f"stringency {__version__} with stringency-toy 0.1.2 | method" in coverage
    assert "(plugin stringency-toy 0.1.2)" in (d.path / "methods.md").read_text()


def test_a_changed_plugin_version_is_noted_at_run_open(make_project: InitFn) -> None:
    p = make_project(pipeline="toy-engine", execution="engine")
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    cfg = p.root / "stringency.yml"
    data = yaml.safe_load(cfg.read_text())
    data["plugins"]["stringency-toy"] = "0.0.9"
    cfg.write_text(yaml.safe_dump(data, sort_keys=False))
    from stringency.project import Project

    rc = open_run(Project.load(p.root))
    assert rc.plugin_changes == [{"plugin": "stringency-toy", "at_init": "0.0.9", "now": "0.1.2"}]
    ev = p.store.one(
        "SELECT payload_json FROM run_events WHERE run_id=? AND event='captures'", (rc.run_id,)
    )
    assert json.loads(ev["payload_json"])["plugin_changes"] == rc.plugin_changes


def test_resolve_image_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    envs_root = tmp_path / "method" / "envs"
    envs_root.mkdir(parents=True)
    absolute = tmp_path / "abs.sif"
    assert resolve_image(str(absolute), envs_root) == absolute  # as given, even when absent
    monkeypatch.delenv("STRINGENCY_IMAGES", raising=False)
    # nothing exists: the first candidate names where it was looked for (the method checkout)
    assert resolve_image("x.sif", envs_root) == envs_root.parent / "x.sif"
    (envs_root / "x.sif").write_text("")
    assert resolve_image("x.sif", envs_root) == envs_root / "x.sif"
    site = tmp_path / "xdg" / "stringency"
    site.mkdir(parents=True)
    (site / "config.yml").write_text(f"images_root: {tmp_path / 'site-images'}\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    (tmp_path / "site-images").mkdir()
    (tmp_path / "site-images" / "x.sif").write_text("")
    assert resolve_image("x.sif", envs_root) == tmp_path / "site-images" / "x.sif"
    monkeypatch.setenv("STRINGENCY_IMAGES", str(tmp_path / "env-images"))
    (tmp_path / "env-images").mkdir()
    (tmp_path / "env-images" / "x.sif").write_text("")
    assert resolve_image("x.sif", envs_root) == tmp_path / "env-images" / "x.sif"
    assert resolve_image("missing.sif", envs_root) == tmp_path / "env-images" / "missing.sif"


def test_probe_reports_the_install_and_checks_a_method(
    method_repo: MethodRepo, tmp_path: Path
) -> None:
    payload = probe(None)
    assert (
        payload["engine"]["version"] == __version__
        and payload["plugins"]["stringency-toy"] == "0.1.2"
    )
    names = {c["name"]: c for c in payload["checks"]}
    assert names["engine"]["ok"] and names["plugins"]["ok"]
    assert names["container"]["ok"] is None  # no method, no image needed: reported, not judged
    assert payload["ok"]
    payload = probe(str(method_repo.path))
    names = {c["name"]: c for c in payload["checks"]}
    assert names["requires"]["ok"] and "satisfy" in names["requires"]["detail"]
    assert names["lock toy-py"]["ok"] and payload["method"]["envs"]["toy-py"]["image"] is None
    assert payload["ok"]
    r = runner.invoke(app, ["probe", "--method", str(method_repo.path), "--json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["ok"] is True
    # a manifest naming an image that is not here: the check names where it looked
    mf = method_repo.path / "envs" / "manifest.yml"
    data = yaml.safe_load(mf.read_text())
    data["environments"]["toy-py"]["image"] = "toy-py-0.1.0.sif"
    mf.write_text(yaml.safe_dump(data))
    r = runner.invoke(app, ["probe", "--method", str(method_repo.path)])
    assert r.exit_code == 1, r.output
    assert "FAIL image toy-py:" in r.output and "toy-py-0.1.0.sif not found" in r.output
    assert "not ready: " in r.output


def test_probe_skills_check_reads_the_version_and_accepts_an_older_skill(tmp_path: Path) -> None:
    from stringency.probe import _skill_engine, skills_check

    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "# operator\n\n**Which text of this skill to follow.** This text is for engine 0.2.19. "
        "The engine\ninstalls its own copy.\n"
    )
    assert (
        _skill_engine(skill) == "0.2.19"
    )  # the whole version, not the digits before the first dot
    assert skills_check(
        skill, "0.2.19", "0.2.20"
    ).ok  # a skill for an older engine drives a newer one
    assert skills_check(skill, "0.2.20", "0.2.20").ok
    c = skills_check(skill, "0.3.0", "0.2.20")
    assert not c.ok and "newer than this engine" in c.detail
    assert not skills_check(skill, None, "0.2.20").ok
