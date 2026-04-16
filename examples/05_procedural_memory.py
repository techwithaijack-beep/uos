"""Example 05 — Procedural memory lifting.

Shows:
 - A trace with a repeating CALL sequence
 - Lifting the sequence into an L4 Skill
 - Listing skills via /proc/skills
"""
from uos import kernel, tool
from uos.mm.procedural import Skill
from uos.drivers.mock import MockDriver


@tool
def fetch(url: str) -> str:
    return f"[fetched {url}]"


@tool
def summarize(text: str) -> str:
    return f"[summary of {text[:20]}…]"


def run():
    with kernel(driver=MockDriver()) as k:
        k.register_tool("fetch", fetch.fn)
        k.register_tool("summarize", summarize.fn)

        root = k.root_cap()
        cap = root.subset(["tool.fetch", "tool.summarize", "mem.read", "mem.write",
                           "introspect.read"])

        def body(k, pcb):
            # Do the fetch→summarize sequence three times.
            for url in ("a", "b", "c"):
                page = k.call(pcb, pcb.caps, "fetch", url=url)
                k.call(pcb, pcb.caps, "summarize", text=page)
            return "done"

        p = k.spawn("repeat", body=body, caps=cap, budget_tokens=1000)
        k.run(p)

        # Lift the recurring prefix into a skill.
        calls = [c.operands for c in k.trace.calls()]
        skill = k._l4.lift_from_trace(  # type: ignore[attr-defined]
            calls[:2], name="fetch_then_summarize", min_steps=2,
        )
        if skill is not None:
            h = k.mmu.allocate(skill, tier="L4")
            print(f"lifted skill: {skill.name} (steps={len(skill.steps)}) @ {h}")

        print("\n/proc/skills:")
        print(k.call(p, root, "proc_fs", "/proc/skills"))


if __name__ == "__main__":
    run()
