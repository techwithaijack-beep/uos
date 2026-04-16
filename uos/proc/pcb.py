"""Process Control Block and lifecycle states.

See WHITEPAPER §5 and spec/semantics.md §process states.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class ProcState(Enum):
    NEW     = auto()
    READY   = auto()
    RUNNING = auto()
    BLOCKED = auto()
    ZOMBIE  = auto()


@dataclass
class PCB:
    pid: int
    goal: str
    caps: "Capability"               # forward-ref; resolved at runtime  # noqa: F821
    budget_tokens: int
    priority: int = 1
    effective_priority: int = 1
    parent_pid: int | None = None
    state: ProcState = ProcState.NEW
    children: set[int] = field(default_factory=set)
    exit_value: Any = None
    tokens_consumed: int = 0
    body: Callable | None = None     # the process body function

    def snapshot(self) -> dict:
        """Read-only view for introspection."""
        return {
            "pid": self.pid,
            "parent_pid": self.parent_pid,
            "goal": self.goal,
            "state": self.state.name,
            "priority": self.priority,
            "effective_priority": self.effective_priority,
            "budget_tokens": self.budget_tokens,
            "tokens_consumed": self.tokens_consumed,
            "children": sorted(self.children),
            "exit_value": repr(self.exit_value) if self.exit_value is not None else None,
        }
