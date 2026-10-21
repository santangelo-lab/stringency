"""The `command` judgment adapter (design 10.2, backlog L34 H3): the engine runs a configured
command once per replicate, in a fresh process, with the rendered prompt on its standard input
(or in a file the template names) and the module's `schema.json` in a file, and reads the
response the command leaves behind. The first command is `codex exec` (`integrations/codex/
README.md`); any headless agent that can take a prompt and write JSON matching a schema fits.

Placeholders in the template: `{schema}` (a file holding the JSON schema), `{response}` (the file
the command must write its answer to), `{prompt_file}` (a file holding the prompt; when named,
nothing goes on stdin), `{dir}` (a scratch directory for this call). The answer is the JSON
object in the response file, or, when the template names no `{response}`, the last JSON object
on stdout. Standard output in JSON Lines with a `turn.completed` event (codex's shape) yields the
token counts; everything else the command does not report is `unknown`, never guessed.
Recorded `via: command`, `isolation: as_reported` (the process is fresh but can read beyond the
prompt). Tested with a stand-in command only; no network in tests."""

from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from stringency import __version__
from stringency.exit_codes import ConfigError
from stringency.harness.base import Family, Invocation, Request, Sampling

DEFAULT_TIMEOUT_S = 900


class CommandHarness:
    kind = "command"
    version = __version__
    family: Family = "direct"

    def __init__(
        self, command: str | None, *, model: str | None = None, timeout_s: int | None = None
    ) -> None:
        if not command or not command.strip():
            raise ConfigError(
                "the command harness needs `judgment.command` in stringency.yml (the command the "
                "engine runs per replicate; see integrations/codex/README.md)"
            )
        self.command = command
        self.model = model
        self.timeout_s = timeout_s or DEFAULT_TIMEOUT_S

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        model = sampling.model or self.model
        with tempfile.TemporaryDirectory(prefix="stringency-command-") as td:
            d = Path(td)
            schema_path, response_path, prompt_path = (
                d / "schema.json",
                d / "response.json",
                d / "prompt.md",
            )
            schema_path.write_text(json.dumps(schema, indent=2))
            prompt_path.write_text(prompt)
            uses_prompt_file = "{prompt_file}" in self.command
            uses_response = "{response}" in self.command
            argv = [
                a.format(
                    schema=str(schema_path),
                    response=str(response_path),
                    prompt_file=str(prompt_path),
                    dir=str(d),
                )
                for a in shlex.split(self.command)
            ]
            t0 = time.monotonic()
            error: str | None = None
            stdout, stderr, code = "", "", None
            try:
                proc = subprocess.run(
                    argv,
                    input=None if uses_prompt_file else prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    cwd=str(d),
                    check=False,
                )
                stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
            except FileNotFoundError:
                error = f"command not found: {argv[0]}"
            except subprocess.TimeoutExpired:
                error = f"command timed out after {self.timeout_s}s"
            duration = int((time.monotonic() - t0) * 1000)
            raw = ""
            structured: dict[str, Any] | None = None
            if error is None:
                if code != 0:
                    error = f"command exited {code}: {stderr.strip()[-500:]}"
                elif uses_response:
                    if response_path.exists():
                        raw = response_path.read_text()
                    else:
                        error = "command left no response file"
                else:
                    raw = _last_json_line(stdout)
                    if not raw:
                        error = "no JSON object on the command's standard output"
            if error is None:
                try:
                    parsed = json.loads(raw)
                    structured = parsed if isinstance(parsed, dict) else None
                    if structured is None:
                        error = "response is not a JSON object"
                except json.JSONDecodeError as e:
                    error = f"unparseable response: {e}"
            tokens_in, tokens_out = _usage(stdout)
        return Invocation(
            structured,
            raw,
            False,
            model_requested=model,
            model_resolved="unknown",
            harness_kind=self.kind,
            harness_version=self.version,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration,
            via="command",
            isolation="as_reported",
            error=error,
        )

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        raise NotImplementedError("the command harness is a direct adapter")

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        raise NotImplementedError("the command harness is a direct adapter")


def _last_json_line(stdout: str) -> str:
    """The last line of stdout that is a JSON object, else the whole text when it is one."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict) and doc.get("type") is None:
                return line
    text = stdout.strip()
    return text if text.startswith("{") else ""


def _usage(stdout: str) -> tuple[int | None, int | None]:
    """Token counts from a `turn.completed` JSON Lines event (codex exec --json), else None."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "turn.completed":
            u = ev.get("usage") or {}
            return _int(u.get("input_tokens")), _int(u.get("output_tokens"))
    return None, None


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
