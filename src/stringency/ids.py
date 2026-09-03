"""ULIDs for every identifier the engine mints."""

from __future__ import annotations

from ulid import ULID


def new_id() -> str:
    return str(ULID())
