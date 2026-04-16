"""Execution trace — append-only log of ISA instructions.

Every instruction the kernel dispatches is recorded here with enough metadata
for replay and audit. See spec/isa.md §encoding.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Iterator
import json
import time


class Opcode(str, Enum):
    THINK = "THINK"
    CALL  = "CALL"
    LOAD  = "LOAD"
    STORE = "STORE"
    FORK  = "FORK"
    JOIN  = "JOIN"
    YIELD = "YIELD"
    TRAP  = "TRAP"
    RET   = "RET"   # sugar: process exit


@dataclass
class Instr:
    opcode: Opcode
    pid: int
    ts: float
    # operands / metadata; opcode-specific
    operands: dict = field(default_factory=dict)
    cap_id: str | None = None        # for CALL
    result: Any = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["opcode"] = self.opcode.value
        return d


class Trace:
    """Append-only instruction log. O(1) append, O(n) filter."""

    def __init__(self) -> None:
        self._log: list[Instr] = []

    def record(
        self,
        opcode: Opcode,
        pid: int,
        *,
        operands: dict | None = None,
        cap_id: str | None = None,
        result: Any = None,
    ) -> Instr:
        instr = Instr(
            opcode=opcode,
            pid=pid,
            ts=time.time(),
            operands=operands or {},
            cap_id=cap_id,
            result=result,
        )
        self._log.append(instr)
        return instr

    def __iter__(self) -> Iterator[Instr]:
        return iter(self._log)

    def __len__(self) -> int:
        return len(self._log)

    def filter(self, **kw) -> list[Instr]:
        def match(i: Instr) -> bool:
            return all(getattr(i, k, None) == v for k, v in kw.items())
        return [i for i in self._log if match(i)]

    def for_pid(self, pid: int) -> list[Instr]:
        return [i for i in self._log if i.pid == pid]

    def calls(self, cap_id: str | None = None) -> list[Instr]:
        out = [i for i in self._log if i.opcode == Opcode.CALL]
        if cap_id is not None:
            out = [i for i in out if i.cap_id == cap_id]
        return out

    def summary(self, max_lines: int = 40) -> str:
        """Human-readable trace summary (for debug / quickstart)."""
        lines = []
        for i, instr in enumerate(self._log):
            if i >= max_lines:
                lines.append(f"… {len(self._log) - max_lines} more instructions")
                break
            op = instr.opcode.value
            pid = instr.pid
            meta = ""
            if instr.opcode == Opcode.CALL:
                fname = instr.operands.get("name", "?")
                meta = f" {fname}"
            elif instr.opcode == Opcode.THINK:
                tokens = instr.operands.get("tokens", 0)
                meta = f" ({tokens}t)"
            elif instr.opcode == Opcode.FORK:
                child = instr.operands.get("child_pid")
                meta = f" → pid={child}"
            elif instr.opcode == Opcode.RET:
                meta = f" {repr(instr.result)[:40]}"
            lines.append(f"  [p{pid}] {op}{meta}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps([i.to_dict() for i in self._log], default=str, indent=2)

    # ---- metrics ----------------------------------------------------------
    def total_tokens(self) -> int:
        return sum(i.operands.get("tokens", 0) for i in self._log
                   if i.opcode == Opcode.THINK)

    def call_count(self, name: str | None = None) -> int:
        calls = self.calls()
        if name is None:
            return len(calls)
        return sum(1 for c in calls if c.operands.get("name") == name)
