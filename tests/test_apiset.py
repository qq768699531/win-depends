import ctypes
import win_depends.apiset as apiset


def test_contract_detection_and_normalize():
    assert apiset.is_apiset_contract("api-ms-win-core-file-l1-1-0.dll")
    assert apiset.is_apiset_contract("ext-ms-win-foo.dll")
    assert not apiset.is_apiset_contract("kernel32.dll")
    assert (
        apiset._normalize_contract_name("API-MS-Win-Core-File-L1-1-0.DLL")
        == "api-ms-win-core-file-l1-1-0"
    )


def test_lookup_in_schema_prefers_longest_prefix():
    schema = {
        "api-ms-win-core-file": ["kernelbase.dll"],
        "api-ms-win-core-file-l1-1-0": ["kernel32.dll"],
    }
    targets = apiset._lookup_in_schema(schema, "api-ms-win-core-file-l1-1-0")
    assert targets == ["kernel32.dll"]


def test_lookup_in_schema_falls_back_to_same_family_revision():
    schema = {
        "api-ms-win-core-libraryloader-l1-2-3": ["kernelbase.dll"],
        "api-ms-win-core-libraryloader-l1-1-1": ["kernel32.dll"],
    }
    targets = apiset._lookup_in_schema(schema, "api-ms-win-core-libraryloader-l1-2-0")
    assert targets == ["kernelbase.dll"]


def test_lookup_apiset_host_basic(monkeypatch):
    monkeypatch.setattr(
        apiset,
        "_load_apiset_schema_v6",
        lambda: {"api-ms-win-core-libraryloader-l1-2-0": ["kernelbase.dll"]},
    )
    assert (
        apiset.lookup_apiset_host("api-ms-win-core-libraryloader-l1-2-0.dll")
        == "kernelbase.dll"
    )
    assert apiset.lookup_apiset_host("kernel32.dll") is None


def test_resolve_apiset_contract_basic(monkeypatch):
    monkeypatch.setattr(
        apiset,
        "lookup_apiset_host",
        lambda contract_name: "kernelbase.dll" if "libraryloader" in contract_name else None,
    )
    assert apiset.resolve_apiset_contract("api-ms-win-core-libraryloader-l1-2-0.dll") == "kernelbase.dll"
    assert apiset.resolve_apiset_contract("kernel32.dll") is None


def test_load_apiset_schema_v6_from_memory(monkeypatch):
    header_size = ctypes.sizeof(apiset.API_SET_NAMESPACE_V6)
    entry_size = ctypes.sizeof(apiset.API_SET_NAMESPACE_ENTRY_V6)
    value_size = ctypes.sizeof(apiset.API_SET_VALUE_ENTRY_V6)
    buffer = ctypes.create_string_buffer(1024)
    base = ctypes.addressof(buffer)

    contract = "api-ms-win-core-test-l1-1-0"
    contract_bytes = contract.encode("utf-16-le")
    host = "kernelbase.dll"
    host_bytes = host.encode("utf-16-le")

    entry_offset = header_size
    value_offset = entry_offset + entry_size
    contract_offset = value_offset + value_size
    host_offset = contract_offset + len(contract_bytes)

    header = apiset.API_SET_NAMESPACE_V6.from_address(base)
    header.Version = 6
    header.Size = 0
    header.Flags = 0
    header.Count = 1
    header.EntryOffset = entry_offset
    header.HashOffset = 0
    header.HashFactor = 0

    entry = apiset.API_SET_NAMESPACE_ENTRY_V6.from_address(base + entry_offset)
    entry.Flags = 0
    entry.NameOffset = contract_offset
    entry.NameLength = len(contract_bytes)
    entry.HashedLength = len(contract_bytes)
    entry.ValueOffset = value_offset
    entry.ValueCount = 1

    value = apiset.API_SET_VALUE_ENTRY_V6.from_address(base + value_offset)
    value.Flags = 0
    value.NameOffset = 0
    value.NameLength = 0
    value.ValueOffset = host_offset
    value.ValueLength = len(host_bytes)

    ctypes.memmove(base + contract_offset, contract_bytes, len(contract_bytes))
    ctypes.memmove(base + host_offset, host_bytes, len(host_bytes))

    monkeypatch.setattr(apiset, "_get_apiset_map_address", lambda: base)
    apiset._load_apiset_schema_v6.cache_clear()
    parsed = apiset._load_apiset_schema_v6()
    assert parsed[contract] == [host]


def test_load_apiset_schema_v6_rejects_non_v6(monkeypatch):
    buffer = ctypes.create_string_buffer(ctypes.sizeof(apiset.API_SET_NAMESPACE_V6))
    base = ctypes.addressof(buffer)
    header = apiset.API_SET_NAMESPACE_V6.from_address(base)
    header.Version = 4
    monkeypatch.setattr(apiset, "_get_apiset_map_address", lambda: base)
    apiset._load_apiset_schema_v6.cache_clear()
    assert apiset._load_apiset_schema_v6() == {}
