"""OpenAI driver.

Usage:
    from uos.drivers.openai import OpenAIDriver
    driver = OpenAIDriver(model="gpt-4o-mini")

Requires: pip install uos[openai] and OPENAI_API_KEY set.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class OpenAIDriver:
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    name: str = "openai"

    def __post_init__(self) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "openai not installed. pip install uos[openai]"
            ) from e
        self._client = OpenAI()

    def think(self, prompt: str, tools=None, max_tokens: int = 256):
        r = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = r.choices[0].message.content or ""
        usage = {
            "total_tokens": r.usage.total_tokens,
            "prompt_tokens": r.usage.prompt_tokens,
            "completion_tokens": r.usage.completion_tokens,
        }
        return text, usage
