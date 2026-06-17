from win_depends.graph import DependencyGraph


def test_add_edge_and_cycle_detection():
    g = DependencyGraph()
    # create a simple cycle A->B->C->A
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    g.add_edge("C", "A")
    # Ensure nodes created
    assert "A" in g.nodes
    assert "B" in g.nodes
    assert "C" in g.nodes
    # Mark cycles
    g._mark_cycles()
    # At least one edge should be in a cycle
    assert any(edge.in_cycle for edge in g.edges.values())


def test_parents_children_mapping():
    g = DependencyGraph()
    g.add_edge("p1", "c1")
    p = g.get_node("p1")
    c = g.get_node("c1")
    assert c in g.children[p]
    assert p in g.parents[c]
