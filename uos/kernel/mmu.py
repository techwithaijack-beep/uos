"""Attention MMU — virtual memory for the context window.

Maps logical memory handles to resident context tokens. Pages in from higher
memory tiers on miss; evicts cold pages under a pluggable policy. See
spec/semantics.md §MMU coherence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol, Callable
import itertools
import time


_handle_counter = itertools.count(1)


@dataclass(frozen=True)
class Handle:
    """Opaque memory handle. Always paired with a tier hint for fast-path resolution."""
    id: int
    tier_hint: str  # "L1" | "L2" | "L3" | "L4"

    def __repr__(self) -> str:
        return f"<h{self.id}@{self.tier_hint}>"


def _new_handle(tier: str) -> Handle:
    return Handle(next(_handle_counter), tier)


class MemoryTier(Protocol):
    """Every tier implements a minimal interface. See uos/mm/."""
    name: str
    def read(self, h: Handle) -> Any: ...
    def write(self, h: Handle, v: Any) -> None: ...
    def has(self, h: Handle) -> bool: ...
    def evict(self, h: Handle) -> None: ...
    def working_set(self) -> list[Handle]: ...


# ---------------------------------------------------------------------------
# Eviction policies
# ---------------------------------------------------------------------------

class EvictionPolicy(Protocol):
    def pick(self, candidates: list[Handle], access_log: dict[int, float]) -> Handle: ...


class LRUPolicy:
    """Least-recently-used."""
    def pick(self, candidates, access_log):
        return min(candidates, key=lambda h: access_log.get(h.id, 0.0))


class ImportanceWeightedLRU:
    """LRU weighted by an importance score.

    importance(h) = recency_weight * 1/(now - last_access)
                  + reference_weight * ref_count[h]
                  + task_weight * task_relevance(h)
    (task_relevance is pluggable; defaults to constant.)
    """
    def __init__(self,
                 recency_weight: float = 1.0,
                 reference_weight: float = 0.5,
                 task_weight: float = 0.0,
                 task_relevance: Callable[[Handle], float] | None = None) -> None:
        self.recency_weight = recency_weight
        self.reference_weight = reference_weight
        self.task_weight = task_weight
        self.task_relevance = task_relevance or (lambda h: 0.0)

    def pick(self, candidates, access_log, ref_count=None):
        ref_count = ref_count or {}
        now = time.time()
        def score(h: Handle) -> float:
            last = access_log.get(h.id, now)
            recency = 1.0 / max(now - last, 1e-3)
            refs = ref_count.get(h.id, 0)
            return (self.recency_weight * recency
                    + self.reference_weight * refs
                    + self.task_weight * self.task_relevance(h))
        return min(candidates, key=score)  # lowest score → evict


# ---------------------------------------------------------------------------
# MMU
# ---------------------------------------------------------------------------

@dataclass
class _TLBEntry:
    value: Any
    last_access: float
    ref_count: int = 0


class MMU:
    """Attention MMU.

    Tier lookup order: L1 → L2 → L3 → L4.
    On L1 miss: fetch from the lowest tier that has the handle and promote to L1.
    On L1 full: evict via the active policy to make room.
    """

    def __init__(
        self,
        tiers: dict[str, MemoryTier],
        *,
        l1_capacity: int = 32,
        policy: EvictionPolicy | None = None,
    ) -> None:
        if "L1" not in tiers:
            raise ValueError("MMU requires at least an L1 tier")
        self.tiers = tiers
        self.l1_capacity = l1_capacity
        self.policy = policy or ImportanceWeightedLRU()

        # TLB: hot cache of recent resolutions
        self._tlb: dict[int, _TLBEntry] = {}

        # Metrics
        self.page_ins = 0
        self.page_outs = 0
        self.tlb_hits = 0
        self.tlb_misses = 0

    # ---- allocate ---------------------------------------------------------
    def allocate(self, value: Any, *, tier: str = "L1") -> Handle:
        if tier not in self.tiers:
            raise ValueError(f"Unknown tier: {tier}")
        # Make room before the write so we don't transiently exceed capacity.
        if tier == "L1":
            self._ensure_capacity()
        h = _new_handle(tier)
        self.tiers[tier].write(h, value)
        self._touch(h, value)
        return h

    # ---- load -------------------------------------------------------------
    def load(self, h: Handle) -> Any:
        # TLB
        entry = self._tlb.get(h.id)
        if entry is not None:
            self.tlb_hits += 1
            entry.last_access = time.time()
            entry.ref_count += 1
            return entry.value

        self.tlb_misses += 1

        # Tier lookup: L1 → L2 → L3 → L4
        for tname in ("L1", "L2", "L3", "L4"):
            t = self.tiers.get(tname)
            if t is not None and t.has(h):
                v = t.read(h)
                if tname != "L1":
                    # Page in: promote to L1
                    self._ensure_capacity()
                    self.tiers["L1"].write(h, v)
                    self.page_ins += 1
                self._touch(h, v)
                return v
        raise KeyError(f"Invalid handle: {h}")

    # ---- store ------------------------------------------------------------
    def store(self, v: Any, *, tier: str = "L1", flush: bool = False) -> Handle:
        h = self.allocate(v, tier=tier)
        if flush:
            self.flush(h)
        return h

    def write(self, h: Handle, v: Any) -> None:
        """Update value at an existing handle."""
        t = self._resident_tier(h)
        t.write(h, v)
        self._touch(h, v)

    # ---- flush ------------------------------------------------------------
    def flush(self, h: Handle) -> None:
        """Propagate outward: L1 → L2 → L3 (skip L4; L4 is for lifted skills)."""
        value = self.load(h)
        for tname in ("L2", "L3"):
            t = self.tiers.get(tname)
            if t is not None:
                t.write(h, value)

    # ---- query (delegated to tier-specific search) ------------------------
    def query(self, q: str, *, tier: str = "L3", top_k: int = 5) -> list[Handle]:
        t = self.tiers.get(tier)
        if t is None:
            return []
        fn = getattr(t, "query", None)
        if fn is None:
            return []
        return fn(q, top_k=top_k)

    # ---- stats ------------------------------------------------------------
    def stats(self) -> dict:
        return {
            "page_ins": self.page_ins,
            "page_outs": self.page_outs,
            "tlb_hits": self.tlb_hits,
            "tlb_misses": self.tlb_misses,
            "l1_resident": len(self.tiers["L1"].working_set()),
            "l1_capacity": self.l1_capacity,
        }

    # ---- internals --------------------------------------------------------
    def _touch(self, h: Handle, v: Any) -> None:
        entry = self._tlb.get(h.id)
        if entry is None:
            self._tlb[h.id] = _TLBEntry(value=v, last_access=time.time(), ref_count=1)
        else:
            entry.value = v
            entry.last_access = time.time()
            entry.ref_count += 1

    def _ensure_capacity(self) -> None:
        """Ensure L1 has room for at least one new entry."""
        l1 = self.tiers["L1"]
        ws = l1.working_set()
        # Evict while L1 would overflow AFTER we add one.
        while len(ws) + 1 > self.l1_capacity:
            access_log = {hid: e.last_access for hid, e in self._tlb.items()}
            ref_count = {hid: e.ref_count for hid, e in self._tlb.items()}
            if isinstance(self.policy, ImportanceWeightedLRU):
                victim = self.policy.pick(ws, access_log, ref_count=ref_count)
            else:
                victim = self.policy.pick(ws, access_log)
            # Before eviction from L1, ensure persisted at ≥L2
            if not self.tiers.get("L2", _NullTier()).has(victim):
                l2 = self.tiers.get("L2")
                if l2 is not None:
                    l2.write(victim, l1.read(victim))
            l1.evict(victim)
            self._tlb.pop(victim.id, None)
            self.page_outs += 1
            ws = l1.working_set()

    def _resident_tier(self, h: Handle) -> MemoryTier:
        for tname in ("L1", "L2", "L3", "L4"):
            t = self.tiers.get(tname)
            if t is not None and t.has(h):
                return t
        raise KeyError(f"Handle not resident: {h}")


class _NullTier:
    name = "null"
    def read(self, h): raise KeyError(h)
    def write(self, h, v): pass
    def has(self, h): return False
    def evict(self, h): pass
    def working_set(self): return []
