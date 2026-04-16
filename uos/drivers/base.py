"""Driver interface — what every LLM backend implements."""
from __future__ import annotations
from typing import Protocol, Any


class Driver(Protocol):
    """An LLM driver.

    Methods:
      think(prompt, tools, max_tokens) → (text, usage)
        `tools` is a list of {"name", "privilege"} dicts the driver may surface
        as a tool-call protocol native to its API. The returned `text` is
        plain text; tool-calls are returned via `usage["tool_calls"]` when the
        driver supports them, else the SDK parses them from `text`.

      usage : {"total_tokens": int, "prompt_tokens": int?, "completion_tokens": int?,
               "tool_calls": list?}
    """

    name: str

    def think(self, prompt: str, tools: list[dict] | None = None,
              max_tokens: int = 256) -> tuple[str, dict]: ...
