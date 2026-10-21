"""Who is operating a run: the operator harness, its version and its session reference, as
recorded on runs, reviews and declarations. Reads the environment; writes nothing."""

from __future__ import annotations

import os
import re
from pathlib import Path

VERSION_LIKE = re.compile(r"\d+(?:\.\d+)+")


def operator_env() -> dict[str, str | None]:
    """Who is operating: `STRINGENCY_OPERATOR`, `STRINGENCY_OPERATOR_VERSION` and
    `STRINGENCY_SESSION_REF` when set. Inside Claude Code, which exports `CLAUDECODE`,
    `CLAUDE_CODE_SESSION_ID` and `CLAUDE_CODE_EXECPATH` (ending in its version), each unset or
    `unknown` value is taken from there (lung, 2026-10-08, recorded version `unknown` and an
    invented session name); inside Codex CLI likewise from `CODEX_VERSION` and
    `CODEX_THREAD_ID` (backlog L34, 2026-10-21)."""
    env = os.environ

    def given(name: str) -> str | None:
        v = (env.get(name) or "").strip()
        return v if v and v.lower() != "unknown" else None

    harness, version, session = (
        given("STRINGENCY_OPERATOR"),
        given("STRINGENCY_OPERATOR_VERSION"),
        given("STRINGENCY_SESSION_REF"),
    )
    if env.get("CLAUDECODE"):
        harness = harness or "claude-code"
        if harness == "claude-code":
            if version is None:
                m = VERSION_LIKE.fullmatch(Path(env.get("CLAUDE_CODE_EXECPATH", "")).name)
                version = m.group(0) if m else None
            if session is None and env.get("CLAUDE_CODE_SESSION_ID"):
                session = f"claude-code:{env['CLAUDE_CODE_SESSION_ID']}"
    elif env.get("CODEX_VERSION") or env.get("CODEX_THREAD_ID"):
        # Codex CLI exports CODEX_VERSION, CODEX_THREAD_ID and CODEX_SESSION_ID in a session
        # (surveyed 2026-10-21, codex-cli 0.163.0; integrations/codex/README.md)
        harness = harness or "codex"
        if harness == "codex":
            if version is None:
                m = VERSION_LIKE.search(env.get("CODEX_VERSION", ""))
                version = m.group(0) if m else None
            thread = env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID")
            if session is None and thread:
                session = f"codex:{thread}"
    return {
        "harness": harness,
        "version": version or env.get("STRINGENCY_OPERATOR_VERSION") or None,
        "session_ref": session,
    }
