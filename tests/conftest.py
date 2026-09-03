"""Shared fixtures: a temporary method repo (git init + commit + tag) copied from the toy
plugin's method directory, and a temporary project bound to it via `init`."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from stringency import git, hashing
from stringency.db.store import Store
from stringency.ids import new_id
from stringency.plugins import load_plugins
from stringency.project import InitRequest, Project, init_project
from stringency_toy import METHOD_TEMPLATE

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class MethodRepo:
    path: Path
    tag: str
    sha: str

    @property
    def spec(self) -> str:
        return f"{self.path}@{self.tag}"

    def commit(self, message: str = "edit") -> str:
        return git.commit_all(self.path, message)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden", action="store_true", default=False, help="rewrite golden files"
    )


@pytest.fixture(autouse=True)
def _plugins() -> None:
    load_plugins(refresh=True)


@pytest.fixture
def method_repo(tmp_path: Path) -> MethodRepo:
    dest = tmp_path / "method-src"
    shutil.copytree(METHOD_TEMPLATE, dest)
    git.init_repo(dest)
    sha = git.commit_all(dest, "toy method v0.1.0")
    git.tag(dest, "v0.1.0")
    return MethodRepo(dest, "v0.1.0", sha)


@pytest.fixture
def toy_data(tmp_path: Path) -> Path:
    src = METHOD_TEMPLATE / "controls" / "fixtures" / "groups.csv"
    dst = tmp_path / "data" / "groups.csv"
    dst.parent.mkdir(parents=True)
    shutil.copyfile(src, dst)
    return dst


def write_declarations(
    dirpath: Path,
    data_path: Path,
    *,
    design: dict | None = None,
    objective: dict | None = None,
    inputs: dict | None = None,
) -> dict[str, Path]:
    dirpath.mkdir(parents=True, exist_ok=True)
    d = design or {
        "design": 1,
        "units": {"observation": "row", "sample": "unit"},
        "factors": {"group": {"column": "group", "levels": ["A", "B", "C"]}},
        "batch": [],
        "replication_unit": "unit",
        "holdout": [],
    }
    o = objective or {
        "objective": 1,
        "id": "toy_ab",
        "question": "compare_groups",
        "contrasts": [["group", "A", "B"]],
        "replication_unit": "unit",
        "min_n_per_group": 2,
        "deliverables": ["comparison_table", "group_labels"],
        "domain": {},
    }
    i = inputs or {
        "inputs": 1,
        "items": [
            {
                "name": "groups",
                "path": str(data_path),
                "type": "frame",
                "blake3": hashing.hash_file(data_path),
                "source": "toy fixture",
            }
        ],
    }
    out: dict[str, Path] = {}
    for name, obj in (("design.yml", d), ("objective.yml", o), ("inputs.yml", i)):
        p = dirpath / name
        p.write_text(yaml.safe_dump(obj, sort_keys=False))
        out[name] = p
    return out


@pytest.fixture
def declarations(tmp_path: Path, toy_data: Path) -> dict[str, Path]:
    return write_declarations(tmp_path / "decl", toy_data)


InitFn = Callable[..., Project]


@pytest.fixture
def make_project(tmp_path: Path, method_repo: MethodRepo, declarations: dict[str, Path]) -> InitFn:
    counter = {"n": 0}

    def _make(**overrides: object) -> Project:
        counter["n"] += 1
        req = InitRequest(
            path=tmp_path / f"proj{counter['n']}",
            method=method_repo.spec,
            pipeline="toy",
            objective=declarations["objective.yml"],
            design=declarations["design.yml"],
            inputs=declarations["inputs.yml"],
            owner="tester",
            reviewer="tester",
            judgment_harness="mock",
            execution="operator",
            executor="local",
        )
        for k, v in overrides.items():
            setattr(req, k, v)
        return init_project(req)

    return _make


@pytest.fixture
def project(make_project: InitFn) -> Project:
    return make_project()


def accept_hold(store: Store, hold_id: str, reviewer: str = "tester", reason: str = "ok") -> str:
    """Pre-seed an accept review through the store API (used before M8's `review` exists)."""
    rid = new_id()
    store.insert(
        "reviews",
        {
            "review_id": rid,
            "hold_id": hold_id,
            "reviewer": reviewer,
            "host": "test",
            "via": "tty",
            "ts": "2026-01-01T00:00:00Z",
            "verdict": "accept",
            "reason": reason,
        },
    )
    store.resolve_hold(hold_id, rid, "tty")
    return rid


@pytest.fixture
def confirmed_project(project: Project) -> Project:
    h = project.confirm_hold()
    assert h is not None
    accept_hold(project.store, h["hold_id"])
    return project
