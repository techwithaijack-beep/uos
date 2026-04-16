# Design principles

μOS is a small codebase with an opinion. These principles decide what gets
merged.

## 1. Abstractions before features.

A feature without a home in the model (ISA / MMU / memory hierarchy / process
model / capabilities) is rejected. If the abstraction is wrong, we refactor
the abstraction, not bolt on a special case.

## 2. Small enough to read.

Every module targets ≤ 400 LOC. The full kernel + memory + process code
targets ≤ 2,500 LOC. Readability is a correctness property: a codebase you
can hold in your head is a codebase you can reason about.

## 3. Plain Python. No magic.

No metaclasses, no heavy DSL, no runtime-generated classes. `grep` must find
every interesting line. A new reader should be able to trace a call from
`Agent.run` all the way through `Kernel.call` to the tool function in one
pass.

## 4. Every decision is testable.

A claim that is not tested is a claim that is wrong. Capability
unforgeability, MMU eviction, trace replay, scheduler fairness — all
property-tested. Bench numbers go in the README only once they reproduce
from `benchmarks/run.py`.

## 5. LLM-agnostic.

The kernel does not know what model it runs. Drivers live at the edge.
`AnthropicDriver`, `OpenAIDriver`, `LocalDriver`, `MockDriver` — all
implement the same 2-line interface.

## 6. No hidden state.

Everything the agent "knows" is either in a handle (introspectable) or in
the trace (replayable). There is no per-framework private dict an agent
can hide things in. If you want persistence, you use the memory tiers
like everyone else.

## 7. Capability-first.

Every side-effect crosses a capability check. New syscalls must declare
their privilege. New tools inherit `tool.<name>`. There is no "internal"
escape hatch.

## 8. Ship the mechanism, not the policy.

Scheduler, eviction policy, skill lifter — all pluggable. The reference
impl picks a reasonable default; the interface is the contract.

## What gets rejected

- "Add a plugin system" — no, we have tools + capabilities.
- "Add retry-on-error to the Agent" — no, write a tool that retries.
- "Make Kernel thread-safe by default" — file an ADR, show the benchmark.
- "Auto-instrument all LLM calls with OpenTelemetry" — the trace *is* the
  telemetry; emit it if you want OTEL.

## What gets fast-tracked

- Bug reports with a failing test.
- Tighter abstractions (removing special cases).
- New drivers for new backends.
- Benchmark adapters that let us measure against prior frameworks honestly.
