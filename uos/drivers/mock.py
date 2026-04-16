"""MockDriver — deterministic, zero-cost driver for tests and examples.

Behavior is scripted: you hand it a list of (pattern_or_None, response) pairs,
and each `think` pops the next matching scripted response. Useful for testing
the kernel without an API key.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import re


@dataclass
class MockDriver:
    """Scripted LLM.

    Each `script` entry is either:
      - a string (always matches)
      - a (pattern, response) tuple where pattern is a regex over the prompt
      - a callable (prompt, tools) -> str
    """
    name: str = "mock"
    script: list = field(default_factory=list)
    default: str = "DONE"
    tokens_per_step: int = 50
    _idx: int = 0

    def think(self, prompt: str, tools: list[dict] | None = None,
              max_tokens: int = 256) -> tuple[str, dict]:
        resp = None
        # Sequential script consumption
        if self._idx < len(self.script):
            item = self.script[self._idx]
            self._idx += 1
            if isinstance(item, str):
                resp = item
            elif isinstance(item, tuple):
                pattern, answer = item
                if pattern is None or re.search(pattern, prompt):
                    resp = answer
            elif callable(item):
                resp = item(prompt, tools)
        if resp is None:
            resp = self.default
        usage = {
            "total_tokens": self.tokens_per_step,
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": self.tokens_per_step,
        }
        return resp, usage

    def reset(self) -> None:
        self._idx = 0
