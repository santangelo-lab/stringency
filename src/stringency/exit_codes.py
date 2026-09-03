"""CLI exit codes (design 14.2). Frozen."""

from enum import IntEnum


class Exit(IntEnum):
    OK = 0
    INTERNAL = 1
    HELD = 10
    BLOCKED = 11
    REJECTED = 12
    FAILED = 13
    DIRTY = 14
    CONFIG = 15
    REFUSED = 16
    DISPATCHING = 20
    AWAITING_EXECUTION = 21


class StringencyError(Exception):
    """An error with a CLI exit code. The message is printed as-is; nothing is added."""

    code: Exit = Exit.INTERNAL

    def __init__(self, message: str, code: Exit | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ConfigError(StringencyError):
    code = Exit.CONFIG


class RefusedError(StringencyError):
    code = Exit.REFUSED


class HeldError(StringencyError):
    code = Exit.HELD


class BlockedError(StringencyError):
    code = Exit.BLOCKED


class RejectedError(StringencyError):
    code = Exit.REJECTED


class FailedError(StringencyError):
    code = Exit.FAILED


class DirtyTreeError(StringencyError):
    code = Exit.DIRTY
