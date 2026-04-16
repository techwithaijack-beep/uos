# FAQ

**Is this production-ready?**
No. v0.1 is a reference implementation. Use it to prototype and to read.

**Why Python?**
Readability. A Rust port with equivalent semantics is planned once the model
stabilizes.

**Why call it an OS if it runs in-process?**
Because "OS" names the *abstractions* (processes, memory, syscalls, capabilities),
not the deployment mode. A single-host reference is the shortest path to
establishing those abstractions precisely; distribution is a follow-on concern.

**How is this different from LangGraph / CrewAI / AutoGen?**
Those are libraries over the chat loop. μOS is the *model*: an ISA, an MMU,
a memory hierarchy, a process scheduler, a capability table. You could
re-implement LangGraph on top of μOS, but not vice-versa.

**Is the LLM really a CPU?**
It's an analogy that pays rent. Treating the LLM as a CPU with a
pre-specified instruction set forces explicit answers to questions
(preemption, replay, budget, coherence) that other frameworks answer by
accident. The fact that the LLM is stochastic is one reason the analogy is
*useful*, not a reason it's wrong — it forces us to design replay and
determinism as first-class concerns.

**Does μOS require a specific LLM?**
No. Drivers are ~50 LOC each. Ships with Anthropic, OpenAI, local (OpenAI-compatible
HTTP endpoint), and Mock.

**What about streaming?**
v0.1 uses a single `THINK` response per inference. Streaming drivers that
emit `CALL` instructions mid-stream are a v0.2 concern.

**What's the relationship to Karpathy's "LLM OS" sketch?**
We took the sketch seriously. μOS is one concrete realization; we expect and
welcome others.

**Can I persist the memory tiers across runs?**
Not in v0.1. L2 is in-memory; L3 is in-memory with a deterministic hash; L4
skills are in-memory. Persistence lands in v0.2.

**Is μOS safe?**
The capability model is the answer. It is not *perfect* — a compromised
driver is in the TCB. But it does make prompt-injection robustness a
*property you can check*, rather than a property you hope holds.
