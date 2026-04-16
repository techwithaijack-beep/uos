"""/proc introspection — pseudo-filesystem over kernel state.

Supports:
    /proc                        — list of pids
    /proc/<pid>                  — PCB snapshot
    /proc/<pid>/trace            — per-pid trace slice
    /proc/<pid>/calls            — per-pid CALLs
    /proc/stats                  — aggregate trace + mmu stats
    /proc/skills                 — L4 skill registry
"""
from __future__ import annotations


def read(kernel, path: str) -> str:
    path = path.rstrip("/")
    if path in ("", "/proc"):
        return "\n".join(str(p.pid) for p in kernel.all_pcbs())

    if path == "/proc/stats":
        s = kernel.mmu.stats()
        t = kernel.trace
        return (
            f"trace_len={len(t)}\n"
            f"total_think_tokens={t.total_tokens()}\n"
            f"call_count={t.call_count()}\n"
            f"page_ins={s['page_ins']} page_outs={s['page_outs']}\n"
            f"tlb_hits={s['tlb_hits']} tlb_misses={s['tlb_misses']}\n"
            f"l1_resident={s['l1_resident']}/{s['l1_capacity']}\n"
        )

    if path == "/proc/skills":
        return "\n".join(
            f"{s.name} steps={len(s.steps)} conf={s.confidence():.2f}"
            for s in kernel._l4.list_skills()  # type: ignore[attr-defined]
        ) or "(empty)"

    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "proc" and parts[1].isdigit():
        pid = int(parts[1])
        pcb = kernel.pcb(pid)
        if len(parts) == 2:
            snap = pcb.snapshot()
            return "\n".join(f"{k}: {v}" for k, v in snap.items())
        if parts[2] == "trace":
            return "\n".join(
                f"{i.ts:.3f} {i.opcode.value} {i.operands}"
                for i in kernel.trace.for_pid(pid)
            )
        if parts[2] == "calls":
            return "\n".join(
                f"{i.operands.get('name','?')}({i.operands.get('args_len',0)}) → {i.result}"
                for i in kernel.trace.for_pid(pid)
                if i.opcode.value == "CALL"
            )

    raise FileNotFoundError(path)
