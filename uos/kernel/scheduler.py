"""Cognitive scheduler.

Fair-share over ready processes, measured in TOKEN QUANTA (not wall-clock).
Priority inheritance on JOIN prevents inversion. Pluggable policy module.

Spec: see WHITEPAPER §5 and spec/semantics.md §fair-share.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol
from uos.proc.pcb import PCB, ProcState


class SchedulerPolicy(Protocol):
    def pick(self, ready: list[PCB]) -> PCB | None: ...
    def on_consume(self, pcb: PCB, tokens: int) -> None: ...


class FairShareScheduler:
    """Virtual-time fair share.

    Each process has a virtual clock `v_i` that advances by tokens_consumed / priority.
    The scheduler runs the ready process with the smallest `v_i`.
    """

    def __init__(self, quantum_tokens: int = 512) -> None:
        self.quantum_tokens = quantum_tokens
        self._vclock: dict[int, float] = {}

    def pick(self, ready: list[PCB]) -> PCB | None:
        if not ready:
            return None
        return min(ready, key=lambda p: (self._vclock.get(p.pid, 0.0), p.pid))

    def on_consume(self, pcb: PCB, tokens: int) -> None:
        prio = max(pcb.effective_priority, 1)
        self._vclock[pcb.pid] = self._vclock.get(pcb.pid, 0.0) + tokens / prio

    def on_fork(self, child: PCB, parent: PCB) -> None:
        # Inherit parent's vclock to avoid starving others on a child burst.
        self._vclock[child.pid] = self._vclock.get(parent.pid, 0.0)

    def on_join(self, joiner: PCB, joinee: PCB) -> None:
        # Priority inheritance: joinee runs at joiner's priority while joiner blocks.
        joinee.effective_priority = max(joinee.effective_priority, joiner.priority)

    def on_exit(self, pcb: PCB) -> None:
        # Restore base priority in case it was lifted.
        pcb.effective_priority = pcb.priority
        self._vclock.pop(pcb.pid, None)


# ---- a simple round-robin alternative, for benchmarks ----------------------

class RoundRobinScheduler:
    def __init__(self, quantum_tokens: int = 512) -> None:
        self.quantum_tokens = quantum_tokens
        self._last: int = -1

    def pick(self, ready: list[PCB]) -> PCB | None:
        if not ready:
            return None
        # Pick the ready process with pid > last, else the smallest.
        after = [p for p in ready if p.pid > self._last]
        choice = min(after, key=lambda p: p.pid) if after else min(ready, key=lambda p: p.pid)
        self._last = choice.pid
        return choice

    def on_consume(self, pcb, tokens): pass
    def on_fork(self, child, parent): pass
    def on_join(self, joiner, joinee): pass
    def on_exit(self, pcb): pass
