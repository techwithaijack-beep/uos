"""Inter-process communication — typed message queues and shared regions."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class Message:
    sender_pid: int
    recipient_pid: int
    body: Any
    ts: float = field(default_factory=time.time)


class MessageQueue:
    """Per-process FIFO queue. Bounded to prevent runaway memory."""

    def __init__(self, capacity: int = 1024) -> None:
        self.capacity = capacity
        self._q: deque[Message] = deque()

    def send(self, msg: Message) -> None:
        if len(self._q) >= self.capacity:
            raise OverflowError(f"Queue full (capacity={self.capacity})")
        self._q.append(msg)

    def recv(self) -> Message | None:
        if not self._q:
            return None
        return self._q.popleft()

    def peek(self) -> Message | None:
        return self._q[0] if self._q else None

    def __len__(self) -> int:
        return len(self._q)


class SharedRegion:
    """Named shared memory region. Multiple processes can attach."""

    def __init__(self, region_id: str) -> None:
        self.region_id = region_id
        self._data: dict[str, Any] = {}
        self._attached: set[int] = set()

    def attach(self, pid: int) -> None:
        self._attached.add(pid)

    def detach(self, pid: int) -> None:
        self._attached.discard(pid)

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def keys(self) -> list[str]:
        return list(self._data.keys())


class IPC:
    """Kernel's IPC manager."""

    def __init__(self) -> None:
        self._queues: dict[int, MessageQueue] = {}
        self._regions: dict[str, SharedRegion] = {}

    def register(self, pid: int) -> MessageQueue:
        q = MessageQueue()
        self._queues[pid] = q
        return q

    def unregister(self, pid: int) -> None:
        self._queues.pop(pid, None)
        for r in self._regions.values():
            r.detach(pid)

    def queue_for(self, pid: int) -> MessageQueue:
        q = self._queues.get(pid)
        if q is None:
            raise KeyError(f"No queue for pid={pid}")
        return q

    def send(self, sender: int, recipient: int, body: Any) -> None:
        q = self.queue_for(recipient)
        q.send(Message(sender, recipient, body))

    def recv(self, pid: int) -> Message | None:
        return self.queue_for(pid).recv()

    def shm(self, region_id: str) -> SharedRegion:
        r = self._regions.get(region_id)
        if r is None:
            r = SharedRegion(region_id)
            self._regions[region_id] = r
        return r
