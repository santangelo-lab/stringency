"""`stringency status` (design 14.1)."""

from __future__ import annotations

from stringency.cli.common import handle_errors, not_implemented


@handle_errors
def status() -> None:
    not_implemented("status")
