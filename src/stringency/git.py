"""git facts the trace records: SHA, dirty flag, blob hash for a path at HEAD, clone at tag."""

from __future__ import annotations

import subprocess
from pathlib import Path

from stringency.exit_codes import ConfigError


def git_dir_beside(worktree: Path) -> Path:
    """Where `clone_at` keeps a checkout's git directory: `<name>.git` beside `<name>/`, so the
    working tree holds no path named `.git` (the Claude Science sandbox on a Mac refuses to
    create one, L151)."""
    return worktree.with_name(worktree.name + ".git")


def _locate(repo: Path) -> list[str]:
    """How git is pointed at `repo`: a checkout with its own `.git` (a method source repository,
    a test fixture) by `-C`; a checkout `clone_at` made by its git directory beside it."""
    beside = git_dir_beside(repo)
    if not (repo / ".git").exists() and beside.is_dir():
        return ["--git-dir", str(beside), "--work-tree", str(repo)]
    return ["-C", str(repo)]


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *_locate(repo), *args], check=True, capture_output=True, text=True
        )
    except FileNotFoundError:
        raise ConfigError("git is not installed") from None
    except subprocess.CalledProcessError as e:
        raise ConfigError(f"git {' '.join(args)} failed in {repo}: {e.stderr.strip()}") from None
    return out.stdout.strip()


def head_sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def is_dirty(repo: Path) -> bool:
    """Uncommitted changes to tracked files, or untracked files not ignored."""
    return bool(_git(repo, "status", "--porcelain", "--untracked-files=all"))


def blob_hash(repo: Path, relpath: str) -> str | None:
    """git blob hash of `relpath` at HEAD, or None if the path is not tracked."""
    try:
        out = _git(repo, "rev-parse", f"HEAD:{relpath}")
    except ConfigError:
        return None
    return out or None


def tag_sha(repo: Path, tag: str) -> str:
    return _git(repo, "rev-list", "-n", "1", tag)


def remote_url(repo: Path) -> str | None:
    try:
        return _git(repo, "remote", "get-url", "origin") or None
    except ConfigError:
        return None


def clone_at(url: str, tag: str, dest: Path) -> str:
    """Clone `url` into `dest` and check out `tag`. Returns the checked-out SHA.

    `url` may be a `git+https://...` URL, a plain URL, or a local path. The git directory is
    `git_dir_beside(dest)`, not `dest/.git`: the working tree is the method's files alone, and
    every later git fact (`head_sha`, `is_dirty`, `blob_hash`) reads through `_locate`.
    """
    if url.startswith("git+"):
        url = url[4:]
    gitdir = git_dir_beside(dest)
    if gitdir.exists() or dest.exists():
        raise ConfigError(f"could not clone {url} at {tag}: {dest} or {gitdir} already exists")
    dest.mkdir(parents=True)

    def run(*args: str) -> None:
        subprocess.run(
            ["git", "--git-dir", str(gitdir), "--work-tree", str(dest), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        run("init", "--quiet")
        run("remote", "add", "origin", url)
        run("fetch", "--quiet", "--tags", "origin")
        run("checkout", "--quiet", tag)
    except subprocess.CalledProcessError as e:
        raise ConfigError(f"could not clone {url} at {tag}: {e.stderr.strip()}") from None
    return head_sha(dest)


def init_repo(path: Path) -> None:
    """git init with a main branch. Used by tests and the method-repo template."""
    _git(path, "init", "--quiet", "--initial-branch=main")


def commit_all(path: Path, message: str) -> str:
    _git(path, "add", "-A")
    _git(
        path,
        "-c",
        "user.name=stringency",
        "-c",
        "user.email=stringency@localhost",
        "commit",
        "--quiet",
        "--allow-empty",
        "-m",
        message,
    )
    return head_sha(path)


def tag(path: Path, name: str) -> None:
    _git(path, "tag", name)
