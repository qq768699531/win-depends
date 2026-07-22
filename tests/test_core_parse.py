import types
import win_depends.core as core


def _write_dummy_files(tmp_path, *file_names):
    for file_name in file_names:
        (tmp_path / file_name).write_text("x")


def _patch_pe_constructor(monkeypatch, pe_ctor):
    monkeypatch.setattr("pefile.PE", pe_ctor)


class FakeImportItem:
    def __init__(self, name=None, ordinal=None, hint=None):
        self.name = name
        self.ordinal = ordinal
        self.hint = hint


class FakeImportDesc:
    def __init__(self, dll, imports):
        self.dll = dll
        self.imports = imports


class FakeExportSymbol:
    def __init__(self, name=None, ordinal=None, forwarder=None):
        self.name = name
        self.ordinal = ordinal
        self.forwarder = forwarder


class FakePE:
    def __init__(self, path, fast_load=True, max_symbol_exports=None):
        self._path = path
        # 按路径区分：基础文件或被依赖文件。
        if path.endswith("base.exe"):
            # 基础文件导入 child.dll 的 func1。
            self.DIRECTORY_ENTRY_IMPORT = [
                FakeImportDesc(b"child.dll", [FakeImportItem(name=b"func1")])
            ]
            self.DIRECTORY_ENTRY_DELAY_IMPORT = []
            self.DIRECTORY_ENTRY_BOUND_IMPORT = []
            self.DIRECTORY_ENTRY_EXPORT = []
        else:
            # 依赖文件导出 func1。
            self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(symbols=[FakeExportSymbol(name=b"func1")])
            self.DIRECTORY_ENTRY_IMPORT = []
            self.DIRECTORY_ENTRY_DELAY_IMPORT = []
            self.DIRECTORY_ENTRY_BOUND_IMPORT = []

    def parse_data_directories(self, *_):
        return

    def close(self):
        return


def test_parse_file_for_dependencies_valid(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "child.dll")
    _write_dummy_files(tmp_path, "base.exe", "child.dll")

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(
        monkeypatch,
        lambda path, fast_load=True, max_symbol_exports=None: FakePE(
            path, fast_load, max_symbol_exports
        ),
    )

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    item = items[0]
    assert item.dll_path == dep_path
    assert item.is_missing is False
    assert item.is_valid is True


def test_parse_file_for_dependencies_missing(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    _write_dummy_files(tmp_path, "base.exe")

    # 本地和系统目录都找不到依赖。
    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: None)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(
        monkeypatch,
        lambda path, fast_load=True, max_symbol_exports=None: FakePE(
            path, fast_load, max_symbol_exports
        ),
    )

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    item = items[0]
    assert item.is_missing is True
    assert item.is_valid is False


def test_parse_file_for_dependencies_forwarded(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "child.dll")
    _write_dummy_files(tmp_path, "base.exe", "child.dll")

    class FakePEForward:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_IMPORT = [
                    FakeImportDesc(b"child.dll", [FakeImportItem(name=b"func1")])
                ]
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []
                self.DIRECTORY_ENTRY_EXPORT = []
            else:
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[
                        FakeExportSymbol(
                            name=b"func1",
                            forwarder=b"real_target.dll.func1",
                        )
                    ]
                )
                self.DIRECTORY_ENTRY_IMPORT = []
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(
        monkeypatch,
        lambda path, fast_load=True, max_symbol_exports=None: FakePEForward(
            path, fast_load, max_symbol_exports
        ),
    )

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    item = items[0]
    assert item.is_missing is False
    assert item.is_valid is True
    assert item.is_forward is True
    assert item.forward_to == ["real_target.dll"]


def test_parse_file_for_dependencies_apiset_resolved(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    host_path = str(tmp_path / "kernelbase.dll")
    _write_dummy_files(tmp_path, "base.exe", "kernelbase.dll")

    class FakePEApiSet:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_IMPORT = [
                    FakeImportDesc(
                        b"api-ms-win-core-libraryloader-l1-2-0.dll",
                        [FakeImportItem(name=b"LoadLibraryExW")],
                    )
                ]
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []
                self.DIRECTORY_ENTRY_EXPORT = []
            else:
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[FakeExportSymbol(name=b"LoadLibraryExW")]
                )
                self.DIRECTORY_ENTRY_IMPORT = []
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: None)
    monkeypatch.setattr(
        core,
        "find_system_dll",
        lambda dll: host_path if dll == "kernelbase.dll" else None,
    )
    monkeypatch.setattr(
        core,
        "resolve_apiset_contract",
        lambda contract_name: "kernelbase.dll",
    )
    _patch_pe_constructor(
        monkeypatch,
        lambda path, fast_load=True, max_symbol_exports=None: FakePEApiSet(
            path, fast_load, max_symbol_exports
        ),
    )

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    item = items[0]
    assert item.dll_path == "api-ms-win-core-libraryloader-l1-2-0.dll"
    assert item.is_missing is False
    assert item.is_valid is True
    assert item.is_forward is True
    assert item.forward_to == ["kernelbase.dll"]
    assert item.is_virtual is True


def test_parse_file_for_dependencies_parses_delay_directory(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "delay.dll")
    _write_dummy_files(tmp_path, "base.exe", "delay.dll")
    called = {"directories": None}

    class FakePEDelaySensitive:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            self._path = path
            self.DIRECTORY_ENTRY_IMPORT = []
            self.DIRECTORY_ENTRY_BOUND_IMPORT = []
            self.DIRECTORY_ENTRY_DELAY_IMPORT = []
            self.DIRECTORY_ENTRY_EXPORT = []
            if not path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[FakeExportSymbol(name=b"DelayFunc")]
                )

        def parse_data_directories(self, directories=None, *_):
            if self._path.endswith("base.exe"):
                called["directories"] = directories
            if self._path.endswith("base.exe") and directories and 13 in directories:
                self.DIRECTORY_ENTRY_DELAY_IMPORT = [
                    FakeImportDesc(b"delay.dll", [FakeImportItem(name=b"DelayFunc")])
                ]

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(
        monkeypatch,
        lambda path, fast_load=True, max_symbol_exports=None: FakePEDelaySensitive(
            path, fast_load, max_symbol_exports
        ),
    )

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    assert items[0].dll_path == dep_path
    assert items[0].is_delay is True
    assert 13 in called["directories"]


def test_parse_file_for_dependencies_missing_delay_keeps_delay_flag(
    monkeypatch, tmp_path
):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    _write_dummy_files(tmp_path, "base.exe")

    class FakePEDelayMissing:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            self.DIRECTORY_ENTRY_IMPORT = []
            self.DIRECTORY_ENTRY_BOUND_IMPORT = []
            self.DIRECTORY_ENTRY_DELAY_IMPORT = []
            self.DIRECTORY_ENTRY_EXPORT = []
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_DELAY_IMPORT = [
                    FakeImportDesc(b"missing_delay.dll", [FakeImportItem(name=b"DelayFunc")])
                ]

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: None)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(monkeypatch, FakePEDelayMissing)

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    assert items[0].is_missing is True
    assert items[0].is_delay is True


def test_parse_file_for_dependencies_name_mismatch_not_hidden_by_hint(
    monkeypatch, tmp_path
):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "UPKoios.dll")
    _write_dummy_files(tmp_path, "base.exe", "UPKoios.dll")

    class FakePENamePriority:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_IMPORT = [
                    FakeImportDesc(
                        b"UPKoios.dll",
                        [FakeImportItem(name=b"NeedByName", ordinal=None, hint=1)],
                    )
                ]
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []
                self.DIRECTORY_ENTRY_EXPORT = []
            else:
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[FakeExportSymbol(name=b"DifferentName", ordinal=1)]
                )
                self.DIRECTORY_ENTRY_IMPORT = []
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(monkeypatch, FakePENamePriority)

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    assert items[0].is_missing is False
    assert items[0].is_valid is False


def test_parse_file_for_dependencies_name_can_fallback_to_hint_when_ordinal_only_target(
    monkeypatch, tmp_path
):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "UP3D.ScannerDeviceController.dll")
    _write_dummy_files(tmp_path, "base.exe", "UP3D.ScannerDeviceController.dll")

    class FakePEOrdinalOnlyTarget:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_IMPORT = [
                    FakeImportDesc(
                        b"UP3D.ScannerDeviceController.dll",
                        [FakeImportItem(name=b"InitializeController", ordinal=None, hint=17)],
                    )
                ]
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []
                self.DIRECTORY_ENTRY_EXPORT = []
            else:
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[FakeExportSymbol(name=None, ordinal=17)]
                )
                self.DIRECTORY_ENTRY_IMPORT = []
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(monkeypatch, FakePEOrdinalOnlyTarget)

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    assert items[0].is_missing is False
    assert items[0].is_valid is True


def test_parse_file_for_dependencies_no_symbol_info_is_invalid(monkeypatch, tmp_path):
    base_dir = str(tmp_path)
    base_file = str(tmp_path / "base.exe")
    dep_path = str(tmp_path / "child.dll")
    _write_dummy_files(tmp_path, "base.exe", "child.dll")

    class FakePENoSymbolInfo:
        def __init__(self, path, fast_load=True, max_symbol_exports=None):
            if path.endswith("base.exe"):
                self.DIRECTORY_ENTRY_IMPORT = [
                    FakeImportDesc(b"child.dll", [FakeImportItem(name=None, ordinal=None)])
                ]
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []
                self.DIRECTORY_ENTRY_EXPORT = []
            else:
                self.DIRECTORY_ENTRY_EXPORT = types.SimpleNamespace(
                    symbols=[FakeExportSymbol(name=b"Any", ordinal=1)]
                )
                self.DIRECTORY_ENTRY_IMPORT = []
                self.DIRECTORY_ENTRY_DELAY_IMPORT = []
                self.DIRECTORY_ENTRY_BOUND_IMPORT = []

        def parse_data_directories(self, *_):
            return

        def close(self):
            return

    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    _patch_pe_constructor(monkeypatch, FakePENoSymbolInfo)

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    assert items[0].is_missing is False
    assert items[0].is_valid is False
