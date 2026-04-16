"""L3: Semantic memory — vector + graph hybrid.

v0.1 ships a simple bag-of-words vectorizer (no external deps) plus a
string-keyed adjacency graph. Swap in a real embedder for production by
subclassing and overriding `_embed`.
"""
from __future__ import annotations
import math
import re
from collections import Counter
from typing import Any
from uos.kernel.mmu import Handle


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(s: str) -> list[str]:
    return _WORD_RE.findall(s.lower())


class SemanticMemory:
    """Persistent-intent semantic store.

    Vectors: bag-of-words TF (L2-normalized) — cheap, deterministic, good
    enough for the reference implementation. Graph: adjacency map with
    named edges for relation queries.
    """
    name = "L3"

    def __init__(self) -> None:
        self._store: dict[int, Any] = {}
        self._vecs: dict[int, dict[str, float]] = {}
        # graph: handle_id → {edge_label: set(handle_ids)}
        self._graph: dict[int, dict[str, set[int]]] = {}

    # ---- tier contract ----------------------------------------------------
    def read(self, h: Handle) -> Any:
        return self._store[h.id]

    def write(self, h: Handle, v: Any) -> None:
        self._store[h.id] = v
        self._vecs[h.id] = self._embed(v)

    def has(self, h: Handle) -> bool:
        return h.id in self._store

    def evict(self, h: Handle) -> None:
        self._store.pop(h.id, None)
        self._vecs.pop(h.id, None)
        self._graph.pop(h.id, None)

    def working_set(self) -> list[Handle]:
        return [Handle(hid, "L3") for hid in self._store.keys()]

    # ---- queries ----------------------------------------------------------
    def query(self, q: str, top_k: int = 5) -> list[Handle]:
        qv = self._embed(q)
        scores = [
            (_cosine(qv, v), hid)
            for hid, v in self._vecs.items()
        ]
        scores.sort(reverse=True)
        return [Handle(hid, "L3") for s, hid in scores[:top_k] if s > 0]

    def neighbors(self, h: Handle, edge: str | None = None) -> list[Handle]:
        adj = self._graph.get(h.id, {})
        if edge is not None:
            return [Handle(nid, "L3") for nid in adj.get(edge, set())]
        out: set[int] = set()
        for ids in adj.values():
            out |= ids
        return [Handle(nid, "L3") for nid in out]

    # ---- graph ops --------------------------------------------------------
    def link(self, a: Handle, b: Handle, edge: str) -> None:
        self._graph.setdefault(a.id, {}).setdefault(edge, set()).add(b.id)

    # ---- internals --------------------------------------------------------
    def _embed(self, v: Any) -> dict[str, float]:
        tokens = _tokenize(str(v))
        if not tokens:
            return {}
        counts = Counter(tokens)
        norm = math.sqrt(sum(c * c for c in counts.values()))
        return {w: c / norm for w, c in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    return sum(a[w] * b[w] for w in common)
