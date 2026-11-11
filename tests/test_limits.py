"""The limits band, chosen apart from the profile (design 6.4, 2026-11-10; PLAN L171). The
owner's policy for the benchmark is strict-level limits with nobody reviewing as a run goes
along; the engine tied the band of `ranges` to the profile (`qc_ranges`), and the `strict`
profile itself cannot run unattended (it locks parameters, turns flags into blocks, refuses a
relayed verdict and open mode). A project now names its band at `init`, and only what reads a
range moves."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from stringency.deliver import deliver
from stringency.exit_codes import ConfigError
from stringency.policy import load_policy
from stringency.predicates.registry import registry
from stringency.project import Project
from stringency.runs import load_run
from tests.conftest import InitFn, MethodRepo, accept_hold
from tests.test_run import MOCK, cli


def _policy(method_repo: MethodRepo):  # type: ignore[no-untyped-def]
    return load_policy(method_repo.path / "policy.yml")


def test_a_policy_read_at_a_chosen_band_moves_its_ranges_and_nothing_else(
    method_repo: MethodRepo,
) -> None:
    base = _policy(method_repo)
    key = sorted(base.ranges)[0]
    assert base.bands() == ["standard", "strict", "wide"]
    assert base.band_for("standard") == "standard"
    assert base.range_for(key, "standard") == base.ranges[key]["standard"]
    strict = base.with_limits("strict")
    assert strict.band_for("standard") == strict.band_for("exploratory") == "strict"
    assert strict.range_for(key, "standard") == base.ranges[key]["strict"]
    # the profile keeps its own review rule, parameter rule and remap
    assert strict.profile("standard") == base.profile("standard")
    assert strict.profile("standard").relayed_review and strict.profile("standard").params == (
        "ranged"
    )
    # runs judged at different limits never share a policy digest; no choice, no change
    assert strict.digest(registry) != base.digest(registry)
    assert base.with_limits(None).digest(registry) == base.digest(registry)
    with pytest.raises(ConfigError, match="limits band 'tight' is not one the method's policy"):
        base.with_limits("tight")


def test_limits_is_not_a_key_of_the_policy_file(method_repo: MethodRepo) -> None:
    path = method_repo.path / "policy.yml"
    doc = yaml.safe_load(path.read_text())
    doc["limits"] = "strict"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ConfigError, match="`limits` is a project's choice"):
        load_policy(path)


def test_a_project_names_its_band_at_init_and_the_record_says_so(
    make_project: InitFn, tmp_path: Path
) -> None:
    p = make_project(pipeline="toy-engine", execution="engine", limits="strict")
    cfg = yaml.safe_load((p.root / "stringency.yml").read_text())
    assert (cfg["profile"], cfg["limits"]) == ("standard", "strict")
    key = sorted(p.policy.ranges)[0]
    assert p.policy.range_for(key, p.config.profile) == p.policy.ranges[key]["strict"]
    again = Project(p.root)  # read back from disk, the band is still the project's
    assert again.policy.band_for("standard") == "strict"
    echo = " ".join(p.echo_path().read_text().split())
    assert (
        "Limits: checks that read a range from the method's policy are judged at its `strict` "
        "band, chosen for this project; the `standard` profile's own band is `standard`." in echo
    )
    assert "limits band" in p.inheritance_report()
    accept_hold(p.store, p.confirm_hold()["hold_id"])
    r = cli(p, "run", "--json", env=MOCK)
    assert r.exit_code == 0, r.output
    run_id = json.loads(r.output)["run_id"]
    d = deliver(load_run(p, run_id))
    assert "| profile standard | limits strict (chosen for this project)" in d.coverage
    assert "under the standard profile at the policy's strict limits" in d.methods
    cov = json.loads((d.path / "coverage.json").read_text())
    assert (cov["limits"], cov["limits_chosen"]) == ("strict", True)
    digest = p.store.scalar("SELECT policy_digest FROM runs WHERE run_id=?", (run_id,))
    plain = make_project(pipeline="toy-engine", execution="engine")
    assert digest == p.policy.digest(registry) != plain.policy.digest(registry)
    assert "Limits:" not in plain.echo_path().read_text()
    assert yaml.safe_load((plain.root / "stringency.yml").read_text())["limits"] is None


def test_init_and_declare_check_refuse_a_band_the_policy_does_not_declare(
    make_project: InitFn, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    from typer.testing import CliRunner

    from stringency.cli.app import app

    with pytest.raises(ConfigError, match="limits band 'tight'"):
        make_project(pipeline="toy-engine", execution="engine", limits="tight")
    args = [
        "declare",
        str(declarations["design.yml"].parent),
        "--check",
        "--method",
        method_repo.spec,
        "--pipeline",
        "toy",
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
        "--limits",
    ]
    r = CliRunner().invoke(app, [*args, "tight"])
    assert r.exit_code == 15 and "limits band 'tight'" in (r.output + str(r.stderr))
    r = CliRunner().invoke(app, [*args, "strict"])
    assert r.exit_code == 0, r.output
    assert "judged at its `strict` band" in " ".join(r.output.split())


def test_the_site_names_a_band_for_every_project_and_the_flag_wins(
    monkeypatch: pytest.MonkeyPatch, method_repo: MethodRepo, declarations: dict[str, Path]
) -> None:
    """A benchmark's container says `limits: strict` once, in the install's config, so the
    band does not rest on the agent remembering a flag."""
    from typer.testing import CliRunner

    from stringency import siteconfig
    from stringency.cli import verb_declare
    from stringency.cli.app import app
    from stringency.project import check_declarations

    seen: list[str | None] = []

    def spy(req):  # type: ignore[no-untyped-def]
        seen.append(req.limits)
        return check_declarations(req)

    monkeypatch.setattr(verb_declare, "check_declarations", spy)
    args = [
        "declare",
        str(declarations["design.yml"].parent),
        "--check",
        "--method",
        method_repo.spec,
        "--pipeline",
        "toy",
        "--judgment-harness",
        "mock",
        "--executor",
        "local",
    ]
    assert CliRunner().invoke(app, args).exit_code == 0
    cfg = siteconfig.config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("limits: strict\n")
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 0 and "judged at its `strict` band" in " ".join(r.output.split())
    assert CliRunner().invoke(app, [*args, "--limits", "wide"]).exit_code == 0
    assert seen == [None, "strict", "wide"]
    cfg.write_text("limits: [strict]\n")
    r = CliRunner().invoke(app, args)
    assert r.exit_code == 15 and "limits must be the name of a band" in (r.output + str(r.stderr))
