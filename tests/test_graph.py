import pytest

from win_depends.graph import DependencyGraph
from win_depends.edgedata import EdgeData
from win_depends.nodedata import NodeData
from win_depends.printer import print_tree


def test_add_edge_and_cycle_detection(capsys):
    g = DependencyGraph()
    # create a simple cycle A->B->C->A
    g.add_edge("A", "B", EdgeData())
    g.add_edge("B", "C", EdgeData())
    g.add_edge("C", "A", EdgeData())
    # Ensure nodes created
    assert "A" in g.graph.nodes
    assert "B" in g.graph.nodes
    assert "C" in g.graph.nodes
    # Mark cycles via tree rendering path
    print_tree(g, max_depth=3)
    _ = capsys.readouterr()
    # At least one edge should be in a cycle
    assert any(attrs["data"].in_cycle for _, _, attrs in g.graph.edges(data=True))


def test_parents_children_mapping():
    g = DependencyGraph()
    g.add_edge("p1", "c1", EdgeData())
    assert "c1" in list(g.graph.successors("p1"))
    assert "p1" in list(g.graph.predecessors("c1"))


def test_graph_should_include():
    g = DependencyGraph()
    edge_data = EdgeData(is_missing=False)
    assert g.should_include(edge_data=edge_data, is_system=False, detect_system=False)
    assert not g.should_include(edge_data=edge_data, is_system=True, detect_system=False)
    assert g.should_include(edge_data=edge_data, is_system=True, detect_system=True)
    missing_edge = EdgeData(is_missing=True)
    assert g.should_include(edge_data=missing_edge, is_system=True, detect_system=False)


def test_graph_should_expand():
    g = DependencyGraph()
    assert g.should_expand(node_data=NodeData(is_virtual=False), edge_data=EdgeData(is_missing=False))
    assert not g.should_expand(node_data=NodeData(is_virtual=False), edge_data=EdgeData(is_missing=True))
    assert not g.should_expand(node_data=NodeData(is_virtual=True), edge_data=EdgeData(is_missing=False))


@pytest.mark.parametrize("delays", [(False, True), (True, False), (True, True)])
def test_duplicate_imports_preserve_required_edge(delays):
    graph = DependencyGraph()
    for is_delay in delays:
        graph.add_edge(
            "app.exe", "missing.dll", EdgeData(is_delay=is_delay, is_missing=True)
        )
    data = graph.graph.edges["app.exe", "missing.dll"]["data"]
    assert data.is_delay == all(delays)
    assert data.is_missing
