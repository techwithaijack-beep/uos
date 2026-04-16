# Benchmarks

Two kinds of numbers live here:

**External** — well-known agent benchmarks. μOS must not lose on these.

- `gaia/` — GAIA (general assistant)
- `swebench/` — SWE-bench-Verified (code agents)
- `agentbench/` — AgentBench
- `webarena/` — WebArena (web agents, paging-stressed)

**μOS-native** — metrics that the paradigm makes meaningful and prior frameworks cannot report.

- `micro/context_efficiency.py` — useful tokens / total tokens under paging
- `micro/recall_precision.py` — L2/L3/L4 recall at k
- `micro/coord_latency.py` — multi-process IPC round-trip
- `micro/preemption_fidelity.py` — checkpoint/resume outcome equivalence
- `micro/capability_audit.py` — % of sensitive calls mediated

**Head-to-head** — `compare/` contains adapter shims that wrap an OpenClaw-style
tool-use loop, a MemPalace-style memory wrapper, and a Hermes-style multi-agent
runner so they run the same task suite with the same LLM, for apples-to-apples
numbers.

Run:

```
python -m benchmarks.run --suite micro --driver mock
python -m benchmarks.run --suite gaia --driver anthropic --n 20
python -m benchmarks.run --compare --task gaia-lite
```

Results land in `benchmarks/results/<suite>/<timestamp>.json` and are summarized
in README.md after each reproduction.
