"""Shared CLI helpers: exit-code handling and JSON output."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import typer

from stringency.exit_codes import Exit, StringencyError

DETACH_HELP = (
    "start the verb in a child that outlives this command and print {job_id, pid, log} at "
    "once; `stringency wait --job <id>` prints what it printed, with its exit code"
)
OUT_HELP = (
    "write the JSON payload to this file and print only its path and a one-line summary "
    "(for a connection that cuts long output)"
)


def emit(
    payload: dict[str, Any],
    as_json: bool,
    human: str | None = None,
    *,
    out: Path | None = None,
    summary: str | None = None,
) -> None:
    """Print `payload` as JSON when --json was given, else `human` (or a plain rendering).
    With `out` (L134 f) the JSON payload is written to that file whatever `as_json` says, and
    what is printed is the file's path, its size and a one-line summary (`summary`, else the
    first line of `human`), as JSON under `--json`."""
    if out is not None:
        text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
        target = Path(out)
        target.write_text(text)
        first = next((ln for ln in (human or "").splitlines() if ln.strip()), "")
        line = summary or first or str(payload.get("kind") or payload.get("schema") or "")
        small = {
            "schema": "stringency.out/1",
            "out": str(target.resolve()),
            "bytes": len(text.encode("utf-8")),
            "payload_schema": payload.get("schema"),
            "summary": line,
        }
        if as_json:
            sys.stdout.write(json.dumps(small, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(f"wrote {small['out']} ({small['bytes']} bytes): {line}\n")
        return
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


def detach_now(as_json: bool) -> None:
    """`--detach` (L134 c): start this command line again in a detached child and print the
    job's `{job_id, pid, log}`. Writes `prov/jobs/<job_id>/` (see `stringency.jobs`)."""
    from stringency.jobs import detach, detached_text

    p = detach()
    emit(p, as_json, detached_text(p))
