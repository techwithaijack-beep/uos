"""MMU tests — allocation, paging, eviction, stats."""
from uos.kernel.mmu import MMU
from uos.mm.working import WorkingMemory
from uos.mm.episodic import EpisodicMemory
from uos.mm.semantic import SemanticMemory
from uos.mm.procedural import ProceduralMemory


def _mmu(l1_capacity=4):
    return MMU(
        tiers={
            "L1": WorkingMemory(),
            "L2": EpisodicMemory(),
            "L3": SemanticMemory(),
            "L4": ProceduralMemory(),
        },
        l1_capacity=l1_capacity,
    )


def test_basic_store_load():
    mmu = _mmu()
    h = mmu.store("hello")
    assert mmu.load(h) == "hello"


def test_l1_evicts_to_l2():
    mmu = _mmu(l1_capacity=3)
    handles = [mmu.store(f"v{i}") for i in range(6)]
    # Oldest values should still be reachable via paging.
    for h in handles:
        assert mmu.load(h).startswith("v")
    s = mmu.stats()
    assert s["page_outs"] > 0
    assert s["page_ins"] > 0


def test_query_semantic():
    mmu = _mmu()
    mmu.store("the study of operating systems", tier="L3")
    mmu.store("the study of compilers", tier="L3")
    hits = mmu.query("operating systems", tier="L3", top_k=1)
    assert len(hits) == 1
    assert "operating systems" in mmu.load(hits[0])


def test_tlb_hit_counter():
    mmu = _mmu()
    h = mmu.store("v")
    mmu.load(h); mmu.load(h); mmu.load(h)
    assert mmu.stats()["tlb_hits"] >= 2
