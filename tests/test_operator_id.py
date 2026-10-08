"""Who is operating (lung, 2026-10-08: version `unknown`, an invented session name)."""

from __future__ import annotations

import pytest

from stringency.operator_id import operator_env

CLAUDE = {
    "CLAUDECODE": "1",
    "CLAUDE_CODE_SESSION_ID": "0f1e2d3c-aaaa-bbbb-cccc-000000000001",
    "CLAUDE_CODE_EXECPATH": "/home/u/.local/share/claude/versions/2.1.294",
}
OURS = ("STRINGENCY_OPERATOR", "STRINGENCY_OPERATOR_VERSION", "STRINGENCY_SESSION_REF")


def _env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for k in (*OURS, *CLAUDE):
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_outside_claude_code_only_the_stringency_variables_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, {})
    assert operator_env() == {"harness": None, "version": None, "session_ref": None}
    _env(monkeypatch, {"STRINGENCY_OPERATOR": "codex", "STRINGENCY_OPERATOR_VERSION": "1.0"})
    assert operator_env() == {"harness": "codex", "version": "1.0", "session_ref": None}


def test_inside_claude_code_unset_or_unknown_values_come_from_its_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _env(monkeypatch, CLAUDE)
    assert operator_env() == {
        "harness": "claude-code",
        "version": "2.1.294",
        "session_ref": "claude-code:0f1e2d3c-aaaa-bbbb-cccc-000000000001",
    }
    _env(monkeypatch, {**CLAUDE, "STRINGENCY_OPERATOR_VERSION": "unknown"})
    assert operator_env()["version"] == "2.1.294"
    # what the operator sets explicitly stands
    _env(monkeypatch, {**CLAUDE, "STRINGENCY_SESSION_REF": "claude-code:named"})
    assert operator_env()["session_ref"] == "claude-code:named"
    # another harness running inside a Claude Code shell keeps its own identity
    _env(monkeypatch, {**CLAUDE, "STRINGENCY_OPERATOR": "codex"})
    assert operator_env() == {"harness": "codex", "version": None, "session_ref": None}
