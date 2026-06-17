import types
import win_depends.core as core


class FakeImportItem:
    def __init__(self, name=None, ordinal=None):
        self.name = name
        self.ordinal = ordinal


class FakeImportDesc:
    def __init__(self, dll, imports):
        self.dll = dll
        self.imports = imports


class FakeExportSymbol:
    def __init__(self, name=None, ordinal=None):
        self.name = name
        self.ordinal = ordinal


class FakePE:
    def __init__(self, path, fast_load=True, max_symbol_exports=None):
        self._path = path
        # determine if this is the base file or a dependency by path
        if path.endswith("base.exe"):
            # base imports child.dll with symbol func1
            self.DIRECTORY_ENTRY_IMPORT = [
                FakeImportDesc(b"child.dll", [FakeImportItem(name=b"func1")])
            ]
            self.DIRECTORY_ENTRY_DELAY_IMPORT = []
            self.DIRECTORY_ENTRY_BOUND_IMPORT = []
            self.DIRECTORY_ENTRY_EXPORT = []
        else:
            # dependency exports func1
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
    # create dummy files
    (tmp_path / "base.exe").write_text("x")
    (tmp_path / "child.dll").write_text("x")

    # monkeypatch pefile.PE to use FakePE
    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: dep_path)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    monkeypatch.setattr("pefile.PE", lambda path, fast_load=True, max_symbol_exports=None: FakePE(path, fast_load, max_symbol_exports))

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
    (tmp_path / "base.exe").write_text("x")

    # no local or system dll found
    monkeypatch.setattr(core, "find_local_dll", lambda base, dll: None)
    monkeypatch.setattr(core, "find_system_dll", lambda dll: None)
    monkeypatch.setattr("pefile.PE", lambda path, fast_load=True, max_symbol_exports=None: FakePE(path, fast_load, max_symbol_exports))

    result = core.parse_file_for_dependencies(base_dir, base_file)
    items = list(result)
    assert len(items) == 1
    item = items[0]
    assert item.is_missing is True
    assert item.is_valid is False
