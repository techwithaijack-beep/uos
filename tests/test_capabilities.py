"""Capability tests — unforgeability, delegation, revocation."""
from uos.kernel.capabilities import CapabilityTable, CapabilityViolation


def test_mint_and_authorize():
    t = CapabilityTable()
    c = t.mint(["tool.search", "mem.read"])
    assert c.authorizes("tool.search")
    assert c.authorizes("mem.read")
    assert not c.authorizes("mem.write")


def test_wildcard():
    t = CapabilityTable()
    c = t.mint(["tool.*"])
    assert c.authorizes("tool.search")
    assert c.authorizes("tool.anything")
    assert not c.authorizes("mem.read")


def test_subset_is_narrower():
    t = CapabilityTable()
    parent = t.mint(["tool.a", "tool.b", "mem.read"])
    child = parent.subset(["tool.a"])
    assert child.authorizes("tool.a")
    assert not child.authorizes("tool.b")
    assert not child.authorizes("mem.read")


def test_subset_cannot_expand():
    t = CapabilityTable()
    parent = t.mint(["tool.a"])
    # Attempt to grant tool.b via subset — should be narrowed to empty.
    child = parent.subset(["tool.b"])
    assert not child.authorizes("tool.b")
    assert not child.authorizes("tool.a")


def test_revocation_propagates():
    t = CapabilityTable()
    parent = t.mint(["tool.*"])
    child = parent.subset(["tool.a"])
    grandchild = child.subset(["tool.a"])
    assert grandchild.authorizes("tool.a")
    t.revoke(parent)
    assert not parent.authorizes("tool.a")
    assert not child.authorizes("tool.a")
    assert not grandchild.authorizes("tool.a")


def test_prefix_scoped_privilege():
    t = CapabilityTable()
    parent = t.mint(["fs.read"])
    # Derive a scoped child
    child = parent.subset(["fs.read:/home/user/docs"])
    assert child.authorizes("fs.read:/home/user/docs")
    assert not child.authorizes("fs.write")
