import pytest

from win_depends.graph import DependencyGraph
from win_depends.nodedata import NodeData
from win_depends.edgedata import EdgeData
from win_depends.printer import print_missing


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


@pytest.mark.parametrize("delay_at", [0, 1, 2, None])
def test_missing_delay_propagates_through_chain(delay_at, capsys):
    graph = DependencyGraph()
    paths = ["app.exe", "plugin.dll", "helper.dll", "missing.dll"]
    for index, (parent, child) in enumerate(zip(paths, paths[1:])):
        graph.add_edge(
            parent,
            child,
            EdgeData(is_delay=index == delay_at, is_missing=index == 2),
        )

    print_missing(graph)

    output = capsys.readouterr().out
    if delay_at is None:
        assert "❌ missing.dll" in output
        assert "warning only" not in output
    else:
        assert "⚠️ missing.dll" in output
        assert "delay-loaded; warning only" in output
        assert "❌" not in output
        assert "Required by: helper.dll [DELAY-LOADED]" in output
    assert graph.graph.edges["helper.dll", "missing.dll"]["data"].is_missing


@pytest.mark.parametrize("reverse", [False, True])
def test_missing_shared_file_keeps_required_path(reverse, capsys):
    graph = DependencyGraph()
    edges = [
        ("app.exe", "plugin.dll", EdgeData(is_delay=True)),
        ("app.exe", "required.dll", EdgeData()),
        ("plugin.dll", "missing.dll", EdgeData(is_missing=True)),
        ("required.dll", "missing.dll", EdgeData(is_missing=True)),
    ]
    for parent, child, data in reversed(edges) if reverse else edges:
        graph.add_edge(parent, child, data)

    print_missing(graph)

    output = capsys.readouterr().out
    assert output.count("❌ missing.dll") == 1
    assert "warning only" not in output
    assert "Required by: plugin.dll [DELAY-LOADED]" in output
    assert "Required by: required.dll\n" in output


@pytest.mark.parametrize("reverse", [False, True])
def test_shared_ancestor_with_required_path_is_not_delayed(reverse, capsys):
    graph = DependencyGraph()
    edges = [
        ("app.exe", "plugin.dll", EdgeData(is_delay=True)),
        ("app.exe", "required.dll", EdgeData()),
        ("required.dll", "plugin.dll", EdgeData()),
        ("plugin.dll", "missing.dll", EdgeData(is_missing=True)),
    ]
    for parent, child, data in reversed(edges) if reverse else edges:
        graph.add_edge(parent, child, data)
    print_missing(graph)
    output = capsys.readouterr().out
    assert "❌ missing.dll" in output
    assert "warning only" not in output


def test_delayed_cycle_does_not_become_required(capsys):
    graph = DependencyGraph()
    graph.add_edge("app.exe", "plugin.dll", EdgeData(is_delay=True))
    graph.add_edge("plugin.dll", "helper.dll", EdgeData())
    graph.add_edge("helper.dll", "plugin.dll", EdgeData())
    graph.add_edge("helper.dll", "missing.dll", EdgeData(is_missing=True))
    print_missing(graph)
    output = capsys.readouterr().out
    assert "⚠️ missing.dll" in output
    assert "❌" not in output


def test_explicit_entry_point_in_cycle(capsys):
    graph = DependencyGraph()
    graph.graph.graph["entry_points"] = ["app.exe"]
    graph.add_edge("app.exe", "plugin.dll", EdgeData(is_delay=True))
    graph.add_edge("plugin.dll", "app.exe", EdgeData())
    graph.add_edge("plugin.dll", "missing.dll", EdgeData(is_missing=True))
    print_missing(graph)
    output = capsys.readouterr().out
    assert "⚠️ missing.dll" in output
    assert "❌" not in output


def test_source_cycle_is_conservatively_required(capsys):
    graph = DependencyGraph()
    graph.add_edge("a.dll", "b.dll", EdgeData())
    graph.add_edge("b.dll", "a.dll", EdgeData())
    graph.add_edge("b.dll", "missing.dll", EdgeData(is_missing=True))
    print_missing(graph)
    assert "❌ missing.dll" in capsys.readouterr().out


def test_missing_errors_and_warnings_are_separate(capsys):
    graph = DependencyGraph()
    graph.add_edge("app.exe", "optional.dll", EdgeData(is_missing=True, is_delay=True))
    graph.add_edge("app.exe", "required.dll", EdgeData(is_missing=True))
    print_missing(graph)
    output = capsys.readouterr().out
    assert "❌ required.dll" in output
    assert "⚠️ optional.dll" in output
    assert output.index("❌ required.dll") < output.index("⚠️ optional.dll")


@pytest.mark.parametrize("with_edge", [False, True])
def test_no_missing_dependencies(with_edge, capsys):
    graph = DependencyGraph()
    if with_edge:
        graph.add_edge("app.exe", "plugin.dll", EdgeData(is_delay=True))
    print_missing(graph)
    assert capsys.readouterr().out == "✅ No missing dependencies.\n"
