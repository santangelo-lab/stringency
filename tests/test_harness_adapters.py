"""The `command` and `openai-compatible` judgment adapters (design 10.2; backlog L34 H3), Codex
as an operator harness (H2), the egress class of a local endpoint, and the conformance fixtures
(L36). No network: a stand-in command, a fake client, recorded shapes."""

from __future__ import annotations

import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from stringency.egress import harness_class
from stringency.exit_codes import ConfigError
from stringency.harness.base import Request, Sampling
from stringency.harness.command import CommandHarness
from stringency.harness.openai_compat import OpenAICompatibleHarness
from stringency.operator_id import operator_env

ROOT = Path(__file__).parent.parent


def _req() -> Request:
    return Request(1, "n-1", "prompt text", {"type": "object"}, ("A",), "m@1", "prompt.md")


def _script(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "judge.py"
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def test_command_adapter_runs_the_command_per_call_and_reads_the_response(tmp_path: Path) -> None:
    """The prompt arrives on stdin, the schema in a file, the answer in the response file; usage
    comes from a codex-shaped `turn.completed` event on stdout."""
    script = _script(
        tmp_path,
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "schema = json.load(open(sys.argv[1]))\n"
        "json.dump({'items': [{'item_id': 'A', 'label': 'keep', 'seen': prompt, 'schema': schema['type']}]}, open(sys.argv[2], 'w'))\n"
        "print(json.dumps({'type': 'turn.started'}))\n"
        "print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 12, 'output_tokens': 5}}))\n",
    )
    h = CommandHarness(f"{sys.executable} {script} {{schema}} {{response}}", model="gpt-6")
    inv = h.invoke("prompt text", {"type": "object"}, sampling=Sampling(), request=_req())
    assert inv.error is None and inv.structured is not None
    assert inv.structured["items"][0] == {
        "item_id": "A",
        "label": "keep",
        "seen": "prompt text",
        "schema": "object",
    }
    assert (inv.via, inv.isolation, inv.harness_kind) == ("command", "as_reported", "command")
    assert inv.model_requested == "gpt-6" and inv.model_resolved == "unknown"
    assert inv.tokens_in == 12 and inv.tokens_out == 5 and inv.duration_ms is not None
    # the prompt in a file, the answer on stdout as the last JSON object
    script2 = _script(
        tmp_path / "two" if (tmp_path / "two").mkdir() or True else tmp_path,
        "import sys\n"
        "text = open(sys.argv[1]).read()\n"
        "print('log line')\n"
        "print('{\"items\": [{\"item_id\": \"A\", \"label\": \"' + ('keep' if 'prompt' in text else 'drop') + '\"}]}')\n",
    )
    h2 = CommandHarness(f"{sys.executable} {script2} {{prompt_file}}")
    inv2 = h2.invoke("prompt text", {}, sampling=Sampling(), request=_req())
    assert inv2.error is None and inv2.structured == {"items": [{"item_id": "A", "label": "keep"}]}
    assert inv2.tokens_in is None


def test_command_adapter_names_every_failure(tmp_path: Path) -> None:
    h = CommandHarness("stringency-no-such-command-xyz {schema}")
    assert (
        h.invoke("p", {}, sampling=Sampling(), request=_req()).error
        == "command not found: stringency-no-such-command-xyz"
    )
    failing = _script(tmp_path, "import sys; sys.stderr.write('boom'); sys.exit(3)\n")
    inv = CommandHarness(f"{sys.executable} {failing}").invoke(
        "p", {}, sampling=Sampling(), request=_req()
    )
    assert inv.error == "command exited 3: boom"
    silent = _script(tmp_path, "pass\n")
    inv = CommandHarness(f"{sys.executable} {silent} {{response}}").invoke(
        "p", {}, sampling=Sampling(), request=_req()
    )
    assert inv.error == "command left no response file"
    inv = CommandHarness(f"{sys.executable} {silent}").invoke(
        "p", {}, sampling=Sampling(), request=_req()
    )
    assert inv.error == "no JSON object on the command's standard output"
    bad = _script(tmp_path, "import sys; open(sys.argv[1], 'w').write('[1]')\n")
    inv = CommandHarness(f"{sys.executable} {bad} {{response}}").invoke(
        "p", {}, sampling=Sampling(), request=_req()
    )
    assert inv.error == "response is not a JSON object"
    slow = _script(tmp_path, "import time; time.sleep(5)\n")
    inv = CommandHarness(f"{sys.executable} {slow}", timeout_s=1).invoke(
        "p", {}, sampling=Sampling(), request=_req()
    )
    assert inv.error == "command timed out after 1s"
    with pytest.raises(ConfigError, match="judgment.command"):
        CommandHarness(None)


class FakeCompletions:
    def __init__(self, recorded: dict) -> None:
        self.recorded = recorded
        self.calls: list[dict] = []

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        r = self.recorded
        return SimpleNamespace(
            model=r["model"],
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=r["content"], refusal=r.get("refusal"))
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=r["usage"]["prompt_tokens"],
                completion_tokens=r["usage"]["completion_tokens"],
            ),
        )


def _client(recorded: dict) -> SimpleNamespace:
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(recorded)))


def test_openai_compatible_adapter_replays_a_recorded_response() -> None:
    recorded = {
        "model": "qwen3:32b",
        "content": json.dumps({"items": [{"item_id": "A", "label": "keep"}]}),
        "usage": {"prompt_tokens": 300, "completion_tokens": 40},
    }
    client = _client(recorded)
    h = OpenAICompatibleHarness(
        "qwen3:32b", base_url="http://localhost:11434/v1", temperature=0.2, seed=7, client=client
    )
    inv = h.invoke(
        "p", {"type": "object", "required": ["items"]}, sampling=Sampling(), request=_req()
    )
    assert inv.error is None and inv.structured == {"items": [{"item_id": "A", "label": "keep"}]}
    assert inv.model_requested == "qwen3:32b" and inv.model_resolved == "qwen3:32b"
    assert inv.tokens_in == 300 and inv.tokens_out == 40
    assert (inv.via, inv.isolation, inv.harness_kind) == ("direct", "enforced", "openai-compatible")
    call = client.chat.completions.calls[0]
    assert call["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "judgment",
            "schema": {"type": "object", "required": ["items"]},
            "strict": True,
        },
    }
    assert call["temperature"] == 0.2 and call["seed"] == 7 and call["model"] == "qwen3:32b"
    # a server that ignores the schema: the invocation is invalid, never silently parsed
    for content, prefix in (
        ("", "server returned no structured output"),
        ("Sure! Here", "unparseable response"),
        ("[1]", "response is not a JSON object"),
    ):
        bad = OpenAICompatibleHarness("m", client=_client({**recorded, "content": content}))
        assert (bad.invoke("p", {}, sampling=Sampling(), request=_req()).error or "").startswith(
            prefix
        )
    refused = OpenAICompatibleHarness(
        "m", client=_client({**recorded, "content": "", "refusal": "no"})
    )
    assert refused.invoke("p", {}, sampling=Sampling(), request=_req()).error == "refusal: no"
    unknown = OpenAICompatibleHarness("m", client=_client({**recorded, "model": None}))
    assert unknown.invoke("p", {}, sampling=Sampling(), request=_req()).model_resolved == "unknown"
    with pytest.raises(ConfigError, match="judgment.model"):
        OpenAICompatibleHarness(None)


def test_codex_session_is_recognised(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "STRINGENCY_OPERATOR",
        "STRINGENCY_OPERATOR_VERSION",
        "STRINGENCY_SESSION_REF",
        "CLAUDECODE",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CODEX_VERSION", "0.163.0")
    monkeypatch.setenv("CODEX_THREAD_ID", "01a16026-82a8-75c1-8138-104ec9fafe29")
    assert operator_env() == {
        "harness": "codex",
        "version": "0.163.0",
        "session_ref": "codex:01a16026-82a8-75c1-8138-104ec9fafe29",
    }
    monkeypatch.setenv("STRINGENCY_OPERATOR", "claude-science")
    assert operator_env()["harness"] == "claude-science" and operator_env()["session_ref"] is None


def test_local_endpoint_sends_nothing_off_the_machine() -> None:
    assert harness_class("openai-compatible", "http://localhost:11434/v1")[0] == 0
    assert harness_class("openai-compatible", "http://127.0.0.1:8000/v1")[0] == 0
    assert harness_class("openai-compatible", "https://api.example.org/v1") == (
        3,
        "https://api.example.org/v1",
        harness_class("openai-compatible")[2],
    )
    assert harness_class("openai-compatible")[0] == 3 and harness_class("command")[0] == 3


def test_conformance_fixtures_enumerate_and_hold() -> None:
    spec = importlib.util.spec_from_file_location(
        "conformance", ROOT / "integrations" / "conformance.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.dispatch_cases("codex") == []
    core = (
        ROOT / "integrations" / "claude-science" / "stringency-operator" / "SKILL.md"
    ).read_text()
    appendix = (ROOT / "integrations" / "codex" / "README.md").read_text()
    assert mod.hold_cases(core) == []
    assert mod.hold_cases(core + "\n" + appendix) == []
    assert mod.hold_cases(appendix) != []  # the appendix is read beside the skill, not alone
    assert mod.hold_cases("nothing here") != []
    doc = json.loads((ROOT / "tests" / "shared" / "dispatch.json").read_text())
    assert doc["accepted"] and doc["refused"]


def test_render_skill_harness_switch() -> None:
    import yaml

    from tests.test_render_skill import EXAMPLE, _render_example, rs

    text = _render_example()
    assert "call_command" in text
    ctx, problems = rs.validate(yaml.safe_load(EXAMPLE.read_text()), EXAMPLE, None)
    assert not problems
    ctx["harness"] = "codex"
    out = rs.render(ctx)
    assert "CODEX_THREAD_ID" in out and "call_command" not in out.split("## Appendix")[0]
    ctx["harness"] = "claude-code"
    out = rs.render(ctx)
    assert "Claude Code's own environment" in out
