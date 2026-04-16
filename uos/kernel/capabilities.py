"""Capability-based security.

A Capability is an opaque, unforgeable token that authorizes a set of privileges.
Capabilities form a derivation tree under subset(); revocation propagates.
See spec/capabilities.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Optional
import secrets


class CapabilityViolation(Exception):
    """Raised when a capability does not authorize an operation."""


@dataclass(frozen=True)
class _CapHandle:
    """Opaque handle (kernel-private id wrapper)."""
    id: str

    def __repr__(self) -> str:  # don't leak id in logs
        return f"<cap {self.id[:8]}…>"


@dataclass
class _CapEntry:
    id: str
    privileges: frozenset[str]
    parent: Optional[str]
    children: set[str] = field(default_factory=set)
    valid: bool = True


class CapabilityTable:
    """Kernel-private table. Only the Kernel instantiates this."""

    def __init__(self) -> None:
        self._entries: dict[str, _CapEntry] = {}

    # ---- minting & derivation ----------------------------------------------
    def mint(self, privileges: Iterable[str]) -> Capability:
        entry = _CapEntry(
            id=secrets.token_hex(16),
            privileges=frozenset(privileges),
            parent=None,
        )
        self._entries[entry.id] = entry
        return Capability(_CapHandle(entry.id), self)

    def subset(self, parent: Capability, privileges: Iterable[str]) -> Capability:
        parent_e = self._require(parent._handle.id)
        requested = frozenset(privileges)
        # Start with exact intersection.
        narrowed = requested & parent_e.privileges
        # Then admit requested privs that are covered by parent wildcards or prefixes:
        #   parent "tool.*"    → child may hold "tool.search"
        #   parent "fs.read"   → child may hold "fs.read:/path"
        for p in requested:
            if p in narrowed:
                continue
            # wildcard coverage
            if "." in p:
                ns = p.split(".", 1)[0]
                if f"{ns}.*" in parent_e.privileges:
                    narrowed = narrowed | {p}
                    continue
            # prefix coverage
            if ":" in p:
                prefix = p.split(":", 1)[0]
                if prefix in parent_e.privileges:
                    narrowed = narrowed | {p}
        entry = _CapEntry(
            id=secrets.token_hex(16),
            privileges=narrowed,
            parent=parent_e.id,
        )
        self._entries[entry.id] = entry
        parent_e.children.add(entry.id)
        return Capability(_CapHandle(entry.id), self)

    # ---- revocation --------------------------------------------------------
    def revoke(self, cap: Capability) -> None:
        self._revoke_tree(cap._handle.id)

    def _revoke_tree(self, cid: str) -> None:
        e = self._entries.get(cid)
        if e is None or not e.valid:
            return
        e.valid = False
        for child_id in list(e.children):
            self._revoke_tree(child_id)

    # ---- authorization check ----------------------------------------------
    def authorizes(self, cap: Capability, privilege: str) -> bool:
        e = self._entries.get(cap._handle.id)
        if e is None or not e.valid:
            return False
        if privilege in e.privileges:
            return True
        # Prefix match: "fs.read" authorizes "fs.read:/path"
        if ":" in privilege:
            prefix = privilege.split(":", 1)[0]
            if prefix in e.privileges:
                return True
        # Wildcard: "tool.*" authorizes "tool.web_search"
        if "." in privilege:
            ns = privilege.split(".", 1)[0]
            if f"{ns}.*" in e.privileges:
                return True
        return False

    # ---- internals ---------------------------------------------------------
    def _require(self, cid: str) -> _CapEntry:
        e = self._entries.get(cid)
        if e is None:
            raise CapabilityViolation(f"Unknown capability: {cid[:8]}…")
        if not e.valid:
            raise CapabilityViolation(f"Revoked capability: {cid[:8]}…")
        return e


class Capability:
    """User-visible capability handle.

    Opaque: you cannot inspect its privilege set from userland. Use subset()
    to narrow, and pass it to kernel calls that need authorization.
    """

    __slots__ = ("_handle", "_table")

    def __init__(self, handle: _CapHandle, table: CapabilityTable) -> None:
        self._handle = handle
        self._table = table

    def subset(self, privileges: Iterable[str]) -> "Capability":
        """Derive a narrower capability for delegation."""
        return self._table.subset(self, privileges)

    def authorizes(self, privilege: str) -> bool:
        return self._table.authorizes(self, privilege)

    def __repr__(self) -> str:
        return f"Capability({self._handle})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Capability) and other._handle.id == self._handle.id

    def __hash__(self) -> int:
        return hash(self._handle.id)
