"""Multi-process coordination latency — IPC round-trip cost."""
from __future__ import annotations
import time
from uos import kernel
from uos.drivers.mock import MockDriver


def run(n: int = 1000) -> dict:
    with kernel(driver=MockDriver()) as k:
        # Register two processes with simple bodies (they never run; we just
        # need PIDs + queues).
        def noop(k, pcb): return None
        p1 = k.spawn("p1", body=noop, caps=k.root_cap(), budget_tokens=1000)
        p2 = k.spawn("p2", body=noop, caps=k.root_cap(), budget_tokens=1000)

        t0 = time.perf_counter_ns()
        for i in range(n):
            k.ipc.send(p1.pid, p2.pid, i)
            k.ipc.recv(p2.pid)
        t1 = time.perf_counter_ns()
        ns_per_rt = (t1 - t0) / n
        return {"n": n, "ns_per_roundtrip": ns_per_rt}


if __name__ == "__main__":
    r = run()
    print(f"coord_latency: {r['ns_per_roundtrip']:.0f} ns / round-trip "
          f"(n={r['n']})")
