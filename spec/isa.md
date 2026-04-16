# The Cognitive ISA

The cognitive instruction set is the core execution contract of μOS. Every process is a program in this ISA. Every trace is a sequence of instructions from this set.

## Instructions

### `THINK → instr`
Run one inference step over the current context. The output of the step is interpreted as the next instruction. `THINK` is the only instruction that directly exercises the LLM.

**Cost:** `ctx_len` input tokens + `max_output` output tokens, charged against the process budget.

**Effects:** advances `trace_ptr`, may update L1 via natural-language side-effects recorded by the post-hoc tracer.

### `CALL c f(*args) → value`
Invoke tool or syscall `f` with capability `c` and arguments `args`. The kernel verifies `c` authorizes `f`; a mismatch raises `TRAP cap_violation`.

**Cost:** tool-declared token cost (default 0) + serialization overhead.

**Effects:** side-effects defined by the tool; return value is written to a fresh handle in L1.

### `LOAD h → value`
Dereference memory handle `h`. If the backing tier is not L1, page into L1 via the MMU; may evict cold pages.

**Cost:** resident load is free; non-resident load charges eviction + fetch token costs.

### `STORE v → h`
Write value `v` to memory, returning a handle. The target tier is inferred from annotations (default L1; `ephemeral=False` targets L2; `persistent=True` targets L3).

**Cost:** tier-dependent write cost.

### `FORK g(*args, caps=σ, budget=β) → pid`
Spawn a child process with goal `g`, capability subset `σ ⊆ self.caps`, and budget `β ≤ self.budget_remaining`. The child inherits a fresh L1; L2/L3/L4 are shared with configurable isolation.

**Cost:** PCB allocation (O(1)).

### `JOIN p → value`
Block until process `p` reaches state `ZOMBIE`. Returns its exit value. Triggers priority inheritance: `p`'s effective priority is lifted to the joiner's while `p` runs.

**Cost:** 0 by itself; the joinee's budget is what is charged.

### `YIELD`
Voluntary preemption point. The scheduler may deschedule this process in favor of another ready process.

**Cost:** 0.

### `TRAP k`
Kernel interrupt with kind `k ∈ {timeout, out_of_context, cap_revoked, budget_exhausted, signal}`. Dispatched to the registered handler; default handler transitions to `ZOMBIE` with a descriptive exit value.

**Cost:** handler-dependent.

## Encoding

In memory, an instruction is a tagged record:

```
Instr ::= (opcode, operands, timestamp, pid, cap_id)
```

The trace is a monotonically growing append-only log of `Instr` records with enough metadata to replay.

## Determinism and replay

Replay is exact for all non-`THINK` instructions. `THINK` replay requires either (a) temperature-0 inference with a fixed seed where the driver supports it, or (b) a response cache keyed on `(prompt_hash, params)`. The reference runtime uses (b) by default; drivers that support (a) enable it under `DETERMINISTIC=1`.

## Example program (the quickstart, in ISA)

```
THINK               ; "I need to add 17+25 then double"
CALL add(17,25)     ; → h1 (value 42)
LOAD h1             ; → 42 into L1
THINK               ; "double it → 84"
CALL add(42,42)     ; → h2 (value 84)
LOAD h2
THINK               ; emit final answer
RET 84
```

## Why these eight?

The set is deliberately minimal. Any instruction that can be expressed as a short sequence of the others is not included. `RET` is sugar for exiting with a value via the lifecycle, not an instruction. Metacognitive operations (reflection, replanning) are compositions of `THINK` + `LOAD` from L2/L3. Parallel map is `FORK`/`JOIN` over a collection.

Extensions are possible (a `BARRIER` for fork/join patterns, a `PIPE` for streaming between processes) and may arrive in v0.2 if usage justifies them.
