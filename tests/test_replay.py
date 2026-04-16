"""Trace replay — a run + a fresh run on the same scripted driver produce
the same non-THINK opcodes in order and the same exit value.
"""
from uos.kernel.dispatch import Kernel
from uos.kernel.trace import Opcode
from uos.drivers.mock import MockDriver


def _run_once(script: list) -> tuple:
    k = Kernel(driver=MockDriver(script=list(script)))
    k.register_tool("add", lambda a, b: a + b)
    cap = k.root_cap().subset(["tool.add", "mem.read", "introspect.read"])

    def body(k, pcb):
        a = k.call(pcb, pcb.caps, "add", a=1, b=2)
        b = k.call(pcb, pcb.caps, "add", a=a, b=a)
        return b

    p = k.spawn("t", body=body, caps=cap, budget_tokens=1000)
    exit_value = k.run(p)
    ops = [i.opcode for i in k.trace]
    calls = [(i.operands["name"], i.result) for i in k.trace.calls()]
    return exit_value, ops, calls


def test_trace_replay_deterministic():
    a = _run_once([])
    b = _run_once([])
    assert a == b
    exit_value, ops, calls = a
    assert exit_value == 6
    assert Opcode.CALL in ops
    assert calls[0] == ("add", "3")
    assert calls[1] == ("add", "6")


def test_trace_total_tokens():
    k = Kernel(driver=MockDriver(script=["a", "b", "c"]))

    def body(k, pcb):
        for _ in range(3):
            k.think(pcb, "go")
        return "ok"

    p = k.spawn("t", body=body, caps=k.root_cap(), budget_tokens=1000)
    k.run(p)
    # Each mock THINK charges tokens_per_step=50 by default → 3×50 = 150.
    assert k.trace.total_tokens() == 150
