"""The dispatch adapter (design 10.2): request and response files, nonces, `reported` verbatim.

    runs/<run>/<step>/dispatch/
      manifest.json  req_1.json ...  resp_1.json ...

The engine writes requests and stops (exit 20). The operator harness has one fresh-context
subagent answer each request file. On the next `run` the engine collects, checks nonces,
validates, and proceeds as for a direct invocation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stringency import __version__
from stringency.harness.base import Family, Invocation, Request, Sampling
from stringency.prompting import DISPATCH_SUFFIX


def request_path(dispatch_dir: Path, replicate: int) -> Path:
    return dispatch_dir / f"req_{replicate}.json"


def response_path(dispatch_dir: Path, replicate: int) -> Path:
    return dispatch_dir / f"resp_{replicate}.json"


def write_requests(
    requests: list[Request], dispatch_dir: Path, *, step_id: str, action_id: str, schema_name: str
) -> None:
    """Write manifest.json and one req_N.json per replicate. Never rewrites an existing set."""
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    manifest = dispatch_dir / "manifest.json"
    if manifest.exists():
        return
    for r in requests:
        request_path(dispatch_dir, r.replicate).write_text(
            json.dumps(
                {
                    "replicate": r.replicate,
                    "nonce": r.nonce,
                    "prompt": r.prompt + DISPATCH_SUFFIX.format(nonce=r.nonce),
                    "schema": r.schema,
                    "response_file": str(response_path(dispatch_dir, r.replicate)),
                },
                indent=2,
            )
        )
    manifest.write_text(
        json.dumps(
            {
                "step_id": step_id,
                "action_id": action_id,
                "replicates": len(requests),
                "schema": schema_name,
                "nonce_prefix": action_id,
                "requests": [str(request_path(dispatch_dir, r.replicate)) for r in requests],
                "responses": [str(response_path(dispatch_dir, r.replicate)) for r in requests],
            },
            indent=2,
        )
    )


def read_response(req: Request, dispatch_dir: Path) -> Invocation:
    """Parse one response file. Missing, unparseable, or nonce-mismatched responses are invalid."""
    rp = response_path(dispatch_dir, req.replicate)
    base: dict[str, Any] = {
        "model_requested": None,
        "harness_kind": "subagent",
        "harness_version": __version__,
        "via": "subagent",
        "isolation": "as_reported",
        "request_path": str(request_path(dispatch_dir, req.replicate)),
        "response_path": str(rp),
    }
    if not rp.exists():
        return Invocation(
            None,
            "",
            False,
            model_resolved="unknown",
            nonce_ok=None,
            error="response file missing",
            **base,
        )
    text = rp.read_text()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return Invocation(
            None,
            text,
            False,
            model_resolved="unknown",
            nonce_ok=None,
            error=f"unparseable response: {e}",
            **base,
        )
    if not isinstance(data, dict):
        return Invocation(
            None,
            text,
            False,
            model_resolved="unknown",
            nonce_ok=None,
            error="response is not an object",
            **base,
        )
    reported = data.get("reported") if isinstance(data.get("reported"), dict) else None
    model = str(reported.get("model")) if reported and reported.get("model") else "unknown"
    nonce_ok = data.get("nonce") == req.nonce
    structured = data.get("structured") if isinstance(data.get("structured"), dict) else None
    inv = Invocation(
        structured if nonce_ok else None,
        text,
        False,  # schema validity is decided by the caller
        model_resolved=model,
        nonce_ok=nonce_ok,
        reported=reported,
        error=None if nonce_ok else "nonce mismatch",
        **base,
    )
    return inv


class SubagentHarness:
    kind = "subagent"
    version = __version__
    family: Family = "dispatch"

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        raise NotImplementedError(
            "the subagent harness is a dispatch adapter; use dispatch/collect"
        )

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        # step_id/action_id come from the caller through the directory layout; the manifest is
        # written by judgment.py via write_requests so it can name them.
        raise NotImplementedError("use write_requests")

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        return [read_response(r, dispatch_dir) for r in requests]
