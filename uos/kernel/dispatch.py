"""Kernel dispatch — the ISA interpreter.

The kernel is the only thing that runs ISA instructions. User code
(tools, agent bodies) never executes an instruction directly; it makes
syscalls through the Kernel API, and the kernel records each as a trace
entry and charges the budget accordingly.

This file is deliberately short. If it grows past ~500 LOC, redesign.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import time

from uos.kernel.capabilities import Capability, CapabilityTable, CapabilityViolation
from uos.kernel.mmu import MMU, Handle
from uos.kernel.ipc import IPC
from uos.kernel.trace import Trace, Opcode, Instr
from uos.kernel.scheduler import FairShareScheduler, SchedulerPolicy
from uos.mm.working import WorkingMemory
from uos.mm.episodic import EpisodicMemory
from uos.mm.semantic import SemanticMemory
from uos.mm.procedural import ProceduralMemory
from uos.proc.pcb import PCB, ProcState


class BudgetExhausted(Exception): ...
class InvalidHandle(Exception): ...


@dataclass
class _Tool:
    name: str
    fn: Callable
    token_cost: int = 0
    privilege: str = ""  # "tool.<name>"


class Kernel:
    """The μOS kernel. Owns processes, memory, capabilities, trace, IPC.

    Every agent run is a sequence of kernel calls + THINK steps. No user
    code bypasses the kernel for instructions that matter (CALL, LOAD,
    STORE, FORK, JOIN).
    """

    def __init__(
        self,
        driver=None,
        *,
        l1_capacity: int = 32,
        scheduler: SchedulerPolicy | None = None,
    ) -> None:
        # Memory hierarchy
        self._l1 = WorkingMemory()
        self._l2 = EpisodicMemory()
        self._l3 = SemanticMemory()
        self._l4 = ProceduralMemory()
        self.mmu = MMU(
            tiers={"L1": self._l1, "L2": self._l2, "L3": self._l3, "L4": self._l4},
            l1_capacity=l1_capacity,
        )

        # Security
        self.caps = CapabilityTable()
        self._root_cap: Capability | None = None

        # IPC
        self.ipc = IPC()

        # Trace
        self.trace = Trace()

        # Processes
        self._procs: dict[int, PCB] = {}
        self._next_pid = 1

        # Scheduler
        self.scheduler = scheduler or FairShareScheduler()

        # Tools
        self._tools: dict[str, _Tool] = {}

        # LLM driver (pluggable "CPU")
        self.driver = driver

        # Run-time process stack for re-entrant dispatch
        self._active: list[PCB] = []

    # ---- context management ------------------------------------------------
    def __enter__(self) -> "Kernel":
        return self

    def __exit__(self, *exc) -> None:
        pass

    # ---- bootstrap ---------------------------------------------------------
    def root_cap(self) -> Capability:
        """Return (creating if needed) the root capability.

        Holds 'tool.*', 'mem.*', 'proc.*', 'ipc.*', 'introspect.*',
        'cap.*', 'net.http'. Subset before delegating to a child.
        """
        if self._root_cap is None:
            self._root_cap = self.caps.mint([
                "tool.*", "mem.read", "mem.write", "mem.admin",
                "proc.fork", "proc.join", "proc.kill",
                "ipc.send", "ipc.recv", "ipc.shm",
                "introspect.read",
                "cap.mint", "cap.revoke",
                "net.http",
            ])
        return self._root_cap

    # ---- tools -------------------------------------------------------------
    def register_tool(self, name: str, fn: Callable, *, token_cost: int = 0) -> None:
        self._tools[name] = _Tool(name=name, fn=fn, token_cost=token_cost,
                                   privilege=f"tool.{name}")

    def tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    # ---- processes ---------------------------------------------------------
    def spawn(
        self,
        goal: str,
        *,
        body: Callable[["Kernel", PCB], Any],
        caps: Capability,
        budget_tokens: int = 10_000,
        priority: int = 1,
        parent: PCB | None = None,
    ) -> PCB:
        """Create a new process. Does not yet run it — caller invokes .run_until_done()."""
        pid = self._next_pid; self._next_pid += 1
        pcb = PCB(
            pid=pid,
            parent_pid=parent.pid if parent else None,
            goal=goal,
            caps=caps,
            budget_tokens=budget_tokens,
            priority=priority,
            effective_priority=priority,
            state=ProcState.READY,
            body=body,
        )
        self._procs[pid] = pcb
        self.ipc.register(pid)
        if parent is not None:
            parent.children.add(pid)
            self.scheduler.on_fork(pcb, parent)
        return pcb

    # ---- ISA primitives (called by agent bodies or the SDK) ----------------
    def think(self, pcb: PCB, prompt: str, *, max_tokens: int = 256) -> str:
        """Run one inference step. Charges the budget."""
        if self.driver is None:
            raise RuntimeError("No LLM driver configured")
        # Inject tool registry and /proc context into the prompt
        response, usage = self.driver.think(
            prompt=prompt,
            tools=[{"name": t.name, "privilege": t.privilege}
                   for t in self._tools.values()
                   if pcb.caps.authorizes(t.privilege)],
            max_tokens=max_tokens,
        )
        tokens = usage.get("total_tokens", max_tokens)
        self._charge(pcb, tokens)
        self.trace.record(
            Opcode.THINK, pcb.pid,
            operands={"tokens": tokens, "prompt_len": len(prompt)},
            result=response[:120],
        )
        return response

    def call(self, pcb: PCB, cap: Capability, name: str, *args, **kwargs) -> Any:
        """Invoke a tool or syscall. Capability-checked."""
        # Authorization
        privilege = self._privilege_for(name)
        if not cap.authorizes(privilege):
            self.trace.record(
                Opcode.TRAP, pcb.pid,
                operands={"kind": "cap_violation", "name": name, "privilege": privilege},
            )
            raise CapabilityViolation(
                f"Cap does not authorize '{privilege}' (required for '{name}')"
            )

        # Invoke
        if name in self._tools:
            t = self._tools[name]
            self._charge(pcb, t.token_cost)
            result = t.fn(*args, **kwargs)
        elif name in _SYSCALLS:
            result = _SYSCALLS[name](self, pcb, *args, **kwargs)
        else:
            raise KeyError(f"Unknown tool/syscall: {name}")

        # Record
        self.trace.record(
            Opcode.CALL, pcb.pid,
            operands={"name": name, "args_len": len(args), "kw_keys": list(kwargs.keys())},
            cap_id=cap._handle.id,
            result=_short(result),
        )
        return result

    def load(self, pcb: PCB, h: Handle) -> Any:
        try:
            v = self.mmu.load(h)
        except KeyError:
            raise InvalidHandle(f"{h}")
        self.trace.record(Opcode.LOAD, pcb.pid, operands={"h": h.id, "tier_hint": h.tier_hint})
        return v

    def store(self, pcb: PCB, v: Any, *, tier: str = "L1", flush: bool = False) -> Handle:
        h = self.mmu.store(v, tier=tier, flush=flush)
        self.trace.record(Opcode.STORE, pcb.pid,
                          operands={"h": h.id, "tier": tier, "flush": flush})
        return h

    def fork(self, pcb: PCB, goal: str, body, *,
             caps: Capability, budget_tokens: int, priority: int = 1) -> PCB:
        if budget_tokens > pcb.budget_tokens:
            raise BudgetExhausted(f"Child budget ({budget_tokens}) exceeds parent remaining ({pcb.budget_tokens})")
        child = self.spawn(goal, body=body, caps=caps,
                           budget_tokens=budget_tokens, priority=priority, parent=pcb)
        pcb.budget_tokens -= budget_tokens
        self.trace.record(Opcode.FORK, pcb.pid,
                          operands={"child_pid": child.pid, "goal": goal[:60]})
        return child

    def join(self, pcb: PCB, child: PCB) -> Any:
        self.trace.record(Opcode.JOIN, pcb.pid, operands={"child_pid": child.pid})
        if child.state != ProcState.ZOMBIE:
            self.scheduler.on_join(pcb, child)
            self._run_until_zombie(child)
        return child.exit_value

    def yield_(self, pcb: PCB) -> None:
        self.trace.record(Opcode.YIELD, pcb.pid)

    def exit(self, pcb: PCB, value: Any) -> None:
        pcb.state = ProcState.ZOMBIE
        pcb.exit_value = value
        self.trace.record(Opcode.RET, pcb.pid, result=_short(value))
        self.scheduler.on_exit(pcb)

    # ---- run loop ----------------------------------------------------------
    def run(self, pcb: PCB) -> Any:
        """Run a process to completion and return its exit value."""
        self._run_until_zombie(pcb)
        return pcb.exit_value

    def _run_until_zombie(self, pcb: PCB) -> None:
        # Reentrant: push onto active stack so nested forks work.
        self._active.append(pcb)
        try:
            pcb.state = ProcState.RUNNING
            value = pcb.body(self, pcb)
            if pcb.state != ProcState.ZOMBIE:
                self.exit(pcb, value)
        finally:
            self._active.pop()

    # ---- introspection -----------------------------------------------------
    def pcb(self, pid: int) -> PCB:
        return self._procs[pid]

    def all_pcbs(self) -> list[PCB]:
        return list(self._procs.values())

    # ---- internals ---------------------------------------------------------
    def _charge(self, pcb: PCB, tokens: int) -> None:
        if tokens > pcb.budget_tokens:
            self.trace.record(Opcode.TRAP, pcb.pid,
                              operands={"kind": "budget_exhausted"})
            raise BudgetExhausted(f"pid={pcb.pid} out of tokens")
        pcb.budget_tokens -= tokens
        pcb.tokens_consumed += tokens
        self.scheduler.on_consume(pcb, tokens)

    @staticmethod
    def _privilege_for(name: str) -> str:
        if name in _SYSCALLS:
            return _SYSCALLS_PRIV[name]
        return f"tool.{name}"


# ---------------------------------------------------------------------------
# Syscall implementations (referenced by Kernel.call)
# ---------------------------------------------------------------------------

def _syscall_mem_load(k: Kernel, pcb: PCB, h: Handle) -> Any:
    return k.mmu.load(h)

def _syscall_mem_store(k: Kernel, pcb: PCB, v: Any, tier: str = "L1") -> Handle:
    return k.mmu.store(v, tier=tier)

def _syscall_mem_query(k: Kernel, pcb: PCB, q: str, tier: str = "L3", top_k: int = 5):
    return k.mmu.query(q, tier=tier, top_k=top_k)

def _syscall_msg_send(k: Kernel, pcb: PCB, pid: int, body: Any) -> None:
    k.ipc.send(pcb.pid, pid, body)

def _syscall_msg_recv(k: Kernel, pcb: PCB):
    m = k.ipc.recv(pcb.pid)
    return m.body if m else None

def _syscall_introspect_self(k: Kernel, pcb: PCB):
    return {
        "pid": pcb.pid, "goal": pcb.goal,
        "budget_tokens": pcb.budget_tokens,
        "tokens_consumed": pcb.tokens_consumed,
        "state": pcb.state.name,
        "children": list(pcb.children),
    }

def _syscall_introspect_trace(k: Kernel, pcb: PCB, filter_pid: Optional[int] = None):
    if filter_pid is not None:
        return [i.to_dict() for i in k.trace.for_pid(filter_pid)]
    return [i.to_dict() for i in k.trace]

def _syscall_proc_fs(k: Kernel, pcb: PCB, path: str) -> str:
    from uos.proc.procfs import read as procfs_read
    return procfs_read(k, path)

def _syscall_budget_remaining(k: Kernel, pcb: PCB) -> int:
    return pcb.budget_tokens

def _syscall_time_now(k: Kernel, pcb: PCB) -> float:
    return time.time()


_SYSCALLS = {
    "mem_load":            _syscall_mem_load,
    "mem_store":           _syscall_mem_store,
    "mem_query":           _syscall_mem_query,
    "msg_send":            _syscall_msg_send,
    "msg_recv":            _syscall_msg_recv,
    "introspect_self":     _syscall_introspect_self,
    "introspect_trace":    _syscall_introspect_trace,
    "proc_fs":             _syscall_proc_fs,
    "budget_remaining":    _syscall_budget_remaining,
    "time_now":            _syscall_time_now,
}

_SYSCALLS_PRIV = {
    "mem_load":            "mem.read",
    "mem_store":           "mem.write",
    "mem_query":           "mem.read",
    "msg_send":            "ipc.send",
    "msg_recv":            "ipc.recv",
    "introspect_self":     "introspect.read",   # own PCB always allowed in practice
    "introspect_trace":    "introspect.read",
    "proc_fs":             "introspect.read",
    "budget_remaining":    "introspect.read",
    "time_now":            "introspect.read",
}


def _short(v, n: int = 80) -> str:
    s = repr(v)
    return s if len(s) <= n else s[:n] + "…"
