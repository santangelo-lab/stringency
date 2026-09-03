"""Shared CLI helpers: exit-code handling and JSON output."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer

from stringency.exit_codes import Exit, StringencyError


def emit(payload: dict[str, Any], as_json: bool, human: str | None = None) -> None:
    """Print `payload` as JSON when --json was given, else `human` (or a plain rendering)."""
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    elif human is not None:
        sys.stdout.write(human.rstrip("\n") + "\n")
    else:
        for k, v in payload.items():
            sys.stdout.write(f"{k}: {v}\n")


def handle_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Translate StringencyError into its exit code; anything else exits 1 with the message."""

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except StringencyError as e:
            sys.stderr.write(f"{e}\n")
            raise typer.Exit(code=int(e.code)) from None
        except typer.Exit:
            raise
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"internal error: {type(e).__name__}: {e}\n")
            raise typer.Exit(code=int(Exit.INTERNAL)) from None

    return wrapper


def not_implemented(verb: str) -> None:
    raise StringencyError(f"{verb}: not implemented", Exit.REFUSED)
