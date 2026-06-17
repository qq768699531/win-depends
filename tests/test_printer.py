from win_depends.graph import DependencyGraph
from win_depends.nodedata import NodeData
from win_depends.edgedata import EdgeData


def test_print_orphan(capsys):
    g = DependencyGraph()
    n = NodeData(is_orphan=True)
    g.add_node(r"C:\libs\orphan.dll", n)
    from win_depends.printer import print_orphan

    print_orphan(g)
    captured = capsys.readouterr()
    assert "Orphan DLLs" in captured.out
    assert "orphan.dll" in captured.out


def test_print_missing_and_parents(capsys):
    g = DependencyGraph()
    g.add_node("parent.exe", NodeData())
    g.add_node("missing.dll", NodeData(is_forward=True, forward_to=["kernel32.Sleep"]))
    g.add_edge("parent.exe", "missing.dll", EdgeData(is_missing=True, is_valid=False))
    from win_depends.printer import print_missing

    print_missing(g)
    out = capsys.readouterr().out
    assert "Missing dependencies" in out or "No missing dependencies" not in out
    assert "missing.dll" in out
    assert "FORWARD -> kernel32.Sleep" in out
    assert "Required by" in out or "parent.exe" in out


def test_print_invalid(capsys):
    g = DependencyGraph()
    g.add_node("parent.exe", NodeData())
    g.add_node("bad.dll", NodeData(is_forward=True, forward_to=["ntdll.RtlFoo"]))
    g.add_edge("parent.exe", "bad.dll", EdgeData(is_missing=False, is_valid=False))
    from win_depends.printer import print_invalid

    print_invalid(g)
    out = capsys.readouterr().out
    assert "Invalid files" in out or "No invalid files" not in out
    assert "parent.exe" in out
    assert "bad.dll" in out
    assert "FORWARD -> ntdll.RtlFoo" in out
