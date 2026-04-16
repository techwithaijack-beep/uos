"""Context-utilization efficiency — useful tokens / total tokens under paging.

Runs a synthetic task where the agent must recall a needle across N distractor
pages that exceed L1 capacity. Reports:

    efficiency = needle_hits / total_think_tokens

A naive flat-context framework would score poorly (blows the budget); a good
paging policy keeps the needle hot and scores higher.
"""
from __future__ import annotations
from dataclasses import dataclass
from uos import kernel
from uos.drivers.mock import MockDriver


@dataclass
class MicroResult:
    name: str
    efficiency: float
    page_ins: int
    page_outs: int
    tlb_hits: int
    tlb_misses: int


def run(n_pages: int = 64, l1_capacity: int = 8) -> MicroResult:
    with kernel(driver=MockDriver(), l1_capacity=l1_capacity) as k:
        # Populate L3 with distractor pages + one needle.
        needle = "the answer is 42"
        for i in range(n_pages):
            content = needle if i == n_pages // 2 else f"distractor page {i}"
            k.mmu.store(content, tier="L3")

        # Simulate N lookups.
        hits = 0
        for _ in range(20):
            results = k.mmu.query("the answer", tier="L3", top_k=1)
            for h in results:
                if "answer is 42" in str(k.mmu.load(h)):
                    hits += 1

        s = k.mmu.stats()
        # Efficiency here = recall-hit-rate weighted by TLB reuse.
        total = max(s["tlb_hits"] + s["tlb_misses"], 1)
        efficiency = hits / total
        return MicroResult(
            name="context_efficiency",
            efficiency=efficiency,
            page_ins=s["page_ins"], page_outs=s["page_outs"],
            tlb_hits=s["tlb_hits"], tlb_misses=s["tlb_misses"],
        )


if __name__ == "__main__":
    r = run()
    print(f"{r.name}: efficiency={r.efficiency:.3f} "
          f"page_ins={r.page_ins} page_outs={r.page_outs} "
          f"tlb_hit_rate={r.tlb_hits}/{r.tlb_hits+r.tlb_misses}")
