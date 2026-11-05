"""`git.py`: a checkout whose git directory sits beside the working tree (L151)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from stringency import git
from stringency.exit_codes import ConfigError
from tests.conftest import MethodRepo


def test_clone_at_keeps_the_git_directory_beside_the_working_tree(
    method_repo: MethodRepo, tmp_path: Path
) -> None:
    dest = tmp_path / "proj" / "method"
    sha = git.clone_at(str(method_repo.path), method_repo.tag, dest)
    assert sha == method_repo.sha
    assert (dest / "policy.yml").exists()
    assert not (dest / ".git").exists()
    assert (tmp_path / "proj" / "method.git" / "HEAD").exists()
    assert git.head_sha(dest) == method_repo.sha
    assert git.remote_url(dest) == str(method_repo.path)
    assert git.tag_sha(dest, method_repo.tag) == method_repo.sha
    assert git.blob_hash(dest, "policy.yml") and git.blob_hash(dest, "no-such-file") is None
    # the tree is clean; a change or a new file makes it dirty, as before
    assert not git.is_dirty(dest)
    (dest / "policy.yml").write_text("# changed\n")
    assert git.is_dirty(dest)
    subprocess.run(
        ["git", "--git-dir", str(tmp_path / "proj" / "method.git"), "--work-tree", str(dest)]
        + ["checkout", "--quiet", "--", "policy.yml"],
        check=True,
    )
    assert not git.is_dirty(dest)
    (dest / "extra.txt").write_text("x")
    assert git.is_dirty(dest)


def test_clone_at_takes_a_branch_a_tag_or_a_sha_and_refuses_an_existing_target(
    method_repo: MethodRepo, tmp_path: Path
) -> None:
    for i, ref in enumerate(("main", method_repo.tag, method_repo.sha)):
        dest = tmp_path / f"m{i}" / "method"
        assert git.clone_at(str(method_repo.path), ref, dest) == method_repo.sha
    assert git.head_sha(tmp_path / "m0" / "method") == method_repo.sha
    with pytest.raises(ConfigError, match="already exists"):
        git.clone_at(str(method_repo.path), "main", tmp_path / "m0" / "method")
    with pytest.raises(ConfigError, match="could not clone"):
        git.clone_at(str(method_repo.path), "no-such-ref", tmp_path / "m9" / "method")
    assert not (tmp_path / "m9" / "method" / ".git").exists()


def test_a_source_repository_with_its_own_git_directory_still_reads(
    method_repo: MethodRepo,
) -> None:
    assert git.head_sha(method_repo.path) == method_repo.sha
    assert not git.is_dirty(method_repo.path)


def test_clone_at_takes_a_tag_from_a_shallow_source(
    method_repo: MethodRepo, tmp_path: Path
) -> None:
    # the beta's setup keeps each method as `git clone --depth 1 --branch <tag>`; `init --method
    # <that checkout>@<tag>` then clones from a shallow source, which refuses a full fetch of
    # its tags (the owner's Mac, 2026-11-04)
    (method_repo.path / "CHANGELOG.md").write_text("# 0.1.1\n")
    sha2 = method_repo.commit("v0.1.1")
    git.tag(method_repo.path, "v0.1.1")
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", "--branch", "v0.1.1"]
        + [f"file://{method_repo.path}", str(shallow)],
        check=True,
        capture_output=True,
    )
    assert (shallow / ".git" / "shallow").exists()
    dest = tmp_path / "proj" / "method"
    assert git.clone_at(str(shallow), "v0.1.1", dest) == sha2
    assert git.head_sha(dest) == sha2 and (dest / "CHANGELOG.md").exists()
    assert not (dest / ".git").exists() and (tmp_path / "proj" / "method.git").is_dir()
    assert git.tag_sha(dest, "v0.1.1") == sha2 and not git.is_dirty(dest)
    with pytest.raises(ConfigError, match="could not clone"):
        git.clone_at(str(shallow), "v0.1.0", tmp_path / "p2" / "method")  # not in the source
