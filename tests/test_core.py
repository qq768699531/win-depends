import inspect
import win_depends.core as core
import win_depends.petool as petool
import win_depends.apiset as apiset


def test_build_dependency_graph_callable():
    assert hasattr(core, "build_dependency_graph")
    assert inspect.isfunction(core.build_dependency_graph) or inspect.isbuiltin(core.build_dependency_graph)


def test_get_system_search_paths_returns_list():
    paths = core.get_system_search_paths()
    assert isinstance(paths, list)


def test_symbol_token_and_forward_normalization():
    assert petool._symbol_token(name=b"FuncA") == "N:FuncA"
    assert petool._symbol_token(ordinal=12) == "O:12"
    assert (
        petool._normalize_forward_target_dll(b"kernelbase.LoadLibraryExW")
        == "kernelbase.dll"
    )


def test_is_apiset_contract_detection():
    assert apiset.is_apiset_contract("api-ms-win-core-file-l1-1-0.dll")
    assert apiset.is_apiset_contract("ext-ms-win-rtcore-ntuser-window-l1-1-0.dll")
    assert not apiset.is_apiset_contract("kernel32.dll")


def test_resolve_dependency_target_local_and_missing(monkeypatch):
    monkeypatch.setattr(core, "find_local_dll", lambda base_dir, name: r"C:\x\foo.dll")
    monkeypatch.setattr(core, "find_system_dll", lambda name: None)
    resolved_local = core._resolve_dependency_target(r"C:\x", "foo.dll")
    assert resolved_local.is_missing is False
    assert resolved_local.dll_path.lower().endswith("foo.dll")

    monkeypatch.setattr(core, "find_local_dll", lambda base_dir, name: None)
    monkeypatch.setattr(core, "find_system_dll", lambda name: None)
    monkeypatch.setattr(core, "resolve_apiset_contract", lambda contract: None)
    resolved_missing = core._resolve_dependency_target(r"C:\x", "bar.dll")
    assert resolved_missing.is_missing is True


def test_resolve_dependency_target_apiset(monkeypatch):
    monkeypatch.setattr(core, "find_local_dll", lambda base_dir, name: None)
    monkeypatch.setattr(
        core,
        "find_system_dll",
        lambda name: r"C:\Windows\System32\kernelbase.dll" if name == "kernelbase.dll" else None,
    )
    monkeypatch.setattr(core, "resolve_apiset_contract", lambda contract: "kernelbase.dll")
    resolved = core._resolve_dependency_target(
        r"C:\x",
        "api-ms-win-core-libraryloader-l1-2-0.dll",
    )
    assert resolved.is_virtual is True
    assert resolved.forward_to == ["kernelbase.dll"]
    assert resolved.is_missing is False
