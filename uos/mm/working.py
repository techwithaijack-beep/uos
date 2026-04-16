"""L1: Working memory — the bytes resident in the current context window."""
from __future__ import annotations
from typing import Any
from uos.kernel.mmu import Handle


class WorkingMemory:
    """In-context values. Capacity-bounded; eviction goes to L2."""
    name = "L1"

    def __init__(self) -> None:
        self._store: dict[int, Any] = {}

    def read(self, h: Handle) -> Any:
        return self._store[h.id]

    def write(self, h: Handle, v: Any) -> None:
        self._store[h.id] = v

    def has(self, h: Handle) -> bool:
        return h.id in self._store

    def evict(self, h: Handle) -> None:
        self._store.pop(h.id, None)

    def working_set(self) -> list[Handle]:
        return [Handle(hid, "L1") for hid in self._store.keys()]

    def __len__(self) -> int:
        return len(self._store)
