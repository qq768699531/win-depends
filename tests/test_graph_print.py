from win_depends.graph import DependencyGraph
from win_depends.edgedata import EdgeData
from win_depends.printer import print_tree


def test_print_tree_outputs(capsys):
    g = DependencyGraph()
    g.add_edge("root.exe", "child1.dll", EdgeData())
    g.add_edge("root.exe", "child2.dll", EdgeData())
    g.add_edge("child1.dll", "leaf.dll", EdgeData())
    # call print_tree and capture output
    print_tree(g)
    out = capsys.readouterr().out
    assert "root.exe" in out
    assert "child1.dll" in out
    assert "leaf.dll" in out


def test_print_tree_displays_full_graph_beyond_previous_default(capsys):
    graph = DependencyGraph()
    for depth in range(12):
        graph.add_edge(f"level-{depth}.dll", f"level-{depth + 1}.dll")
    print_tree(graph)
    output = capsys.readouterr().out
    assert "level-12.dll" in output
