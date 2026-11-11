"""A person's file in an open project (design 2.3 as amended 2026-11-11, PLAN L160; closes L48).

`inputs.yml` is never edited after `init`. `stringency inputs add` copies a person's file into
the project at `inputs/added/<name>/`, hashes the copy, and records an `input_added` run event
with the person's words. The project's inputs are then the declared ones and these, read from
every run's events (`include`), so `$inputs.<name>` binds the file by name in `call --in` and
`exec --in`, the digest check covers it, and an answer's qualifier names it with the words.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from stringency import hashing
from stringency.config import InputItem, InputsManifest
from stringency.exit_codes import ConfigError, RefusedError

if TYPE_CHECKING:
    from stringency.db.store import Store
    from stringency.project import Project

ADDED_DIR = Path("inputs") / "added"
EVENT = "input_added"
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def recorded(store: Store) -> dict[str, dict[str, Any]]:
    """Every `input_added` event of the project, by input name, in the order they were added.
    Reads: run_events."""
    out: dict[str, dict[str, Any]] = {}
    for r in store.all(
        "SELECT payload_json FROM run_events WHERE event = ? ORDER BY ts, rowid",
        (EVENT,),
    ):
        payload = json.loads(r["payload_json"] or "{}")
        if isinstance(payload, dict) and payload.get("name"):
            out[str(payload["name"])] = payload
    return out


def item_of(project_root: Path, payload: dict[str, Any]) -> InputItem:
    """The input item an `input_added` event stands for: the copy's absolute path, the type,
    the hash, and the person's words as `source`."""
    return InputItem(
        name=str(payload["name"]),
        path=str(project_root / str(payload["path"])),
        type=str(payload["type"]),
        blake3=str(payload["blake3"]),
        source=str(payload.get("source") or "") or None,
    )


def include(project: Project) -> None:
    """Add the project's recorded person-supplied inputs to `project.inputs` and set
    `project.added_inputs` (name -> event payload). Idempotent; a pipeline project has none.
    Reads: run_events."""
    if not project.open_ended or not project.db_path.exists():
        return
    events = recorded(project.store)
    project.added_inputs = events
    if not events:
        return
    declared = [i for i in project.inputs.items if i.name not in events]
    project.inputs = InputsManifest(
        items=[*declared, *(item_of(project.root, p) for p in events.values())]
    )


def tool_types(project: Project) -> list[str]:
    """The input types the method's tools take, sorted."""
    return sorted({spec.type for m in project.tools() for spec in m.manifest.inputs.values()})


def add(project: Project, name: str, path: Path, type_: str, source: str) -> dict[str, Any]:
    """`stringency inputs add`: copy `path` (a file or a directory) to `inputs/added/<name>/`,
    hash the copy, and append an `input_added` event to the open run, which is opened as `ask`
    opens it. Refused (exit 16) on a pipeline project; a name already an input, a type no tool
    takes, a missing path or empty words are refused (exit 15) before anything is copied.
    Reads: runs, run_events, the module index. Writes: the copy; run_events (`input_added`).
    Returns the event's payload."""
    from stringency.operator_id import operator_env
    from stringency.questions import open_for_questions

    if not project.open_ended:
        raise RefusedError(
            "inputs add brings a person's file into an open project; a declared pipeline's "
            "inputs change only with a new project"
        )
    if not NAME.match(name):
        raise ConfigError(
            f"input name {name!r}: letters, digits, `_` and `-`, starting with a letter"
        )
    words = source.strip()
    if not words:
        raise ConfigError("--source needs the person's words: what the file is and where from")
    include(project)
    if name in project.inputs.by_name():
        raise ConfigError(f"{name} is already an input of this project; choose another name")
    types = tool_types(project)
    if type_ not in types:
        raise ConfigError(
            f"no tool of this method takes an input of type {type_!r}; types: "
            + (", ".join(types) or "none")
        )
    src = Path(path).expanduser()
    if not src.exists():
        raise ConfigError(f"{src} does not exist")
    src = src.resolve()
    rel = ADDED_DIR / name / src.name
    dest = project.root / rel
    if dest.parent.exists():
        raise ConfigError(f"{dest.parent} already exists; nothing was added")
    rc = open_for_questions(project)
    dest.parent.mkdir(parents=True)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    payload: dict[str, Any] = {
        "name": name,
        "type": type_,
        "path": str(rel),
        "from": str(src),
        "blake3": hashing.hash_path(dest),
        "size": hashing.path_size(dest),
        "source": words,
        "operator": operator_env(),
    }
    project.store.run_event(rc.run_id, EVENT, payload)
    include(project)
    return {**payload, "run_id": rc.run_id, "ref": f"$inputs.{name}"}
