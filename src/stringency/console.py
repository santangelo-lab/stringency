"""The console's readers (`spec/plans/console-and-fleet-plan.md` sections 3.5 to 3.9): project
discovery and the registry that keys projects by their trace id, and the lookups that find which
project owns a hold or a run. Everything here reads; nothing writes.

Reads: `stringency.yml` (the project id), `holds` and `runs` (ownership lookups) over read-only
connections. Writes nothing.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from stringency.board import SKIP_DIRS
from stringency.exit_codes import ConfigError

RESCAN_SECONDS = 30.0


def _candidates(d: Path) -> list[Path]:
    """Subdirectories the board would scan: not `superseded/`, `declarations/` or dot-dirs."""
    return sorted(
        c
        for c in d.iterdir()
        if c.is_dir() and c.name not in SKIP_DIRS and not c.name.startswith(".")
    )


def discover(projects: list[Path], projects_dirs: list[Path] | Path | None) -> list[Path]:
    """Project roots: the ones named, plus every child of each directory to depth two that holds
    a `stringency.yml`, skipping the directories the board skips (`superseded/`, `declarations/`,
    dot-dirs) at both levels. Ordered as given, then by path. A named root that is not a project
    is an error; a directory that does not exist contributes nothing."""
    roots: list[Path] = [p.resolve() for p in projects]
    dirs = [projects_dirs] if isinstance(projects_dirs, Path) else list(projects_dirs or [])
    for projects_dir in dirs:
        base = projects_dir.resolve()
        found: list[Path] = []
        for child in _candidates(base) if base.is_dir() else []:
            if (child / "stringency.yml").exists():
                found.append(child)
                continue
            for grand in _candidates(child):
                if (grand / "stringency.yml").exists():
                    found.append(grand)
        roots += [f for f in found if f not in roots]
    for r in roots:
        if not (r / "stringency.yml").exists():
            raise ConfigError(f"{r} is not a stringency project (no stringency.yml)")
    if not roots:
        raise ConfigError("review --serve needs --project <path> or --projects <dir>")
    return roots


def project_id_of(root: Path) -> str | None:
    """The `project_id` in `stringency.yml`, read leniently; None when the file is unreadable."""
    try:
        data = yaml.safe_load((root / "stringency.yml").read_text())
    except (OSError, yaml.YAMLError):
        return None
    if isinstance(data, dict) and isinstance(data.get("project_id"), str):
        return str(data["project_id"])
    return None


def _ro(root: Path) -> sqlite3.Connection | None:
    path = root / "prov" / "run.db"
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=2000")
    return conn


@dataclass
class Registry:
    """The projects a console serves, rescanned every `rescan_seconds` on demand so a project
    initialised during the day appears without a restart. Keyed by `project_id`; the positional
    index survives for the `/p/<i>/...` routes of engine 0.2.6, which redirect."""

    explicit: list[Path]
    dirs: list[Path]
    rescan_seconds: float = RESCAN_SECONDS
    roots: list[Path] = field(default_factory=list)
    by_id: dict[str, Path] = field(default_factory=dict)
    ids: dict[Path, str] = field(default_factory=dict)
    scanned_at: float = 0.0
    _owner: dict[tuple[str, str], str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def refresh(self, *, force: bool = False) -> None:
        with self._lock:
            if (
                not force
                and self.roots
                and time.monotonic() - self.scanned_at < self.rescan_seconds
            ):
                return
            roots = discover(self.explicit, self.dirs)
            by_id: dict[str, Path] = {}
            ids: dict[Path, str] = {}
            for r in roots:
                pid = project_id_of(r)
                if pid is not None and pid not in by_id:
                    by_id[pid] = r
                    ids[r] = pid
            self.roots, self.by_id, self.ids = roots, by_id, ids
            self.scanned_at = time.monotonic()

    def root_of(self, project_id: str) -> Path:
        self.refresh()
        root = self.by_id.get(project_id)
        if root is None:
            self.refresh(force=True)
            root = self.by_id.get(project_id)
        if root is None:
            raise ConfigError(f"no project {project_id}")
        return root

    def id_of(self, root: Path) -> str | None:
        self.refresh()
        return self.ids.get(root)

    def root_at(self, index: int) -> Path:
        """The 0.2.6 positional route."""
        self.refresh()
        if index < 0 or index >= len(self.roots):
            raise ConfigError(f"no project {index}")
        return self.roots[index]

    def owner_of(self, what: str, ident: str) -> tuple[str, Path]:
        """The project that holds hold or run `ident`: (`project_id`, root). Reads `holds` or
        `runs` of each project over a read-only connection; a hit is remembered, since ids never
        move between projects."""
        if what not in ("hold", "run"):
            raise ConfigError(f"no {what} route")
        table, column = ("holds", "hold_id") if what == "hold" else ("runs", "run_id")
        self.refresh()
        pid = self._owner.get((what, ident))
        if pid is not None and pid in self.by_id:
            return pid, self.by_id[pid]
        for root in self.roots:
            conn = _ro(root)
            if conn is None:
                continue
            try:
                found = conn.execute(
                    f"SELECT 1 FROM {table} WHERE {column} = ?",
                    (ident,),  # noqa: S608 - fixed names
                ).fetchone()
            except sqlite3.DatabaseError:
                continue
            finally:
                conn.close()
            if found is not None:
                owner = self.ids.get(root)
                if owner is None:
                    raise ConfigError(f"{root} has no project_id in stringency.yml")
                self._owner[(what, ident)] = owner
                return owner, root
        raise ConfigError(f"no {what} {ident} in {len(self.roots)} project(s)")
