"""Example 03 — Context paging.

Shows:
 - Allocating many handles against a tight L1 capacity
 - MMU eviction to L2
 - Paging back in on demand
 - /proc/stats metrics (page_ins, page_outs, tlb_*)
"""
from uos import kernel
from uos.drivers.mock import MockDriver


def run():
    with kernel(driver=MockDriver(), l1_capacity=4) as k:
        # Allocate a blob of "pages" — each STORE goes to L1 with eviction to L2.
        handles = []
        for i in range(12):
            h = k.mmu.store(f"page-{i} content", tier="L1")
            handles.append(h)

        s = k.mmu.stats()
        print(f"after 12 stores, L1={s['l1_resident']}/{s['l1_capacity']} "
              f"page_outs={s['page_outs']}")

        # Touch an old handle — should page IN from L2.
        v = k.mmu.load(handles[0])
        s = k.mmu.stats()
        print(f"after reading page 0 back: value={v!r}, page_ins={s['page_ins']}")

        # Semantic query across L3 — nothing there yet, so 0 hits.
        print(f"semantic query: {k.mmu.query('unknown topic')}")

        # Promote page-7 to L3 and query it semantically.
        k.mmu.store("the study of operating systems", tier="L3")
        k.mmu.store("the study of compilers", tier="L3")
        results = k.mmu.query("operating systems", tier="L3", top_k=2)
        print(f"top hits for 'operating systems': {[k.mmu.load(h) for h in results]}")


if __name__ == "__main__":
    run()
