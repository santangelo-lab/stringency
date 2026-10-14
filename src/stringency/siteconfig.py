"""The per-user site configuration, `~/.config/stringency/config.yml` (`$XDG_CONFIG_HOME`
honoured; beside `notify.yml`): settings that belong to a machine and a user rather than to a
project. Today one key, `images_root`, the directory container images are resolved in when a
method's environment manifest names an image by file name (design 10.3, backlog L31). Reads only."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from stringency.exit_codes import ConfigError


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "stringency" / "config.yml"


def load(path: Path | None = None) -> dict[str, Any]:
    """The file as a mapping, or {} when there is none."""
    p = path or config_path()
    if not p.is_file():
        return {}
    try:
        doc = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{p}: not valid YAML: {e}") from None
    if not isinstance(doc, dict):
        raise ConfigError(f"{p}: expected a mapping")
    return doc


def images_root() -> Path | None:
    root = load().get("images_root")
    return Path(str(root)).expanduser() if root else None
