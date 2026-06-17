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

    graph = core._build_dependency_graph([a], detect_system=False, verbose=False, threads=2)
    # verify nodes and edge added
    assert a in graph.graph.nodes
    assert b in graph.graph.nodes
    # find an edge from a->b
    edges = list(graph.graph.edges)
    assert any(p == a and c == b for p, c in edges)
