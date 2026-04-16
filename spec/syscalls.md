# Syscalls

μOS distinguishes between **tools** (user-mode, process-defined) and **syscalls** (kernel-mode, always available). Both are invoked via `CALL` and both require a capability.

## Memory

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `mem_load`  | `mem.read`  | `(handle) → value` | Dereference handle via MMU. |
| `mem_store` | `mem.write` | `(value, tier='L1') → handle` | Write, return handle. |
| `mem_flush` | `mem.write` | `(handle, durable=True) → None` | Propagate to higher tier. |
| `mem_query` | `mem.read`  | `(query, tier, top_k=5) → [handle]` | Tier-specific query (vector for L3, substring for L2). |
| `mem_evict` | `mem.admin` | `(handle) → None` | Manual eviction hint. |

## Processes

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `proc_fork`  | `proc.fork` | `(goal, caps, budget) → pid` | Spawn. See ISA `FORK`. |
| `proc_join`  | `proc.join` | `(pid) → value` | Block on child. |
| `proc_exit`  | always     | `(value) → None` | Transition self to ZOMBIE. |
| `proc_self`  | always     | `() → pid` | Own pid. |
| `proc_kill`  | `proc.kill` | `(pid, signal) → None` | Deliver signal to process. |

## IPC

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `msg_send` | `ipc.send` | `(pid, msg) → None` | Typed message to queue of `pid`. |
| `msg_recv` | `ipc.recv` | `(timeout=None) → msg` | Blocking receive from own queue. |
| `shm_attach` | `ipc.shm` | `(region_id) → handle` | Attach to shared region. |

## Time and budget

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `time_now`       | always | `() → float` | Wall-clock timestamp. |
| `budget_remaining` | always | `() → int` | Tokens left. |
| `sleep`          | always | `(ms) → None` | Yield for at least `ms`. |

## Capabilities

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `cap_mint`     | `cap.mint`   | `(privilege, restriction={}) → cap` | New capability. Root-only. |
| `cap_subset`   | always       | `(cap, privileges) → cap'` | Narrow an existing cap. |
| `cap_revoke`   | `cap.revoke` | `(cap) → None` | Invalidate cap and all descendants. |

## Introspection

| Syscall | Capability | Signature | Semantics |
|--------|------------|-----------|-----------|
| `introspect_self`  | always | `() → PCB` | Read own PCB. |
| `introspect_proc`  | `introspect.read` | `(pid) → PCB` | Read another PCB. |
| `introspect_trace` | `introspect.read` | `(filter={}) → [Instr]` | Slice of the trace. |
| `proc_fs`          | `introspect.read` | `(path) → str` | Procfs read (`/proc/<pid>/...`). |

## Calling convention

```python
result = call(cap, "syscall_name", arg1, arg2, kw=…)
```

All calls are synchronous from the caller's POV. Internally, the kernel may deschedule at `CALL` boundaries. Every call appends an `Instr(CALL, …)` record to the trace.

## Failure modes

A syscall fails by raising a subclass of `SyscallError`. The kernel converts this to `TRAP` unless the process has registered a handler. Common errors:

- `CapabilityViolation` — cap does not authorize this syscall.
- `BudgetExhausted` — not enough tokens remaining.
- `InvalidHandle` — referenced handle does not exist or has been evicted with no backing tier.
- `Timeout` — blocking call exceeded its timeout.
