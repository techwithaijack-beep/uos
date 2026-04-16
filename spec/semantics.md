# Operational Semantics

A small-step semantics for μOS programs. The goal is to give a precise enough rendering that `tests/test_semantics.py` can check conformance of alternative implementations.

## State

```
Σ = ⟨P, M, T, C⟩
  P : pid → PCB           (process table)
  M : Tier × handle → value  (memory)
  T : list of Instr        (trace; append-only)
  C : cap_id → Capability  (cap table)
```

## Process states

```
NEW → READY → RUNNING ⇄ BLOCKED → ZOMBIE
                     ↘   (preempt)
```

Transitions:

- `NEW → READY` on `proc_fork` commit.
- `READY → RUNNING` when scheduler selects.
- `RUNNING → READY` on `YIELD` or quantum exhaustion.
- `RUNNING → BLOCKED` on `JOIN` or blocking `msg_recv`.
- `BLOCKED → READY` when blocker resolves.
- `RUNNING | BLOCKED → ZOMBIE` on `proc_exit` or uncaught `TRAP`.

## Step relation

`Σ, p ⟶ Σ', p'`  means process `p` in state `Σ` takes one step.

### THINK
```
THINK
───────────────────────────────────────────────
Σ, p ⟶ Σ[T ← T ++ [(THINK, …, p.pid, …)]], p[ctx ← ctx']
```
where `ctx'` is obtained by appending the inference output to `ctx`. Budget decremented by tokens consumed.

### CALL
```
cap c authorizes syscall f       evaluate f(args) → v
───────────────────────────────────────────────
Σ, p ⟶ Σ[effects_of_f], p[L1 ← L1 ∪ {h↦v}]
```
with `h` a fresh handle. On `¬ authorizes(c, f)`: `TRAP cap_violation`.

### LOAD
```
M(L1)(h) = v                                (resident)
───────────────────────────────────────────────
Σ, p ⟶ Σ, p                                  (no-op apart from trace)

M(L1)(h) undefined, M(tier≥L2)(h) = v          (page in)
───────────────────────────────────────────────
Σ, p ⟶ Σ[M(L1) ← M(L1) ∪ {h↦v}, evicted ← Φ(p)], p
```
where Φ is the active eviction policy.

### STORE
```
fresh h, tier t
───────────────────────────────────────────────
Σ, p ⟶ Σ[M(t) ← M(t) ∪ {h↦v}], p
```

### FORK / JOIN
```
σ ⊆ p.caps          β ≤ p.budget
───────────────────────────────────────────────
Σ, p ⟶ Σ[P ← P ∪ {(q: NEW, goal, ctx₀, σ, β, …)}], p[children ← children ∪ {q}]

P(q).state = ZOMBIE
───────────────────────────────────────────────
Σ, p(state=BLOCKED on q) ⟶ Σ, p[state ← READY, L1 ∪ {h↦P(q).exit_value}]
```

### YIELD
```
───────────────────────────────────────────────
Σ, p(state=RUNNING) ⟶ Σ, p(state=READY)
```

### TRAP
```
handler H registered for kind k
───────────────────────────────────────────────
Σ, p ⟶ Σ[trace ← trace ++ [(TRAP, k, …)]], H(p)
```

## MMU coherence

For a write `STORE v → h` at tier `L1` with `flush=True`:

```
M(L1)[h] = v, M(L2)[h] = v, M(L3)[h] = ν_encode(v)
```

For a write without `flush`:

```
M(L1)[h] = v, M(L2), M(L3) unchanged
```

A later `mem_flush(h)` propagates. Reads prefer the lowest tier with the handle defined.

## Fair-share scheduling

Let `q_i` be the token quantum consumed by process `i` since its last schedule. A fair-share scheduler selects the ready process with minimal `q_i / priority_i`, breaking ties by arrival time. On `JOIN`, the joinee inherits the joiner's priority until ZOMBIE (priority inheritance; prevents inversion).

## Capability derivation

Capabilities form a tree under `cap_subset`:

```
cap_subset(c, π) = c'
   with  privileges(c') = privileges(c) ∩ π
         parent(c') = c
         valid(c') = valid(c)
```

`cap_revoke(c)` sets `valid(c) = False`, which propagates to all descendants via the parent pointer. Capabilities are unforgeable: the table is kernel-private and capabilities are opaque handles outside the kernel.

## Determinism

A run is **trace-deterministic** if replaying the trace yields the same `Σ_final`. Non-`THINK` instructions are trace-deterministic by construction. `THINK` is trace-deterministic under:

1. **Seeded temperature-0 inference** on a driver that supports it, or
2. **Response cache hit** on `hash(prompt, params)`.

`tests/test_replay.py` checks both modes against mock and real drivers.
