# Architecture

μOS is a single-process, single-machine reference implementation. One kernel
instance, many cognitive processes, all sharing a memory hierarchy and a
capability table.

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                          User program                            │
 │                                                                  │
 │     Agent(goal, tools, driver)        k = kernel()                │
 │            │                                │                     │
 └────────────┼────────────────────────────────┼─────────────────────┘
              │                                │
              ▼                                ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │                            Kernel                                │
 │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
 │  │  Dispatch   │  │  Scheduler  │  │   Trace     │  │   IPC    │ │
 │  │ (ISA)       │  │ (fair share)│  │ (append-log)│  │ (queues) │ │
 │  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └──────────┘ │
 │         │                │                                        │
 │  ┌──────▼──────┐  ┌──────▼──────┐                                │
 │  │ Capabilities│  │   MMU +     │                                │
 │  │ (ocap)      │  │ Memory Tiers│                                │
 │  └─────────────┘  └─────┬───────┘                                │
 └────────────────────────┼────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  ┌──────────┐      ┌──────────┐      ┌──────────┐
  │    L1    │─────▶│    L2    │─────▶│    L3    │   L4 (skills)
  │ Working  │      │ Episodic │      │ Semantic │
  └──────────┘      └──────────┘      └──────────┘
```

## Dispatch cycle

1. Scheduler picks a READY PCB.
2. Kernel dispatches the process body; body makes kernel calls.
3. Each call (`think`, `call`, `load`, `store`, `fork`, `join`) records an
   `Instr` in the trace, charges the budget, and returns.
4. Body returns an exit value; kernel transitions PCB → ZOMBIE.

## Files, at a glance

| Path | LOC (approx) | Role |
|------|---------------|------|
| `uos/kernel/dispatch.py` | 230 | ISA interpreter; owns PCBs, tools, trace. |
| `uos/kernel/mmu.py` | 180 | Virtual memory over the hierarchy; paging; TLB. |
| `uos/kernel/capabilities.py` | 120 | Ocap table; mint/subset/revoke. |
| `uos/kernel/scheduler.py` | 60 | Fair-share scheduling over token quanta. |
| `uos/kernel/trace.py` | 110 | Append-only trace; filters; replay. |
| `uos/kernel/ipc.py` | 80 | Queues + shared regions. |
| `uos/mm/{working,episodic,semantic,procedural}.py` | 250 | Four memory tiers. |
| `uos/proc/{pcb,lifecycle,procfs}.py` | 120 | Process model + /proc. |
| `uos/sdk/{agent,tools}.py` | 150 | Ergonomic facade. |
| `uos/drivers/*.py` | 150 | LLM backends. |

Total kernel + mm + proc ≈ **1,300 LOC**. Under budget.

## Extension points

- **Custom scheduler** — implement `SchedulerPolicy` and pass `scheduler=` to `Kernel`.
- **Custom eviction policy** — subclass the MMU's policy interface.
- **Custom driver** — implement `think(prompt, tools, max_tokens) → (text, usage)`.
- **Custom memory tier** — implement the tier protocol (`read`, `write`, `has`, `evict`, `working_set`, optional `query`) and register it with the MMU.
