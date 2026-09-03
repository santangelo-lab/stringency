"""Plugin loading and the Plugin protocol (design 15).

A plugin has a predicate half (pure Python, lives in the engine environment) and a tool half
(scripts the executor runs inside module environments). The engine never imports the tool
half; it invokes tools by name through the executor.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Any

from stringency.exit_codes import ConfigError

if TYPE_CHECKING:
    from stringency.actions import Action
    from stringency.config import Design, InputsManifest, Objective

ENTRY_POINT_GROUP = "stringency.plugins"


@dataclass(frozen=True)
class Operation:
    name: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class ObjectType:
    name: str
    extractor: str  # tool name
    extractor_id: str  # e.g. "toy.frame@1", recorded on every snapshot


@dataclass(frozen=True)
class Tool:
    name: str
    script: Path
    env: str | None = None  # None: run in the calling module's env


@dataclass(frozen=True)
class Plugin:
    name: str
    version: str
    modes: tuple[str, ...]
    predicates_module: str  # importing it registers the predicates
    operations: Mapping[str, Operation]
    object_types: Mapping[str, ObjectType]
    design_schema: dict[str, Any]
    objective_questions: tuple[str, ...]
    vocabularies: Mapping[str, tuple[str, ...]]  # "name@version" -> labels
    tools: Mapping[str, Tool]
    describe: Callable[[Action], str]
    echo: Callable[[Design, Objective, InputsManifest, Mapping[str, Any]], str]

    def predicates(self) -> list[str]:
        """Predicate ids registered by this plugin (after import)."""
        from stringency.predicates.registry import registry

        return [s.id for s in registry.all() if s.source == self.name]

    def vocabulary(self, ref: str) -> tuple[str, ...] | None:
        return self.vocabularies.get(ref)


_cache: dict[str, Plugin] | None = None


def load_plugins(*, refresh: bool = False) -> dict[str, Plugin]:
    """Every plugin on the `stringency.plugins` entry point group, by plugin name.
    Importing a plugin's `predicates_module` registers its predicates."""
    global _cache
    if _cache is not None and not refresh:
        return _cache
    import importlib

    found: dict[str, Plugin] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        obj = ep.load()
        if not isinstance(obj, Plugin):
            raise ConfigError(f"entry point {ep.name} did not yield a Plugin")
        importlib.import_module(obj.predicates_module)
        found[obj.name] = obj
    _cache = found
    return found


def require_plugin(name: str) -> Plugin:
    plugins = load_plugins()
    if name not in plugins:
        raise ConfigError(
            f"pipeline domain {name} is not a loaded plugin; loaded: {sorted(plugins) or 'none'}"
        )
    return plugins[name]
