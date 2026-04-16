"""IPC tests — message queues and shared regions."""
from uos.kernel.ipc import IPC, Message


def test_queue_send_recv():
    ipc = IPC()
    ipc.register(1); ipc.register(2)
    ipc.send(1, 2, "hi")
    m = ipc.recv(2)
    assert m is not None and m.body == "hi" and m.sender_pid == 1


def test_shm_multi_attach():
    ipc = IPC()
    r = ipc.shm("r1")
    r.attach(1); r.attach(2)
    r.set("x", 42)
    r2 = ipc.shm("r1")
    assert r is r2
    assert r2.get("x") == 42


def test_queue_capacity():
    import pytest
    from uos.kernel.ipc import MessageQueue
    q = MessageQueue(capacity=2)
    q.send(Message(1, 2, "a")); q.send(Message(1, 2, "b"))
    with pytest.raises(OverflowError):
        q.send(Message(1, 2, "c"))
