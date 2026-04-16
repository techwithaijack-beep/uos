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

## Why μOS exists

The agent-framework category has crystallized into three shapes:

- **Tool-use libraries** (OpenClaw-style) — helpers on top of a chat loop.
- **Memory subsystems** (MemPalace-style) — a vector DB with a wrapper.
- **Multi-agent runners** (Hermes-style) — a message queue with personas.

Each solves a slice. None offers a **unifying abstraction**. What made Unix durable wasn't any single feature — it was *the model* (processes, files, pipes, syscalls) into which all features fit.

μOS proposes that model for agents.

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
