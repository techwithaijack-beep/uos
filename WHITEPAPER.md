# μOS: A Kernel for LLM-Native Computing

*The LLM is the CPU. The context window is RAM. Memory is a filesystem. Tools are syscalls. Agents are processes.*

---

## 1. Motivation

Agent frameworks have multiplied. Very few of them have advanced the underlying model of what an agent *is*. Examine any current framework and you find the same core object: a loop that calls an LLM, parses a tool call out of the output, runs the tool, and appends the result back into the prompt. Memory, planning, and multi-agent coordination are layered on top as features, not as consequences of a model.

This is the state Unix faced in 1969. Time-sharing systems existed. They were feature-rich. They were also incoherent: every operation had its own calling convention, every resource its own lifecycle, every abstraction leaked. What Unix contributed was not new features — it was a **model** (processes, files, pipes, syscalls) into which all features fit. Every subsequent operating system either adopted the model or justified its deviations against it.

Agent systems today are pre-Unix. Each framework ships its own calling convention for tools, its own lifecycle for memory, its own improvised scheduler for concurrency, its own ad hoc trust boundary. None of these decisions are *wrong* — they are merely local, and local decisions do not compose.

μOS is the argument that **the operating-systems model applies with very little twisting**, and that taking it seriously yields a cleaner substrate than any of the frameworks it generalizes. This whitepaper names the abstractions, defines them formally, and makes the case — with code — that they compose.

## 2. Thesis

LLM-native computing has its own hardware profile:

- The **CPU** is the LLM. It has a fixed clock (tokens per second), a fixed instruction width (context window), a native instruction (*produce the next token given a prefix*), and a native side-effect (*emit a tool call*).
- The **RAM** is the context window. Bounded. Volatile within a run. Random-access at the token level. Every LLM-native program runs against this RAM.
- The **peripheral bus** is the tool layer. Tool calls cross the userland/kernel boundary; their results are DMA'd back into RAM.
- **Processes** are goals. A process has a PCB, a parent, a budget, a set of capabilities, and a lifecycle.
- **The OS** is what manages all of the above: scheduling, memory, I/O, security, introspection.

Taking the analogy literally is uncomfortable because LLMs are stochastic and context is not really "memory" in the von Neumann sense. The claim of this whitepaper is that the discomfort is productive: it forces explicit answers to questions that agent frameworks currently answer by accident.

## 3. The Cognitive ISA

Every μOS program is a sequence of instructions from a small set. This is the *cognitive ISA*. It is not something the LLM is trained on directly — it is the abstraction the kernel dispatches through, and against which traces are recorded.

```
THINK   — run one inference step over the current context; output is the next instruction
CALL f  — invoke tool or syscall f with capability token c and arguments a
LOAD h  — dereference a memory handle h, paging content into RAM
STORE v — write value v to a memory tier, returning a handle
FORK g  — spawn a child process with goal g; return its pid
JOIN p  — block until process p is ZOMBIE; yield its exit value
YIELD   — voluntary preemption point; scheduler may deschedule
TRAP k  — kernel interrupt (timeout, OOC, cap-revoked, signal)
```

### Why an ISA?

- **Uniformity.** Planning, tool use, memory access, and spawning are not special cases; they are instructions on the same bus.
- **Traceability.** Every run is a program in this ISA. The trace *is* the execution record and supports deterministic replay (modulo inference-layer nondeterminism, which is captured via seeds + response cache).
- **Compositionality.** Higher-level constructs (ReAct, Reflexion, Tree-of-Thoughts, Voyager-style skill growth) are libraries over the ISA, not competing primitives.
- **Accountability.** Every side-effect travels through `CALL` with a capability. Audit reduces to filtering the trace.

### Relationship to existing prompts

A ReAct-style prompt is a sugar on `THINK ; CALL ; LOAD`. A planner-executor pattern is `FORK ; JOIN`. A reflection pass is `THINK` reading from L2 episodic memory via `LOAD`. Treating these as instructions instead of prompt patterns means a single scheduler, a single audit trail, and a single place to attach metrics.

## 4. Memory as a First-Class OS Subsystem

Current frameworks treat "memory" as a plug-in (usually a vector database). This underspecifies both capacity and eviction semantics. μOS promotes memory to a full OS subsystem with (a) a hierarchy, (b) an MMU, and (c) cache-coherence semantics.

### 4.1 The hierarchy

| Tier | Name | Medium | Latency | Lifetime | Analogue |
|------|------|--------|---------|----------|----------|
| L1 | Working | Context tokens | 1× inference | Per-THINK | Registers / L1 cache |
| L2 | Episodic | KV ring buffer | ms | Session | DRAM |
| L3 | Semantic | Vector + graph hybrid | 10–100ms | Persistent | SSD |
| L4 | Procedural | Callable skill code | compile-time | Persistent | Firmware / microcode |

L4 is the distinguishing tier. It holds **skills**: successful action sequences (or prefixes thereof) lifted from the trace and made callable. New processes inherit the skill library. This closes the experience→capability loop with an explicit mechanism rather than a prompt.

### 4.2 The Attention MMU

Every memory reference inside a μOS program is a **handle**, not a literal token payload. The Attention MMU is responsible for resolving handles:

- **Resident?** Return directly.
- **Non-resident?** Page in from the appropriate tier; evict cold pages if the context is full.

Eviction is policy-driven (`LRU`, `importance-weighted`, `learned`). The default ships as importance-weighted LRU where importance is derived from recency, referential density, and task-relevance predicted by a small secondary call. A **TLB analogue** caches recently dereferenced handles to amortize the secondary call.

The effect is that the context window behaves like physical RAM under a good paging scheme: programs speak in logical handles and the kernel keeps the working set hot. This is the generalization MemPalace-style systems stopped short of — not "add a retriever", but "treat the window as RAM and evict properly".

### 4.3 Cache coherence

Writes propagate outward (`L1 → L2 → L3`) on `STORE`, with an explicit `flush` syscall for durability boundaries. Reads hit the highest tier where the handle resolves. Coherence is specified formally in [`spec/semantics.md`](spec/semantics.md) and tested via property tests in [`tests/test_mmu.py`](tests/test_mmu.py).

## 5. Processes and Scheduling

### 5.1 The PCB

Every running agent is a **process**, represented by a Process Control Block:

```
PCB {
  pid, parent_pid,
  goal,                     # natural-language goal (immutable)
  ctx_handle,               # root handle for this process's virtual context
  caps,                     # capability set
  budget_tokens, budget_wall,
  state ∈ {NEW, READY, RUNNING, BLOCKED, ZOMBIE},
  children, exit_value,
  trace_ptr,                # offset into global trace
}
```

### 5.2 Scheduling on token quanta

Wall-clock quanta are the wrong primitive for LLM compute. A `THINK` on a 70B model may take 30× longer than a `THINK` on a 7B model but produce the same number of tokens of useful work. **μOS measures quanta in tokens.** The default scheduler is fair-share across ready processes with priority inheritance on `JOIN` (standard result: prevents priority inversion in parent/child chains).

### 5.3 Preemption

`YIELD` is the voluntary preemption point; the kernel may also preempt at `CALL` returns or `TRAP`. Preemption checkpoints the PCB and its root context handle; resume restores both. Checkpoint/resume is tested for **preemption fidelity**: the fraction of preempted-and-resumed runs that produce outcomes identical to non-preempted runs. This is a first-class μOS metric (see §8).

### 5.4 The scheduler is a policy

The scheduler is a pluggable policy module. The reference impl is heuristic (fair-share + priority inheritance). A learned scheduler — trained via RL on end-task success with token cost as regularizer — is a natural extension and an open research surface.

## 6. Capability-Based Security

Agent frameworks' security model is usually a tool allowlist: the agent sees tools X and Y, so it cannot call Z. This fails under delegation: if the agent calls a sub-agent, does the sub-agent inherit X and Y? Usually the answer is "whatever the wrapping code does", which is neither auditable nor enforceable.

μOS uses **capabilities** (in the OS-theory sense): unforgeable tokens that name both a privilege and an optional restriction. To invoke any tool or syscall, an agent must present a matching capability. Capabilities can be **delegated** (passed to a child process as a subset) and **revoked** (by the parent at any time). Every `CALL` in the trace names the capability that authorized it, giving a precise audit.

This matters for prompt-injection robustness. A malicious document cannot trick an agent into reading the user's email if the agent never held a `mail.read` capability. The capability model makes this property **checkable** instead of aspirational.

See [`spec/capabilities.md`](spec/capabilities.md) for the formal definition and threat model.

## 7. A Self-Improving Substrate

Two μOS-specific mechanisms make the substrate improve with use:

### 7.1 Procedural memory lifting

When a process exits successfully and its trace contains a recurring prefix (or a tool-call sequence the kernel has seen N times), the prefix is lifted into L4 as a callable skill. Future processes can `CALL` the skill directly with a capability, reducing the `THINK` count and stabilizing behavior. This is Voyager's insight generalized beyond a specific domain and given a memory tier.

### 7.2 Learnable scheduler

Because quanta are tokens and the trace records every instruction with its outcome, the scheduler policy is a standard RL problem: given (PCB set, context pressure, budget remaining), pick the next process. This is out-of-scope for v0.1 but the scheduler interface is explicitly designed so a learned policy drops in.

## 8. Evaluation

μOS must be evaluated on both external benchmarks and paradigm-native metrics.

**External:** GAIA (general assistant), SWE-bench-Verified (code agents), AgentBench (broad agentic skills), WebArena (web agents, paging-stressed).

**Paradigm-native:**

- **Context-utilization efficiency** — useful tokens / total tokens under paging
- **Recall precision@k** — retrieval quality across L2–L4
- **Coordination latency** — multi-process IPC round-trip cost
- **Preemption fidelity** — % of checkpoint/resume runs producing identical outcomes
- **Capability audit coverage** — % of dangerous tool calls mediated

**Head-to-head:** thin adapter shims wrap OpenClaw-style, MemPalace-style, and Hermes-style competitors so they run the same task suite against the same LLM. Numbers land in README as they reproduce.

## 9. Related Work

**Agent frameworks.** OpenClaw-style tool-use libraries, MemPalace-style memory systems, Hermes-style multi-agent runners. Each is a component that μOS generalizes into a subsystem.

**Memory-augmented LLMs.** MemGPT introduced the explicit read/write memory hierarchy for conversational agents. μOS generalizes the hierarchy, adds an MMU and paging policies, and extends it beyond conversation.

**Skill learning.** Voyager demonstrated skill growth in Minecraft via code lifting. μOS factors the mechanism out of domain and gives it a memory tier (L4).

**Prompt architectures.** ReAct, Reflexion, Tree-of-Thoughts. Each is a *program* in the Cognitive ISA, not a competing primitive.

**Classical OS theory.** Dennis & Van Horn (1966) on capabilities; Lampson (1968) on scheduling; Denning (1970) on working sets. μOS is straightforward port of this lineage.

**Karpathy's "LLM OS."** Sketched the analogy; μOS is one way to make it precise and code-complete.

## 10. Limitations and Open Problems

1. **Nondeterminism at the instruction level.** `THINK` is stochastic. Replay is only reproducible with either temperature=0 or a response cache. Partial solution today; better with upcoming inference-level seed APIs.
2. **Scheduler learning is costly.** Training requires many full task runs. The interface is ready; data is not.
3. **Semantic tier heterogeneity.** Vector+graph hybrids have many parameter choices. v0.1 ships one; proper ablations pending.
4. **Capability ergonomics.** Capabilities work but are verbose. Better SDK sugar is open.
5. **Not yet production.** Persistence, crash-safety, and multi-tenant isolation are v0.2 concerns.

## 11. Conclusion

Agent frameworks today resemble pre-Unix time-sharing systems: functional but incoherent. μOS proposes — and implements — the missing model. Five abstractions (ISA, MMU, memory hierarchy, process model, capabilities), about 2,500 lines of Python, and a set of metrics the abstractions make meaningful. The goal is not another framework; it is the substrate the next generation of frameworks can sit on without relitigating the basics.

If the model is right, the code is small enough to read in an afternoon and big enough to matter.

## Appendix A — Operational semantics

See [`spec/semantics.md`](spec/semantics.md).

## Appendix B — Syscall table

See [`spec/syscalls.md`](spec/syscalls.md).

## Appendix C — Capability model

See [`spec/capabilities.md`](spec/capabilities.md).
