"""L2: Episodic memory — session-scoped KV ring buffer.

Substring query; millisecond-ish latency. Survives L1 eviction; does not
survive a fresh kernel instance unless persisted (not in v0.1).
"""
from __future__ import annotations
from collections import deque
from typing import Any
from uos.kernel.mmu import Handle


class EpisodicMemory:
    name = "L2"

    def __init__(self, capacity: int = 10_000) -> None:
        self.capacity = capacity
        self._store: dict[int, Any] = {}
        self._order: deque[int] = deque()

    def read(self, h: Handle) -> Any:
        return self._store[h.id]

    def write(self, h: Handle, v: Any) -> None:
        if h.id not in self._store and len(self._order) >= self.capacity:
            oldest = self._order.popleft()
            self._store.pop(oldest, None)
        if h.id not in self._store:
            self._order.append(h.id)
        self._store[h.id] = v

    def has(self, h: Handle) -> bool:
        return h.id in self._store

    def evict(self, h: Handle) -> None:
        self._store.pop(h.id, None)
        try:
            self._order.remove(h.id)
        except ValueError:
            pass

    def working_set(self) -> list[Handle]:
        return [Handle(hid, "L2") for hid in self._store.keys()]

    def query(self, q: str, top_k: int = 5) -> list[Handle]:
        """Cheap substring scan. Good enough for session-scoped recall."""
        q_low = q.lower()
        hits = []
        for hid, v in self._store.items():
            s = str(v).lower()
            if q_low in s:
                hits.append((s.count(q_low), hid))
        hits.sort(reverse=True)
        return [Handle(hid, "L2") for _, hid in hits[:top_k]]
