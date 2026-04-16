# μOS

**A kernel for LLM-native computing.**

> The LLM is the CPU.
> The context window is RAM.
> Memory is a filesystem.
> Tools are syscalls.
> Agents are processes.
>
> Everything else follows.

μOS (pronounced *microOS*) is a minimal reference implementation of an **agentic operating system** — not another agent framework, but the substrate an agent framework should sit on. ~2,500 lines of Python. Readable in an afternoon. Serious enough to cite.

---

## The Problem

If you've built an agent in the last year you have hit all of these:

- **Your context explodes and you have no idea what's in it.** Summarization is ad-hoc, retrieval is bolted on, there's no answer to *"what's resident, what got evicted, and why?"*
  → μOS: **Attention MMU + memory hierarchy.**

- **Spawning sub-agents is a rewrite each time.** Async? Queues? Graphs? Every framework picks one. None of them compose.
  → μOS: **a process model with real PCBs, FORK/JOIN, IPC.**

- **"Tool access" is a list, not a policy.** If a sub-agent inherits tools A, B, C — can it delegate them? Revoke them? Audit them? In most frameworks: whatever the wrapper code does.
  → μOS: **unforgeable capabilities.** Delegate a subset. Revoke at any time.

- **Debugging is archaeology.** Your agent made eight calls, produced the wrong answer, and you have… print statements. No replay, no trace, no determinism.
  → μOS: **every run is a program in a formal ISA.** The trace IS the debugger.

- **"Memory" is a vector DB.** That's not memory — that's a retrieval side channel. No tiering, no coherence, no eviction semantics, no way to promote skills.
  → μOS: **L1 working / L2 episodic / L3 semantic / L4 procedural**, with cache-coherence rules and skill lifting.

None of these are novel complaints. What's novel is that μOS answers all five with *the same model* — not five separate libraries.

## Why μOS exists

The agent-framework category has crystallized into three shapes — tool-use libraries (OpenClaw-style), memory subsystems (MemPalace-style), multi-agent runners (Hermes-style). Each solves a slice. None offers a **unifying abstraction**.

What made Unix durable wasn't any single feature — it was *the model* (processes, files, pipes, syscalls) into which all features fit. μOS proposes that model for agents.

## The five abstractions

| # | Abstraction | What it replaces |
|---|-------------|-------------------|
| 1 | **Cognitive ISA** — `THINK`, `CALL`, `LOAD`/`STORE`, `FORK`/`JOIN`, `YIELD`, `TRAP` | Ad-hoc agent loops |
| 2 | **Attention MMU** — virtual memory over the context window, with paging | Flat context stuffing + RAG spaghetti |
| 3 | **Memory hierarchy** — L1 working / L2 episodic / L3 semantic / L4 procedural | One vector DB for everything |
| 4 | **Process model** — real PCBs, preemptive scheduling on token quanta | Async chat loops |
| 5 | **Capability-based security** — unforgeable tokens, delegation, revocation | Tool allowlists |

Each has a formal spec in [`spec/`](spec/) and a ≤400-line implementation in [`uos/`](uos/).

## 60-second quickstart

```bash
pip install uos[anthropic]
```

```python
from uos import Agent, tool

@tool
def add(a: int, b: int) -> int:
    return a + b

agent = Agent(
    goal="Compute 17 + 25, then double it.",
    tools=[add],
    driver="anthropic:claude-sonnet-4-6",
    budget_tokens=4000,
)

result = agent.run()
print(result.answer)          # "84"
print(result.trace.summary()) # ISA-level trace: THINK, CALL add, THINK, CALL add, THINK → RET
```

Multi-agent with `FORK`/`JOIN`:

```python
from uos import kernel

def researcher(topic): ...
def writer(notes): ...

with kernel() as k:
    r = k.fork(researcher, args=("LLM operating systems",), budget_tokens=5000)
    notes = k.join(r)
    w = k.fork(writer, args=(notes,), budget_tokens=3000, caps=r.caps.subset("fs.read"))
    print(k.join(w))
```

## Comparison

|  | OpenClaw-style | MemPalace-style | Hermes-style | **μOS** |
|--|--|--|--|--|
| Tool use | ✓ | — | ✓ | ✓ (capability-gated syscalls) |
| Memory | flat | hierarchical | session | **hierarchy + MMU + paging** |
| Concurrency | — | — | queue | **preemptive scheduler (token quanta)** |
| Security | allowlist | — | — | **capability tokens** |
| Formal semantics | — | — | — | **ISA + operational semantics** |
| Deterministic replay | — | — | — | **trace → replay** |
| Self-improvement | — | — | — | **procedural memory lifting** |
| LOC to understand | large | medium | medium | **~2,500** |

Benchmark numbers live in [`benchmarks/`](benchmarks/) and will land in the README as they reproduce.

## Read in this order

1. **[WHITEPAPER.md](WHITEPAPER.md)** — the design argument (start here).
2. **[`spec/isa.md`](spec/isa.md)** — the cognitive instruction set.
3. **[`spec/syscalls.md`](spec/syscalls.md)** — the OS/userland boundary.
4. **[`uos/kernel/dispatch.py`](uos/kernel/dispatch.py)** — the 200-line interpreter everything runs through.
5. **[`examples/`](examples/)** — one example per abstraction.

## Status

`v0.1` — reference implementation. The kernel runs. Examples execute against a mock driver (zero API cost) and against real Anthropic/OpenAI backends. Benchmark harness is scaffolded; numbers land as each suite reproduces. Breaking changes possible until `v0.2`.

## Design principles

- **Small enough to read.** If a subsystem exceeds 400 LOC, we redesign it.
- **Abstractions before features.** Features without a home in the model don't ship.
- **Plain Python.** No metaclass magic. `grep` should find every interesting line.
- **Every decision is testable.** ISA trace equivalence, capability unforgeability, paging correctness — all in `tests/`.
- **LLM-agnostic core.** The kernel does not know what model it is running.

## Non-goals

- Production-ready hosted runtime.
- A proprietary tool marketplace.
- Training LLMs. μOS is a *substrate*; bring your own model.

## Contributing

Open to contributions that sharpen the model. Tickets that add features without strengthening the abstraction will be closed with love. See [`docs/design_principles.md`](docs/design_principles.md).

## License

MIT. See [LICENSE](LICENSE).

## Citation

```bibtex
@misc{uos2026,
  title  = {{μOS}: A Kernel for {LLM}-Native Computing},
  author = {The {μOS} Authors},
  year   = {2026},
  url    = {https://github.com/your-org/uos},
}
```
