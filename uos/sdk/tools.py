"""The @tool decorator — the single ergonomic entry point for devs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Optional
import inspect


@dataclass
class Tool:
    name: str
    fn: Callable
    token_cost: int = 0
    doc: str = ""

    @property
    def privilege(self) -> str:
        return f"tool.{self.name}"


def tool(fn: Optional[Callable] = None, *, name: Optional[str] = None,
         token_cost: int = 0) -> Any:
    """Decorator: mark a plain function as a tool.

    Usage:
        @tool
        def add(a: int, b: int) -> int:
            return a + b
    """
    def wrap(f: Callable) -> Tool:
        return Tool(
            name=name or f.__name__,
            fn=f,
            token_cost=token_cost,
            doc=inspect.getdoc(f) or "",
        )
    return wrap(fn) if fn else wrap
