# Tutorial — build your first μOS agent

## 1. Install

```bash
pip install -e .          # from a clone
pip install uos           # from PyPI (once published)
```

## 2. A one-shot agent

```python
from uos import Agent, tool
from uos.drivers.mock import MockDriver

@tool
def add(a: int, b: int) -> int:
    return a + b

agent = Agent(
    goal="Add 17 and 25.",
    tools=[add],
    driver=MockDriver(script=['CALL add {"a": 17, "b": 25}', 'DONE 42']),
    budget_tokens=1000,
)
result = agent.run()
print(result.answer)                # 42
print(result.trace.summary())       # ISA-level log
```

Swap the driver for a real model:

```python
from uos.drivers.anthropic import AnthropicDriver
agent.driver = AnthropicDriver(model="claude-opus-4-6")
```

## 3. Multi-process with the kernel API

When you need processes, capabilities, and IPC, drop the Agent facade and
use the kernel directly:

```python
from uos import kernel

with kernel(driver=...) as k:
    k.register_tool("search", my_search_fn)
    researcher_cap = k.root_cap().subset(["tool.search", "mem.read", "mem.write"])

    def researcher(k, pcb):
        hits = k.call(pcb, pcb.caps, "search", query="…")
        return k.mmu.store(hits, tier="L3", flush=True)

    p = k.spawn("research", body=researcher, caps=researcher_cap,
                budget_tokens=5000)
    handle = k.run(p)
```

## 4. Memory tiers

```python
# L1 (default): transient
h = k.mmu.store("hot value")

# L2: session-scoped, survives L1 eviction
h = k.mmu.store("session note", tier="L2")

# L3: persistent-intent, queryable semantically
h = k.mmu.store("a sentence about compilers", tier="L3")
hits = k.mmu.query("compilers", tier="L3", top_k=3)

# L4: procedural skills (see examples/05)
```

## 5. Introspection

```python
print(k.call(pcb, k.root_cap(), "proc_fs", "/proc/stats"))
print(k.call(pcb, k.root_cap(), "proc_fs", f"/proc/{pcb.pid}/calls"))
```

## 6. Debugging a run

The trace IS the debugger. Every decision, budget charge, and capability check
is recorded:

```python
for i in result.trace:
    print(i.opcode.value, i.operands, i.result)
```

## Next

- Read [`WHITEPAPER.md`](../WHITEPAPER.md) for the model.
- Read [`spec/`](../spec/) for formal definitions.
- Read [`uos/kernel/dispatch.py`](../uos/kernel/dispatch.py) — the interpreter, ~230 lines.
