from win_depends.graph import DependencyGraph


def test_print_tree_outputs(capsys):
    g = DependencyGraph()
    g.add_edge("root.exe", "child1.dll")
    g.add_edge("root.exe", "child2.dll")
    g.add_edge("child1.dll", "leaf.dll")
    # call print_tree and capture output
    g.print_tree(max_depth=5)
    out = capsys.readouterr().out
    assert "root.exe" in out
    assert "child1.dll" in out
    assert "leaf.dll" in out
