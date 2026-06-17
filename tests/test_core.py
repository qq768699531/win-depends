import inspect
import win_depends.core as core


def test_build_dependency_graph_callable():
    assert hasattr(core, "build_dependency_graph")
    assert inspect.isfunction(core.build_dependency_graph) or inspect.isbuiltin(core.build_dependency_graph)


def test_get_system_search_paths_returns_list():
    paths = core.get_system_search_paths()
    assert isinstance(paths, list)
