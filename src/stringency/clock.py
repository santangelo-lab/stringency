"""Timestamps. Every trace row carries UTC ISO 8601 with a Z suffix and second precision."""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
