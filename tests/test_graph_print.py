from win_depends.graph import DependencyGraph
from win_depends.edgedata import EdgeData
from win_depends.printer import print_tree


def test_print_tree_outputs(capsys):
    g = DependencyGraph()
    g.add_edge("root.exe", "child1.dll", EdgeData())
    g.add_edge("root.exe", "child2.dll", EdgeData())
    g.add_edge("child1.dll", "leaf.dll", EdgeData())
    # call print_tree and capture output
    print_tree(g, max_depth=5)
    out = capsys.readouterr().out
    assert "root.exe" in out
    assert "child1.dll" in out
    assert "leaf.dll" in out
