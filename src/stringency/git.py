"""git facts the trace records: SHA, dirty flag, blob hash for a path at HEAD, clone at tag."""

from __future__ import annotations

import subprocess
from pathlib import Path

from stringency.exit_codes import ConfigError


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
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

    `url` may be a `git+https://...` URL, a plain URL, or a local path.
    """
    if url.startswith("git+"):
        url = url[4:]
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--no-checkout", url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(dest), "checkout", "--quiet", tag],
            check=True,
            capture_output=True,
            text=True,
        )
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
