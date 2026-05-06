"""
LLM-Wrapper für Anthropic Claude.

Single point of contact für alle LLM-Calls. Hält Modell-Wahl, Retry-Logic,
Token-Tracking und Logging an einer Stelle.
"""
from __future__ import annotations

from dataclasses import dataclass

import anthropic
import structlog

from backend.config import settings

log = structlog.get_logger()


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient:
    """Dünner Wrapper um den Anthropic-Client. Erweitern wenn Streaming/Tools dazukommen."""

    def __init__(self, model: str | None = None):
        self.model = model or settings.anthropic_model
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Synchroner Completion-Call.

        Für lange Async-Pipelines später auf AsyncAnthropic switchen.
        """
        log.debug("llm_call", model=self.model, max_tokens=max_tokens, temperature=temperature)

        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        text = "".join(
            block.text for block in message.content if block.type == "text"
        )

        log.info(
            "llm_response",
            model=self.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

        return LLMResponse(
            text=text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=self.model,
        )


# Default-Instanz für simple Nutzung
default_llm = LLMClient()
