"""The Claude API layer.

One method, `structured()`: a system prompt, a user prompt, a JSON Schema, and
a validated dict back. Every pass in this tool is that shape, so the retry,
caching, and refusal handling live here once.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# Streaming, and a large ceiling: a routes pass for a five-entity app is a lot
# of tokens, and a non-streaming request at this size trips the SDK's HTTP
# timeout rather than returning a partial answer.
MAX_TOKENS = 64000


class LLMError(RuntimeError):
    pass


class Refused(LLMError):
    """Claude declined the request. Carries the category so the CLI can say why."""

    def __init__(self, category: str | None, explanation: str | None) -> None:
        super().__init__(f"request refused ({category or 'unspecified'}): {explanation or ''}")
        self.category = category
        self.explanation = explanation


class LLM(Protocol):
    offline: bool

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict: ...


class OfflineLLM:
    """No API calls. Passes fall back to their deterministic baseline.

    This is not a mock -- it is a real, if unimaginative, generator, and it is
    what protogen's own test suite runs against. A pipeline that can only be
    exercised with a network call and a credit card is a pipeline that stops
    being tested.
    """

    offline = True

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        raise NotImplementedError(f"pass {label!r} has no offline baseline")


class ClaudeLLM:
    offline = False

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.environ.get("PROTOGEN_MODEL", DEFAULT_MODEL)
        self.effort = effort or os.environ.get("PROTOGEN_EFFORT", DEFAULT_EFFORT)
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise LLMError(
                    "the `anthropic` package is not installed; `pip install anthropic`"
                ) from exc
            # Zero-arg: resolves ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
            # `ant auth login` profile. An unset env var does not mean no
            # credentials.
            self._client = anthropic.Anthropic()

    def structured(self, *, system: str, user: str, schema: dict, label: str) -> dict:
        with self._client.beta.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            # Adaptive thinking: `budget_tokens` is rejected on this model
            # family, and disabling thinking on Opus 5 costs more in
            # malformed tool calls than it saves.
            thinking={"type": "adaptive"},
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            # Server-side fallback: a safety refusal on one pass would
            # otherwise abort a generation that is most of the way done.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=[
                {
                    "type": "text",
                    "text": system,
                    # The system prompt is identical across the repair loop's
                    # attempts; caching it is most of the win on a retry.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            raise Refused(
                getattr(details, "category", None), getattr(details, "explanation", None)
            )

        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise LLMError(f"pass {label!r} returned no text block")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"pass {label!r} returned invalid JSON: {exc}") from exc


def build_llm(offline: bool = False) -> LLM:
    if offline or os.environ.get("PROTOGEN_LLM") == "offline":
        return OfflineLLM()
    return ClaudeLLM()
