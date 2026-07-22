import os
import pefile
from tqdm import tqdm
from .apiset import resolve_apiset_contract, is_apiset_contract
from .graph import DependencyGraph
from .edgedata import EdgeData
from .petool import _collect_import_requirements, _load_exports_for_file
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from dataclasses import dataclass, field


def _import_directory_ids():
    directory_entry = getattr(pefile, "DIRECTORY_ENTRY", {})
    return [
        directory_entry.get("IMAGE_DIRECTORY_ENTRY_IMPORT", 1),
        directory_entry.get("IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT", 11),
        directory_entry.get("IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT", 13),
    ]


def _match_ordinals(ordinal_tokens, resolvable_exports):
    return {candidate for candidate in ordinal_tokens if candidate in resolvable_exports}


def _collect_forward_candidates(candidates, dep_forward_map):
    return {candidate for candidate in candidates if candidate in dep_forward_map}


def _evaluate_requirement(
    requirement, resolvable_exports, dep_forward_map, has_named_exports
):
    name_token = requirement.get("name")
    ordinal_tokens = requirement.get("ordinals", set())

    if name_token:
        if name_token in resolvable_exports:
            return True, _collect_forward_candidates({name_token}, dep_forward_map)
        # 目标 DLL 存在命名导出时，按名称严格匹配。
        if has_named_exports:
            return False, set()
        # 目标 DLL 仅 ordinal 导出时，允许 ordinal/hint 兜底。
        matched_ordinals = _match_ordinals(ordinal_tokens, resolvable_exports)
        if not matched_ordinals:
            return False, set()
        return True, _collect_forward_candidates(matched_ordinals, dep_forward_map)

    if not ordinal_tokens:
        return False, set()
    matched_ordinals = _match_ordinals(ordinal_tokens, resolvable_exports)
    if not matched_ordinals:
        return False, set()
    return True, _collect_forward_candidates(matched_ordinals, dep_forward_map)


@lru_cache(maxsize=1)
def get_system_search_paths():
    return [p for p in os.environ.get("PATH", "").split(os.pathsep) if os.path.isdir(p)]


class DependencyParseItem:
    def __init__(
        self,
        dll_path: str,
        is_missing: bool,
        is_valid: bool,
        is_delay: bool,
        is_system: bool,
        is_forward: bool = False,
        forward_to: list[str] | None = None,
        is_virtual: bool = False,
    ):
        self.dll_path = dll_path
        self.is_missing = is_missing
        self.is_valid = is_valid
        self.is_delay = is_delay
        self.is_system = is_system
        self.is_forward = is_forward
        self.forward_to = list(forward_to) if forward_to else []
        self.is_virtual = is_virtual


class DependencyParseResult:
    def __init__(self):
        self.items = []

    def add(self, *args, **kwargs):
        self.items.append(DependencyParseItem(*args, **kwargs))

    def __iter__(self):
        return iter(self.items)


@dataclass(frozen=True)
class DependencyResolution:
    dll_path: str
    export_source_path: str
    is_missing: bool
    is_system: bool
    is_virtual: bool
    forward_to: list[str] = field(default_factory=list)


@lru_cache(maxsize=1024)
def find_local_dll(base_dir, dll):
    temp_path = os.path.abspath(os.path.join(base_dir, dll))
    if os.path.isfile(temp_path):
        return temp_path
    return None


@lru_cache(maxsize=1024)
def find_system_dll(dll):
    for sys_path in get_system_search_paths():
        temp_path = os.path.abspath(os.path.join(sys_path, dll))
        if os.path.isfile(temp_path):
            return temp_path
    return None


def _resolve_dependency_target(base_dir, entry_name):
    dll_local = find_local_dll(base_dir, entry_name)
    dll_system = find_system_dll(entry_name)

    if dll_local:
        return DependencyResolution(
            dll_path=dll_local,
            export_source_path=dll_local,
            is_missing=False,
            is_system=False,
            is_virtual=False,
        )

    if dll_system:
        return DependencyResolution(
            dll_path=dll_system,
            export_source_path=dll_system,
            is_missing=False,
            is_system=True,
            is_virtual=False,
        )

    if is_apiset_contract(entry_name):
        apiset_host_name = resolve_apiset_contract(entry_name.lower())
        apiset_host_path = find_system_dll(apiset_host_name) if apiset_host_name else None
        if apiset_host_path:
            return DependencyResolution(
                dll_path=entry_name,
                export_source_path=apiset_host_path,
                is_missing=False,
                is_system=False,
                is_virtual=True,
                forward_to=[os.path.basename(apiset_host_path).lower()],
            )

    return DependencyResolution(
        dll_path=entry_name,
        export_source_path="",
        is_missing=True,
        is_system=False,
        is_virtual=False,
    )


def _evaluate_resolved_dependency(resolution: DependencyResolution, import_requirements):
    if resolution.is_missing:
        return False, False, ""

    dep_export_set, dep_forward_map = _load_exports_for_file(resolution.export_source_path)
    resolvable_exports = dep_export_set | set(dep_forward_map.keys())
    has_named_exports = any(token.startswith("N:") for token in dep_export_set)
    matched_forward_candidates = set()

    for requirement in import_requirements:
        requirement_valid, requirement_forward_candidates = _evaluate_requirement(
            requirement=requirement,
            resolvable_exports=resolvable_exports,
            dep_forward_map=dep_forward_map,
            has_named_exports=has_named_exports,
        )
        if not requirement_valid:
            return False, False, []
        matched_forward_candidates |= requirement_forward_candidates

    matched_forwarders = sorted(
        {dep_forward_map[candidate] for candidate in matched_forward_candidates}
    )
    dll_is_forward = bool(matched_forwarders) or bool(resolution.forward_to)
    forward_to = resolution.forward_to or matched_forwarders
    # 既然可以走到这里, 那么依赖当然是有效的, 只不过可能是一个转发依赖
    return True, dll_is_forward, forward_to


def parse_file_for_dependencies(base_dir, base_file):
    result = DependencyParseResult()

    pe_base = pefile.PE(base_file, fast_load=True)
    pe_base.parse_data_directories(_import_directory_ids())
    pe_base_imports = getattr(pe_base, "DIRECTORY_ENTRY_IMPORT", [])
    pe_base_delay_imports = getattr(pe_base, "DIRECTORY_ENTRY_DELAY_IMPORT", [])
    pe_base_bound_imports = getattr(pe_base, "DIRECTORY_ENTRY_BOUND_IMPORT", [])

    import_groups = (pe_base_imports, pe_base_delay_imports, pe_base_bound_imports)
    for entries in import_groups:
        for entry in entries:
            entry_name = entry.dll.decode(errors="ignore")
            import_requirements = _collect_import_requirements(entry)
            resolution = _resolve_dependency_target(base_dir, entry_name)
            dll_is_valid, dll_is_forward, dll_forward_to = _evaluate_resolved_dependency(
                resolution, import_requirements
            )
            result.add(
                resolution.dll_path,
                resolution.is_missing,
                dll_is_valid,
                (entry in pe_base_delay_imports),
                resolution.is_system,
                dll_is_forward,
                dll_forward_to,
                resolution.is_virtual,
            )

    pe_base.close()
    return result


def _build_dependency_graph(root_files, detect_system=False, verbose=False, threads=16):
    pbar = tqdm(total=0, desc="Resolving dependencies", unit="file", dynamic_ncols=True)
    abs_files = [os.path.abspath(path) for path in root_files]
    base_dir = os.path.dirname(abs_files[0])
    graph = DependencyGraph()
    submitted = set()

    def upsert_node(
        path: str,
        *,
        is_system: bool = False,
        is_forward: bool = False,
        forward_to: list[str] | None = None,
        is_virtual: bool = False,
    ):
        node_data = graph.node_data(path)
        node_data.is_system = node_data.is_system or is_system
        node_data.is_virtual = node_data.is_virtual or is_virtual
        if is_forward:
            node_data.is_forward = True
            for target in forward_to or []:
                if target and target not in node_data.forward_to:
                    node_data.forward_to.append(target)
        return path

    with ProcessPoolExecutor(max_workers=threads) as executor:
        futures = {}

        def submit(path):
            future = executor.submit(parse_file_for_dependencies, base_dir, path)
            futures[future] = path
            pbar.total += 1
            pbar.refresh()
            if verbose:
                print(f"[DEBUG] Submitting: {path}")

        for abs_file in abs_files:
            upsert_node(abs_file)
            submitted.add(abs_file)
            submit(abs_file)

        while futures:
            # 使用 as_completed 保持并发处理效率。
            for future in as_completed(list(futures.keys())):
                parent_path = futures.pop(future)

                try:
                    results = future.result()
                except Exception as e:
                    if verbose:
                        print(f"[ERROR] Failed to parse {parent_path}: {e}")
                    results = DependencyParseResult()

                for result_item in results:
                    result_item: DependencyParseItem
                    edge_data = EdgeData(
                        is_delay=result_item.is_delay,
                        is_missing=result_item.is_missing,
                        is_valid=result_item.is_valid,
                    )
                    if not graph.should_include(
                        edge_data=edge_data,
                        is_system=result_item.is_system,
                        detect_system=detect_system,
                    ):
                        if verbose:
                            print(
                                f"[DEBUG] Skip {result_item.dll_path} for {parent_path}"
                            )
                        continue
                    parent_node = upsert_node(parent_path)
                    child_node = upsert_node(
                        result_item.dll_path,
                        is_system=result_item.is_system,
                        is_forward=result_item.is_forward,
                        forward_to=result_item.forward_to,
                        is_virtual=result_item.is_virtual,
                    )
                    graph.add_edge(
                        parent_node,
                        child_node,
                        edge_data,
                    )
                    child_node_data = graph.node_data(child_node)
                    if not graph.should_expand(
                        node_data=child_node_data,
                        edge_data=edge_data,
                    ):
                        if verbose:
                            print(
                                f"[DEBUG] Skip expand {result_item.dll_path} for {parent_path}"
                            )
                        continue
                    if child_node not in submitted:
                        submitted.add(child_node)
                        submit(child_node)
                pbar.update(1)
                break

    for node_path, node_attrs in graph.graph.nodes(data=True):
        if node_path.lower().endswith(".dll") and graph.graph.in_degree(node_path) == 0:
            node_attrs["data"].is_orphan = True

    pbar.close()
    return graph


def build_dependency_graph(path, detect_system=False, verbose=False, threads=16):
    abs_path = os.path.abspath(path)
    if os.path.isdir(abs_path):
        files = [
            os.path.abspath(os.path.join(abs_path, e.name))
            for e in os.scandir(abs_path)
            if e.is_file() and e.name.lower().endswith((".dll", ".exe"))
        ]
    else:
        files = [abs_path]
    return _build_dependency_graph(files, detect_system, verbose, threads)
