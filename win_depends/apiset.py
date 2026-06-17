import ctypes
import os
import re
from functools import lru_cache


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2_0", ctypes.c_void_p),
        ("Reserved2_1", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


class API_SET_NAMESPACE_V6(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_uint32),
        ("Size", ctypes.c_uint32),
        ("Flags", ctypes.c_uint32),
        ("Count", ctypes.c_uint32),
        ("EntryOffset", ctypes.c_uint32),
        ("HashOffset", ctypes.c_uint32),
        ("HashFactor", ctypes.c_uint32),
    ]


class API_SET_NAMESPACE_ENTRY_V6(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("NameOffset", ctypes.c_uint32),
        ("NameLength", ctypes.c_uint32),
        ("HashedLength", ctypes.c_uint32),
        ("ValueOffset", ctypes.c_uint32),
        ("ValueCount", ctypes.c_uint32),
    ]


class API_SET_VALUE_ENTRY_V6(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("NameOffset", ctypes.c_uint32),
        ("NameLength", ctypes.c_uint32),
        ("ValueOffset", ctypes.c_uint32),
        ("ValueLength", ctypes.c_uint32),
    ]


def is_apiset_contract(dll_name):
    name = str(dll_name).lower()
    return name.startswith("api-") or name.startswith("ext-")


@lru_cache(maxsize=512)
def resolve_apiset_contract(contract_name):
    if not is_apiset_contract(contract_name):
        return None
    return lookup_apiset_host(contract_name)


def _normalize_contract_name(contract_dll_name):
    return os.path.splitext(os.path.basename(contract_dll_name.strip().lower()))[0]


def _read_utf16_string(base_addr, offset, length_bytes):
    if length_bytes <= 0:
        return ""
    return ctypes.wstring_at(base_addr + offset, length_bytes // 2)


def _get_apiset_map_address():
    ntdll = ctypes.WinDLL("ntdll")
    peb_addr = 0

    if hasattr(ntdll, "RtlGetCurrentPeb"):
        rtl_get_current_peb = ntdll.RtlGetCurrentPeb
        rtl_get_current_peb.restype = ctypes.c_void_p
        peb_addr = rtl_get_current_peb() or 0

    if not peb_addr:
        nt_query_information_process = ntdll.NtQueryInformationProcess
        nt_query_information_process.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        nt_query_information_process.restype = ctypes.c_long

        pbi = PROCESS_BASIC_INFORMATION()
        return_length = ctypes.c_ulong()
        status = nt_query_information_process(
            ctypes.windll.kernel32.GetCurrentProcess(),
            0,  # ProcessBasicInformation
            ctypes.byref(pbi),
            ctypes.sizeof(pbi),
            ctypes.byref(return_length),
        )
        if status != 0:
            return 0
        peb_addr = pbi.PebBaseAddress

    if not peb_addr:
        return 0

    apiset_offset = 0x68 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x38
    return ctypes.c_void_p.from_address(peb_addr + apiset_offset).value or 0


def _lookup_in_schema(schema_map, contract_name):
    if contract_name in schema_map:
        return schema_map[contract_name]

    best_key = None
    for key in schema_map:
        if contract_name.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key
    if best_key is None:
        family_match = re.match(r"^(.*-l\d+-\d+)-\d+$", contract_name)
        if family_match:
            family = family_match.group(1)
            family_candidates = []
            for key in schema_map:
                key_match = re.match(r"^(.*-l\d+-\d+)-(\d+)$", key)
                if key_match and key_match.group(1) == family:
                    family_candidates.append((int(key_match.group(2)), key))
            if family_candidates:
                _, selected_key = max(family_candidates)
                return schema_map[selected_key]
        return None
    return schema_map[best_key]


@lru_cache(maxsize=1)
def _load_apiset_schema_v6():
    base_addr = _get_apiset_map_address()
    if not base_addr:
        return {}

    header = API_SET_NAMESPACE_V6.from_address(base_addr)
    if header.Version != 6:
        return {}

    result = {}
    entry_size = ctypes.sizeof(API_SET_NAMESPACE_ENTRY_V6)
    value_size = ctypes.sizeof(API_SET_VALUE_ENTRY_V6)
    entry_base = base_addr + header.EntryOffset

    for i in range(header.Count):
        entry = API_SET_NAMESPACE_ENTRY_V6.from_address(entry_base + i * entry_size)
        contract = _read_utf16_string(base_addr, entry.NameOffset, entry.NameLength).lower()
        if not contract:
            continue

        host_list = []
        value_base = base_addr + entry.ValueOffset
        for j in range(entry.ValueCount):
            value = API_SET_VALUE_ENTRY_V6.from_address(value_base + j * value_size)
            host = _read_utf16_string(base_addr, value.ValueOffset, value.ValueLength)
            host = host.strip().lower()
            if host:
                host_list.append(host)

        if host_list:
            result[contract] = host_list

    return result


def lookup_apiset_host(contract_dll_name):
    if not is_apiset_contract(contract_dll_name):
        return None

    schema = _load_apiset_schema_v6()
    if not schema:
        return None

    contract = _normalize_contract_name(contract_dll_name)
    targets = _lookup_in_schema(schema, contract)
    if not targets:
        return None
    return targets[0]
