# Copilot instructions for win_depends

## Project summary
- `win_depends` is a Python CLI for analyzing Windows `.dll`/`.exe` dependency graphs, including delayed/bound imports, missing dependencies, forwarded exports, and API-set contract resolution.
- CLI entry point is `win_depends.cli:main` (console script name: `win_depends`).

## Build, test, and lint commands
- Install local editable package: `python -m pip install -e .`
- Build wheel: `python -m build --wheel`
- Run CLI module directly: `python -m win_depends.cli <target> [--print-tree] [--depth N] [--out FILE] [--print-missing] [--print-orphan] [--print-invalid] [--detect-system] [--threads N] [--verbose]` (aliases: `-d`, `-o`, `-t`, `-V`).
- Install export test parsers: `python -m pip install html5lib pydot` (also declared in the Poetry dev group and installed by CI).
- Run all tests: `python -m pytest -q`
- Run a single test: `python -m pytest -q tests/test_core_parse.py::test_parse_file_for_dependencies_apiset_resolved`
- Run lint formatters/checkers:
  - `python -m black win_depends tests`
  - `python -m isort win_depends tests`
  - `python -m flake8 win_depends tests`
  - Optional combined hooks: `python -m pre_commit run --all-files`

## High-level architecture
- `win_depends/cli.py` handles argument parsing and target validation, then delegates dependency analysis to `build_dependency_graph()`, terminal reports to `printer.py`, and atomic file exports to `exporter.py`.
- `win_depends/core.py` is the main engine:
  - `build_dependency_graph()` collects root `.dll`/`.exe` files (directory mode is non-recursive: only direct children from `os.scandir`).
  - `_build_dependency_graph()` performs concurrent expansion with `ProcessPoolExecutor`, submitting `parse_file_for_dependencies()` jobs and progressively building a `DependencyGraph`.
  - Dependency resolution order is local file (`find_local_dll`) -> system `PATH` (`find_system_dll`) -> API-set contract mapping (`resolve_apiset_contract`) -> missing.
- `win_depends/petool.py` validates whether imported symbols are satisfiable by exports from the resolved dependency and identifies forwarded exports.
- `win_depends/apiset.py` resolves `api-ms-*`/`ext-ms-*` contracts by reading the API set schema from the current process PEB (v6 schema parsing via `ctypes`).
- Graph model is split across:
  - `graph.py`: wrapper over `networkx.DiGraph` plus include/expand policies
  - `nodedata.py`: node flags (`is_system`, `is_forward`, `forward_to`, `is_virtual`, `is_orphan`)
  - `edgedata.py`: edge flags (`is_missing`, `is_valid`, `is_delay`, `in_cycle`) used by output and DOT export
- `win_depends/printer.py` produces user-facing terminal reports (`print_tree`, `print_missing`, `print_invalid`, `print_orphan`).
- `win_depends/exporter.py` uses one complete graph document for CSV/JSON/HTML/DOT/TXT; the version 1 schemas are documented in README. `--out` (alias `-o`) infers the format from a case-insensitive extension; `--graph` and `--dot` are removed.
- Cycle flags are finalized at the end of graph construction using strongly connected components in `DependencyGraph.mark_cycle_flags()` (including self-loops). Tree reports and exports reuse cached SCC results unless actual edge topology changes; manually built or directly edited graphs remain supported. Reports must never filter or truncate the exported model.

## Key conventions in this repository
- Keep CLI version and package version synchronized (`win_depends/cli.py` `--version` and `pyproject.toml` `tool.poetry.version`).
- Missing dependencies are always retained in the graph; system dependencies are filtered only when `--detect-system` is not enabled and the edge is not missing (`DependencyGraph.should_include`).
- API-set contracts are represented as virtual nodes (contract name as node path) with `forward_to` pointing to the resolved host DLL; virtual nodes are not expanded further (`DependencyGraph.should_expand`).
- Forward targets and most dependency comparisons are normalized to lowercase; output ordering is generally case-insensitive (`key=str.lower`).
- Orphan detection is post-pass in `core.py`: any `.dll` node with `in_degree == 0` is marked orphan.
- Tests rely heavily on monkeypatching (`pefile.PE`, executors, and resolver helpers) to avoid real PE/system dependencies; follow this pattern for new parser/graph tests.
- Build artifacts (`dist/`, `build/`, `*.egg-info`) may exist in-tree; treat them as generated outputs, not source to edit.