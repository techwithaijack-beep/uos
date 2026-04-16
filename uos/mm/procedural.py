"""L4: Procedural memory — callable skills, lifted from successful traces.

When a process exits successfully and its trace contains a repeated subsequence
of CALLs the kernel has seen N times, the subsequence is promoted to a Skill.
Skills are invocable via `kernel.call(cap, "skill:<name>", …)`.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from uos.kernel.mmu import Handle


@dataclass
class Skill:
    name: str
    steps: list[dict]           # each: {"tool": name, "args": [...], "kwargs": {...}}
    invocations: int = 0
    successes: int = 0

    def confidence(self) -> float:
        return self.successes / max(self.invocations, 1)


class ProceduralMemory:
    """Skill library. Same tier contract as other mm/ modules."""
    name = "L4"

    def __init__(self) -> None:
        self._store: dict[int, Skill] = {}
        self._by_name: dict[str, int] = {}

    # ---- tier contract ----------------------------------------------------
    def read(self, h: Handle) -> Any:
        return self._store[h.id]

    def write(self, h: Handle, v: Any) -> None:
        if not isinstance(v, Skill):
            raise TypeError("ProceduralMemory stores Skill objects")
        self._store[h.id] = v
        self._by_name[v.name] = h.id

    def has(self, h: Handle) -> bool:
        return h.id in self._store

    def evict(self, h: Handle) -> None:
        s = self._store.pop(h.id, None)
        if s is not None:
            self._by_name.pop(s.name, None)

    def working_set(self) -> list[Handle]:
        return [Handle(hid, "L4") for hid in self._store.keys()]

    # ---- skill registry ---------------------------------------------------
    def find(self, name: str) -> Skill | None:
        hid = self._by_name.get(name)
        return self._store.get(hid) if hid is not None else None

    def list_skills(self) -> list[Skill]:
        return list(self._store.values())

    # ---- lifting ----------------------------------------------------------
    def lift_from_trace(self, trace_calls: list[dict], *, name: str,
                        min_steps: int = 2) -> Skill | None:
        """Promote a sequence of CALL records to a Skill.

        `trace_calls` is a list of dicts like {"name": ..., "args_len": ..., …}
        extracted from the trace. v0.1 lifts the raw sequence; later versions
        can generalize arguments via heuristics.
        """
        if len(trace_calls) < min_steps:
            return None
        if name in self._by_name:
            return self._store[self._by_name[name]]
        steps = [{"tool": c["name"]} for c in trace_calls]
        s = Skill(name=name, steps=steps)
        # We don't have a handle yet — the kernel can register via MMU.allocate
        # if it wants a handle. For the registry we just index by name.
        return s
