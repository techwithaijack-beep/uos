"""Example 04 — Capability delegation and revocation.

Shows:
 - Parent has wide caps; child gets a narrow subset
 - Child cannot escape its subset, even via prompt
 - Revocation mid-run causes subsequent calls to TRAP cap_violation
"""
from uos import kernel, tool
from uos.kernel.capabilities import CapabilityViolation
from uos.drivers.mock import MockDriver


@tool
def read_docs(query: str) -> str:
    return f"[doc hit for {query!r}]"


@tool
def send_email(to: str, body: str) -> str:
    return f"(pretended to send to {to})"


def run():
    with kernel(driver=MockDriver()) as k:
        k.register_tool("read_docs", read_docs.fn)
        k.register_tool("send_email", send_email.fn)

        root = k.root_cap()

        # The child gets read_docs but NOT send_email.
        child_cap = root.subset(["tool.read_docs", "mem.read", "introspect.read"])

        def child_body(k, pcb):
            # Authorized call:
            r = k.call(pcb, pcb.caps, "read_docs", query="capabilities")
            print(f"child read_docs → {r}")

            # Unauthorized call:
            try:
                k.call(pcb, pcb.caps, "send_email", to="evil@example.com", body="…")
            except CapabilityViolation as e:
                print(f"child send_email blocked: {e}")

            return "ok"

        child = k.spawn("child", body=child_body, caps=child_cap, budget_tokens=1000)
        k.run(child)

        # Now revoke the child cap and attempt a new process re-using it.
        k.caps.revoke(child_cap)

        def child_body_2(k, pcb):
            try:
                k.call(pcb, pcb.caps, "read_docs", query="post-revoke")
            except CapabilityViolation as e:
                print(f"post-revoke read_docs blocked: {e}")
            return "ok"

        child2 = k.spawn("child2", body=child_body_2, caps=child_cap, budget_tokens=1000)
        k.run(child2)

        # Audit: look at the trace for what was authorized.
        print("\naudit: CALLs by cap id")
        for i in k.trace.calls():
            print(f"  {i.operands['name']:12s} cap={i.cap_id[:8] if i.cap_id else '-'}")


if __name__ == "__main__":
    run()
