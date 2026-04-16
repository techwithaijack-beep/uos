"""Kernel-level integration tests."""
import pytest
from uos.kernel.dispatch import Kernel
from uos.kernel.capabilities import CapabilityViolation
from uos.drivers.mock import MockDriver
from uos.kernel.trace import Opcode


def test_call_authorized():
    k = Kernel(driver=MockDriver())
    k.register_tool("echo", lambda s: s)

    def body(k, pcb):
        return k.call(pcb, pcb.caps, "echo", "hi")

    cap = k.root_cap().subset(["tool.echo"])
    p = k.spawn("test", body=body, caps=cap, budget_tokens=100)
    assert k.run(p) == "hi"


def test_call_unauthorized_traps():
    k = Kernel(driver=MockDriver())
    k.register_tool("secret", lambda: 42)

    def body(k, pcb):
        k.call(pcb, pcb.caps, "secret")  # no tool.secret in caps → violation
        return "should not reach"

    cap = k.root_cap().subset(["tool.other"])
    p = k.spawn("test", body=body, caps=cap, budget_tokens=100)
    with pytest.raises(CapabilityViolation):
        k.run(p)


def test_fork_join():
    k = Kernel(driver=MockDriver())

    def child_body(k, pcb):
        return 42

    def parent_body(k, pcb):
        child = k.fork(pcb, "child", child_body,
                       caps=pcb.caps, budget_tokens=200)
        return k.join(pcb, child)

    cap = k.root_cap()
    p = k.spawn("parent", body=parent_body, caps=cap, budget_tokens=1000)
    assert k.run(p) == 42


def test_trace_records_opcodes():
    k = Kernel(driver=MockDriver(script=["DONE 1"]))
    k.register_tool("noop", lambda: None)

    def body(k, pcb):
        k.think(pcb, "go", max_tokens=10)
        k.call(pcb, pcb.caps, "noop")
        return "done"

    cap = k.root_cap().subset(["tool.noop"])
    p = k.spawn("t", body=body, caps=cap, budget_tokens=200)
    k.run(p)
    ops = [i.opcode for i in k.trace]
    assert Opcode.THINK in ops
    assert Opcode.CALL in ops
    assert Opcode.RET in ops


def test_budget_exhaustion_traps():
    from uos.kernel.dispatch import BudgetExhausted
    # MockDriver consumes tokens_per_step per THINK; set budget below one step.
    k = Kernel(driver=MockDriver(tokens_per_step=100))
    def body(k, pcb):
        k.think(pcb, "go", max_tokens=100)
    p = k.spawn("t", body=body, caps=k.root_cap(), budget_tokens=10)
    with pytest.raises(BudgetExhausted):
        k.run(p)


def test_procfs_stats():
    k = Kernel(driver=MockDriver())
    def body(k, pcb):
        k.mmu.store("hello")
        return "ok"
    p = k.spawn("t", body=body, caps=k.root_cap(), budget_tokens=100)
    k.run(p)
    s = k.call(p, k.root_cap(), "proc_fs", "/proc/stats")
    assert "trace_len=" in s
