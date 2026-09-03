"""`stringency fork` (design 14.1)."""

from __future__ import annotations

from stringency.cli.common import handle_errors, not_implemented


@handle_errors
def fork() -> None:
    not_implemented("fork")
