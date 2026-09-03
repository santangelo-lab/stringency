"""Anthropic Messages API adapter (design 10.2), the direct family. Installed as
`stringency[api]`; kept fully working even though the lab deployment binds `subagent`.

The module's `schema.json` is enforced as structured output (`output_config.format`,
`json_schema`). The resolved model string from the response is what gets recorded; anything
the response does not carry is recorded as `unknown`. Tested against recorded responses only.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from stringency.exit_codes import ConfigError
from stringency.harness.base import Family, Invocation, Request, Sampling

DEFAULT_MODEL = "claude-opus-5"
MAX_TOKENS = 16000


class ApiHarness:
    kind = "api"
    family: Family = "direct"

    def __init__(self, model: str | None = None, client: Any | None = None) -> None:
        self.model = model or DEFAULT_MODEL
        self._client = client
        try:
            import anthropic

            self.version = str(getattr(anthropic, "__version__", "unknown"))
        except ImportError:
            self.version = "unknown"

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ConfigError(
                    "the api harness needs the anthropic SDK: install stringency[api]"
                ) from None
            self._client = anthropic.Anthropic()
        return self._client

    def invoke(
        self, prompt: str, schema: dict[str, Any], *, sampling: Sampling, request: Request
    ) -> Invocation:
        model = sampling.model or self.model
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": sampling.max_tokens or MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        response = self.client.messages.create(**kwargs)
        duration = int((time.monotonic() - t0) * 1000)
        usage = getattr(response, "usage", None)
        resolved = str(getattr(response, "model", None) or "unknown")
        text = "".join(
            getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"
        )
        error = None
        structured: dict[str, Any] | None = None
        if getattr(response, "stop_reason", None) == "refusal":
            details = getattr(response, "stop_details", None)
            error = f"refusal: {getattr(details, 'category', 'unknown')}"
        else:
            try:
                parsed = json.loads(text) if text else None
                structured = parsed if isinstance(parsed, dict) else None
                if structured is None:
                    error = "response is not a JSON object"
            except json.JSONDecodeError as e:
                error = f"unparseable response: {e}"
        return Invocation(
            structured,
            text,
            False,
            model_requested=model,
            model_resolved=resolved,
            harness_kind=self.kind,
            harness_version=self.version,
            tokens_in=getattr(usage, "input_tokens", None),
            tokens_out=getattr(usage, "output_tokens", None),
            duration_ms=duration,
            via="direct",
            isolation="enforced",
            error=error,
        )

    def dispatch(self, requests: list[Request], dispatch_dir: Path) -> None:
        raise NotImplementedError("the api harness is a direct adapter")

    def collect(self, requests: list[Request], dispatch_dir: Path) -> list[Invocation]:
        raise NotImplementedError("the api harness is a direct adapter")
