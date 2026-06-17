import os
import pefile
from tqdm import tqdm
from .graph import DependencyGraph
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache


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
    ):
        self.dll_path = dll_path
        self.is_missing = is_missing
        self.is_valid = is_valid
        self.is_delay = is_delay
        self.is_system = is_system


class DependencyParseResult:
    def __init__(self):
        self.items = []

    def add(self, *args, **kwargs):
        self.items.append(DependencyParseItem(*args, **kwargs))

    def __iter__(self):
        return iter(self.items)


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


def parse_file_for_dependencies(base_dir, base_file):
    result = DependencyParseResult()

    pe_base = pefile.PE(base_file, fast_load=True)
    pe_base.parse_data_directories(1)
    pe_base_imports = getattr(pe_base, "DIRECTORY_ENTRY_IMPORT", [])
    pe_base_delay_imports = getattr(pe_base, "DIRECTORY_ENTRY_DELAY_IMPORT", [])
    pe_base_bound_imports = getattr(pe_base, "DIRECTORY_ENTRY_BOUND_IMPORT", [])

    for entries in pe_base_imports, pe_base_delay_imports, pe_base_bound_imports:
        entries: pefile.ImportDescData
        for entry in entries:
            entry: pefile.ImportData
            entry_name = entry.dll.decode(errors="ignore")
            entry_imports_set = set()
            for item in entry.imports:
                if item.name:
                    entry_imports_set.add(item.name)
                elif item.ordinal:
                    entry_imports_set.add(item.ordinal)
            # 重试本地查找文件
            dll_local = find_local_dll(base_dir, entry_name)
            # 尝试系统路径查找文件
            dll_system = find_system_dll(entry_name)

            dll_is_missing = dll_local is None and dll_system is None
            dll_is_system = dll_local is None and dll_system is not None
            dll_is_delay = entry in pe_base_delay_imports

            if not dll_is_missing:
                dll_path = dll_local if dll_local else dll_system
                # 要导出足够数量的符号避免误判
                pe_dep = pefile.PE(dll_path, fast_load=True, max_symbol_exports=0xF000)
                pe_dep.parse_data_directories(0)
                pe_dep_exports = getattr(pe_dep, "DIRECTORY_ENTRY_EXPORT", [])
                dep_export_set = set()
                # 有些库只使用编号导出, 而有些库使用名称导出, 还有些库什么都用
                # 问题: 如何判断一个库使用哪种导出
                for item in pe_dep_exports.symbols:
                    if item.name:
                        dep_export_set.add(item.name)
                    if item.ordinal:
                        dep_export_set.add(item.ordinal)

                dll_is_valid = entry_imports_set.issubset(dep_export_set)

                result.add(
                    dll_path,
                    dll_is_missing,
                    dll_is_valid,
                    dll_is_delay,
                    dll_is_system,
                )
            else:
                result.add(entry_name, dll_is_missing, False, False, False)

    pe_base.close()
    return result


def _build_dependency_graph(root_files, detect_system=False, verbose=False, threads=16):
    pbar = tqdm(total=0, desc="Resolving dependencies", unit="file", dynamic_ncols=True)
    abs_files = [os.path.abspath(path) for path in root_files]
    base_dir = os.path.dirname(abs_files[0])
    graph = DependencyGraph()
    submitted = set()

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
            submitted.add(abs_file)
            submit(abs_file)

        while futures:
            # 使用as_completed保证并发性能
            for future in as_completed(list(futures.keys())):
                parent_path = futures.pop(future)

                try:
                    results = future.result()
                except Exception as e:
                    if verbose:
                        print(f"[ERROR] Failed to parse {parent_path}: {e}")
                    results = DependencyParseResult()

                for result_item in results:
                    # 如果是系统文件, 并且存在, 并且设置为不检测, 那么跳过
                    # 对于不存在的系统文件, 仍然要显示
                    result_item: DependencyParseItem
                    need_skip: bool = (
                        result_item.is_system
                        and not detect_system
                        and not result_item.is_missing
                    )
                    if need_skip:
                        if verbose:
                            print(
                                f"[DEBUG] Skip {result_item.dll_path} for {parent_path}"
                            )
                        continue
                    graph.add_edge(
                        parent_path,
                        result_item.dll_path,
                        is_delay=result_item.is_delay,
                        is_missing=result_item.is_missing,
                        is_valid=result_item.is_valid,
                    )
                    child_node = graph.get_node(result_item.dll_path)
                    child_node.is_system = result_item.is_system
                    # 如果这个对象丢失, 那么不要继续展开, 没有意义
                    if result_item.is_missing:
                        if verbose:
                            print(
                                f"[DEBUG] Missing {result_item.dll_path} for {parent_path}"
                            )
                        continue
                    if child_node.path not in submitted:
                        submitted.add(child_node.path)
                        submit(child_node.path)
                pbar.update(1)
                break

    for node in graph.nodes.values():
        if node.path.lower().endswith(".dll") and not graph.parents.get(node):
            node.orphan = True

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
