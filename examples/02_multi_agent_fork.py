"""Example 02 — FORK/JOIN: researcher + writer.

Shows:
 - Direct kernel API (bypassing the Agent facade)
 - Two processes with distinct capability subsets
 - Parent-child coordination via JOIN
"""
from uos import kernel, tool
from uos.drivers.mock import MockDriver


@tool
def web_search(query: str) -> str:
    return f"[stub search result for {query!r}: μOS is an agentic operating system]"


@tool
def polish(notes: str) -> str:
    return f"[polished] {notes}"


def run():
    # Three short scripts stitched into one MockDriver; the driver is shared
    # across processes, so ordering reflects THINK call interleaving.
    driver = MockDriver(script=[
        'CALL web_search {"query": "agentic OS"}',
        'DONE μOS introduces a formal kernel model.',
        'CALL polish {"notes": "μOS introduces a formal kernel model."}',
        'DONE [polished] μOS introduces a formal kernel model.',
    ])

    with kernel(driver=driver) as k:
        k.register_tool("web_search", web_search.fn, token_cost=10)
        k.register_tool("polish", polish.fn, token_cost=5)

        root = k.root_cap()
        # Researcher: only search + memory
        researcher_cap = root.subset([
            "tool.web_search", "mem.read", "mem.write", "introspect.read",
        ])
        # Writer: only polish + memory
        writer_cap = root.subset([
            "tool.polish", "mem.read", "mem.write", "introspect.read",
        ])

        # --- Researcher body ---
        def researcher_body(k, pcb):
            from uos.sdk.agent import _make_body  # reuse the ReAct loop
            from uos.sdk.tools import Tool
            body = _make_body(
                "Research agentic operating systems and produce a one-line summary.",
                [Tool("web_search", web_search.fn, token_cost=10)],
                max_steps=4,
            )
            return body(k, pcb)

        # --- Writer body ---
        def writer_body(notes):
            def _body(k, pcb):
                from uos.sdk.agent import _make_body
                from uos.sdk.tools import Tool
                body = _make_body(
                    f"Polish these notes: {notes}",
                    [Tool("polish", polish.fn, token_cost=5)],
                    max_steps=4,
                )
                return body(k, pcb)
            return _body

        # Spawn researcher as child; JOIN returns its exit value.
        researcher = k.spawn("research", body=researcher_body, caps=researcher_cap,
                             budget_tokens=3000)
        notes = k.run(researcher)
        print(f"researcher → {notes!r}")

        # Spawn writer with the notes; capabilities deliberately narrower.
        writer = k.spawn("write", body=writer_body(notes), caps=writer_cap,
                         budget_tokens=2000)
        polished = k.run(writer)
        print(f"writer     → {polished!r}")

        print("\n/proc/stats:")
        print(k.call(researcher, root, "proc_fs", "/proc/stats"))


if __name__ == "__main__":
    run()
