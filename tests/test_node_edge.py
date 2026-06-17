from win_depends.node import DependencyNode
from win_depends.edge import DependencyEdge


def test_dependency_node_repr_and_flags():
    node = DependencyNode(r"C:\path\to\libA.dll", is_system=True)
    node.is_orphan = True
    node.is_forward = True
    node.forward_to = r"C:\path\to\libB.dll"
    r = repr(node)
    assert "libA.dll" in r
    assert "[SYS]" in r
    assert "(orphan)" in r
    assert "->" in r or "forward" in r


def test_dependency_edge_statuses():
    parent = object()
    child = object()
    e_missing = DependencyEdge(parent, child, is_delay=False, is_missing=True, is_valid=False)
    assert "❌" in "".join(e_missing.status_emojis())
    assert "[MISSING]" in "".join(e_missing.status_flags())
    assert e_missing.status_color() == "red"

    e_invalid = DependencyEdge(parent, child, is_delay=False, is_missing=False, is_valid=False)
    assert "❗" in "".join(e_invalid.status_emojis())
    assert "[INVALID]" in "".join(e_invalid.status_flags())
    assert e_invalid.status_color() == "orange"

    e_delay = DependencyEdge(parent, child, is_delay=True, is_missing=False, is_valid=True)
    assert "⏳" in "".join(e_delay.status_emojis())
    assert "[DELAY]" in "".join(e_delay.status_flags())
    assert e_delay.status_color() == "blue"

    e_cycle = DependencyEdge(parent, child, is_delay=False, is_missing=False, is_valid=True)
    e_cycle.in_cycle = True
    assert "🔁" in "".join(e_cycle.status_emojis())
