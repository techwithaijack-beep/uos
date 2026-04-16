"""Anthropic driver — Claude backend.

Usage:
    from uos.drivers.anthropic import AnthropicDriver
    driver = AnthropicDriver(model="claude-opus-4-6")

Requires: pip install uos[anthropic] and ANTHROPIC_API_KEY set.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class AnthropicDriver:
    model: str = "claude-sonnet-4-6"
    max_tokens_default: int = 1024
    temperature: float = 0.0
    name: str = "anthropic"

    def __post_init__(self) -> None:
        try:
            import anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover - optional dep
            raise RuntimeError(
                "anthropic not installed. pip install uos[anthropic]"
            ) from e
        self._client = anthropic.Anthropic()

    def think(self, prompt: str, tools: list[dict] | None = None,
              max_tokens: int = 256) -> tuple[str, dict]:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens_default,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content
            if getattr(block, "type", None) == "text"
        )
        usage = {
            "total_tokens": (msg.usage.input_tokens + msg.usage.output_tokens),
            "prompt_tokens": msg.usage.input_tokens,
            "completion_tokens": msg.usage.output_tokens,
        }
        return text, usage
