import pytest
import win_depends.core as core
from win_depends.core import DependencyParseResult, DependencyParseItem


class FakeFuture:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


class FakeExecutor:
    def __init__(self, max_workers=None):
        self._futures = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, func, base_dir, path):
        # call func inline to produce a result
        res = func(base_dir, path)
        f = FakeFuture(res)
        self._futures.append(f)
        return f


def fake_as_completed(futures_list):
    # yield each future present at call time (submit may append more futures but this simple approach is fine for test)
    for f in list(futures_list):
        yield f


class DummyBar:
    def __init__(self, total=0, desc=None, unit=None, dynamic_ncols=True):
        self.total = total

    def refresh(self):
        pass

    def update(self, n=1):
        pass

    def close(self):
        pass


def test__build_dependency_graph_monkeypatched(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    a = str(tmp_path / "A")
    b = str(tmp_path / "B")
    (tmp_path / "A").write_text("x")
    (tmp_path / "B").write_text("x")

    def fake_parse(base_dir_arg, path):
        res = DependencyParseResult()
        if path == a:
            res.add(b, False, True, False, False)
        else:
            # no further deps
            pass
        return res

    monkeypatch.setattr(core, "parse_file_for_dependencies", fake_parse)
    monkeypatch.setattr(core, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(core, "as_completed", fake_as_completed)
    monkeypatch.setattr(core, "tqdm", lambda **kwargs: DummyBar())

    graph = core._build_dependency_graph(
        [a], detect_system=False, verbose=False, threads=2
    )
    # verify nodes and edge added
    assert a in graph.graph.nodes
    assert b in graph.graph.nodes
    # find an edge from a->b
    edges = list(graph.graph.edges)
    assert any(p == a and c == b for p, c in edges)


def test_build_graph_keeps_file_entry_point_only(monkeypatch, tmp_path):
    from win_depends.graph import DependencyGraph

    target = tmp_path / "app.exe"
    target.write_bytes(b"")

    def fake_build(*args):
        return DependencyGraph()

    monkeypatch.setattr(core, "_build_dependency_graph", fake_build)
    file_graph = core.build_dependency_graph(str(target))
    assert file_graph.graph.graph["entry_points"] == [str(target)]
    directory_graph = core.build_dependency_graph(str(tmp_path))
    assert "entry_points" not in directory_graph.graph.graph


def test_build_marks_cycles_without_tree_and_keeps_isolated_nodes(
    monkeypatch, tmp_path
):
    a, b, isolated = (str(tmp_path / name) for name in ("a.dll", "b.dll", "orphan.dll"))

    def fake_parse(base_dir, path):
        result = DependencyParseResult()
        if path == a:
            result.add(b, False, True, False, False)
        if path == b:
            result.add(a, False, True, False, False)
            result.add(b, False, True, False, False)
        return result

    monkeypatch.setattr(core, "parse_file_for_dependencies", fake_parse)
    monkeypatch.setattr(core, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(core, "as_completed", fake_as_completed)
    monkeypatch.setattr(core, "tqdm", lambda **kwargs: DummyBar())
    graph = core._build_dependency_graph([a, isolated])
    assert set(graph.graph) == {a, b, isolated}
    assert graph.node_data(isolated).is_orphan
    assert all(attrs["data"].in_cycle for _, _, attrs in graph.graph.edges(data=True))


def test_empty_graph_does_not_start_executor(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("empty graphs need no executor")

    monkeypatch.setattr(core, "ProcessPoolExecutor", fail)
    assert len(core._build_dependency_graph([]).graph) == 0


@pytest.mark.parametrize("depth", [0, 1, 2, 3, None])
def test_construction_depth_limits_parsing_and_edges(monkeypatch, tmp_path, depth):
    paths = [str(tmp_path / name) for name in ("app.exe", "a.dll", "b.dll", "c.dll")]
    parsed = []

    def fake_parse(base_dir, path):
        parsed.append(path)
        result = DependencyParseResult()
        index = paths.index(path)
        if index < len(paths) - 1:
            result.add(paths[index + 1], False, True, False, False)
        return result

    monkeypatch.setattr(core, "parse_file_for_dependencies", fake_parse)
    monkeypatch.setattr(core, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(core, "as_completed", fake_as_completed)
    monkeypatch.setattr(core, "tqdm", lambda **kwargs: DummyBar())
    graph = core._build_dependency_graph([paths[0]], depth=depth).graph
    expected_nodes = paths if depth is None else paths[: depth + 1]
    assert set(graph) == set(expected_nodes)
    assert list(graph.edges) == list(zip(expected_nodes, expected_nodes[1:]))
    assert parsed == (paths if depth is None else paths[:depth])


def test_depth_uses_shortest_path_despite_completion_order(monkeypatch, tmp_path):
    paths = {name: str(tmp_path / name) for name in ("app", "a", "b", "shared", "leaf")}
    adjacency = {
        "app": ["a", "shared"],
        "a": ["b"],
        "b": ["shared"],
        "shared": ["leaf"],
    }
    parsed = []

    def fake_parse(base_dir, path):
        name = next(name for name, value in paths.items() if value == path)
        parsed.append(name)
        result = DependencyParseResult()
        for child in adjacency.get(name, []):
            result.add(paths[child], False, True, False, False)
        return result

    monkeypatch.setattr(core, "parse_file_for_dependencies", fake_parse)
    monkeypatch.setattr(core, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(core, "as_completed", lambda futures: reversed(futures))
    monkeypatch.setattr(core, "tqdm", lambda **kwargs: DummyBar())
    graph = core._build_dependency_graph([paths["app"]], depth=2).graph
    assert set(graph) == set(paths.values())
    assert graph.has_edge(paths["shared"], paths["leaf"])
    assert set(parsed) == {"app", "a", "shared"}


def test_directory_input_files_start_at_depth_zero(monkeypatch, tmp_path):
    first, second = tmp_path / "a.exe", tmp_path / "b.dll"
    first.write_bytes(b"")
    second.write_bytes(b"")

    def fail(*args):
        pytest.fail("depth zero must not parse dependencies")

    monkeypatch.setattr(core, "parse_file_for_dependencies", fail)
    monkeypatch.setattr(core, "ProcessPoolExecutor", FakeExecutor)
    monkeypatch.setattr(core, "tqdm", lambda **kwargs: DummyBar())
    graph = core.build_dependency_graph(str(tmp_path), depth=0).graph
    assert set(graph) == {str(first), str(second)}
    assert not graph.edges


def test_negative_depth_is_invalid():
    with pytest.raises(ValueError, match="depth must be nonnegative"):
        core._build_dependency_graph([], depth=-1)
