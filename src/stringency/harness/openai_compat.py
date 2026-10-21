"""The `openai-compatible` direct adapter (design 10.2 and 17; backlog L34 H3,
`judge-sources-plan.md` S1): any server speaking the OpenAI chat completions shape, Ollama's
`/v1` and vLLM first. The module's `schema.json` goes as `response_format: json_schema` with
`strict: true`; `temperature` and `seed` come from `Sampling` or the project's `judgment:`
block. A server that ignores the schema and returns no JSON object leaves the invocation
invalid with its error named, never a silently parsed answer. Installed as `stringency[openai]`;
tested against recorded responses only."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from stringency.exit_codes import ConfigError
from stringency.harness.base import Family, Invocation, Request, Sampling

DEFAULT_BASE_URL = "http://localhost:11434/v1"
MAX_TOKENS = 16000


class OpenAICompatibleHarness:
    kind = "openai-compatible"
    family: Family = "direct"

    def __init__(
        self,
        model: str | None,
        *,
        base_url: str | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        client: Any | None = None,
    ) -> None:
        if not model:
            raise ConfigError(
                "the openai-compatible harness needs `judgment.model` in stringency.yml (the "
                "model tag the server serves)"
            )
        self.model = model
        self.base_url = base_url or DEFAULT_BASE_URL
        self.temperature = temperature
        self.seed = seed
        self._client = client
        try:
            import openai

            self.version = str(getattr(openai, "__version__", "unknown"))
        except ImportError:
            self.version = "unknown"

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise ConfigError(
                    "the openai-compatible harness needs the openai SDK: install stringency[openai]"
                ) from None
            self._client = openai.OpenAI(base_url=self.base_url, api_key="stringency")
        return self._client

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        model = sampling.model or self.model
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": sampling.max_tokens or MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "judgment", "schema": schema, "strict": True},
            },
        }
        temperature = sampling.temperature if sampling.temperature is not None else self.temperature
        if temperature is not None:
            kwargs["temperature"] = temperature
        if self.seed is not None:
            kwargs["seed"] = self.seed
        t0 = time.monotonic()
        response = self.client.chat.completions.create(**kwargs)
        duration = int((time.monotonic() - t0) * 1000)
        usage = getattr(response, "usage", None)
        resolved = str(getattr(response, "model", None) or "unknown")
        choices = list(getattr(response, "choices", None) or [])
        message = getattr(choices[0], "message", None) if choices else None
        text = str(getattr(message, "content", None) or "")
        error: str | None = None
        structured: dict[str, Any] | None = None
        refusal = getattr(message, "refusal", None) if message is not None else None
        if refusal:
            error = f"refusal: {refusal}"
        elif not text.strip():
            error = "server returned no structured output"
        else:
            try:
                parsed = json.loads(text)
                structured = parsed if isinstance(parsed, dict) else None
                if structured is None:
                    error = "response is not a JSON object"
            except json.JSONDecodeError as e:
                error = f"unparseable response (the server may ignore response_format): {e}"
        return Invocation(
            structured,
            text,
            False,
            model_requested=model,
            model_resolved=resolved,
            harness_kind=self.kind,
            harness_version=self.version,
            tokens_in=getattr(usage, "prompt_tokens", None),
            tokens_out=getattr(usage, "completion_tokens", None),
            duration_ms=duration,
            via="direct",
            isolation="enforced",
            error=error,
        )

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        raise NotImplementedError("the openai-compatible harness is a direct adapter")

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        raise NotImplementedError("the openai-compatible harness is a direct adapter")
