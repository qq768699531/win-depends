import pefile
from functools import lru_cache


def _symbol_token(name=None, ordinal=None):
    if name is not None:
        if isinstance(name, bytes):
            return f"N:{name.decode(errors='ignore')}"
        return f"N:{str(name)}"
    if ordinal is not None:
        try:
            return f"O:{int(ordinal)}"
        except Exception:
            return f"O:{str(ordinal)}"
    return None


def _normalize_forward_target_dll(forwarder):
    if not forwarder:
        return ""
    if isinstance(forwarder, bytes):
        forwarder = forwarder.decode(errors="ignore")
    forwarder = str(forwarder).strip()
    if not forwarder:
        return ""
    dll_part = forwarder.split(".", 1)[0].strip()
    if not dll_part:
        return ""
    if not dll_part.lower().endswith(".dll"):
        dll_part = f"{dll_part}.dll"
    return dll_part.lower()


def _collect_import_tokens(entry):
    tokens = set()
    for item in entry.imports:
        token = None
        if item.name:
            token = _symbol_token(name=item.name)
        elif item.ordinal:
            token = _symbol_token(ordinal=item.ordinal)
        if token:
            tokens.add(token)
    return tokens


@lru_cache(maxsize=512)
def _load_exports_for_file(dll_path):
    pe_dep = pefile.PE(dll_path, fast_load=True, max_symbol_exports=0xF000)
    pe_dep.parse_data_directories(0)
    pe_dep_exports = getattr(pe_dep, "DIRECTORY_ENTRY_EXPORT", [])
    dep_export_set = set()
    dep_forward_map = {}
    for item in getattr(pe_dep_exports, "symbols", []):
        name_key = _symbol_token(name=getattr(item, "name", None))
        ord_key = _symbol_token(ordinal=getattr(item, "ordinal", None))
        if name_key:
            dep_export_set.add(name_key)
        if ord_key:
            dep_export_set.add(ord_key)
        forward_dll = _normalize_forward_target_dll(getattr(item, "forwarder", None))
        if forward_dll:
            if name_key:
                dep_forward_map[name_key] = forward_dll
            if ord_key:
                dep_forward_map[ord_key] = forward_dll
    pe_dep.close()
    return dep_export_set, dep_forward_map
