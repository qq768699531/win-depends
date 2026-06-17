# Copilot instructions for win_depends

Short summary
- A small Python CLI tool to analyze Windows DLL/EXE dependencies. Entry point: console script `win_depends` (win_depends.cli:main).

Build / install / run
- Install published package: pip install win_depends
- Install from local source (editable): pip install -e .
- Build wheel from pyproject backend: python -m build --wheel
- Run CLI directly (from repo root): python -m win_depends.cli <target> [--tree | --graph | --dot FILE | --check-missing | --check-orphan | --check-invalid]
  - Example: python -m win_depends.cli ./build/bin --tree

Tests & linters
- Test suite exists under tests/. Run all tests with: python -m pytest -q
- Lint tools are configured: black, isort, flake8.

High-level architecture (big picture)
- CLI layer: win_depends.cli parses args and drives the analysis. It calls build_dependency_graph() in core.
- Core analysis: win_depends.core performs file discovery and dependency resolution, using pefile for PE parsing and a thread pool (default 16 threads) for parallel scanning.
- Data model: Graph uses networkx `DiGraph` to represent relations, with `NodeData`/`EdgeData` as state payloads (nodedata.py, edgedata.py, graph.py).
- Output: printer.py contains presentation helpers (print_orphan, print_missing, print_invalid, print_tree, export_dot) and consumes graph data.
- Packaging: pyproject.toml is the canonical package metadata and build entry point. Third-party runtime deps: pefile, tqdm.

Key repository conventions and notes
- Single-package layout: package name and top-level module both `win_depends`. Keep module and console script names aligned.
- CLI version string is hardcoded in cli.py (`--version` uses "1.0.0") while pyproject.toml has version `1.0.0`. Keep these synchronized when releasing.
- Build artifacts (build/, dist/, *.egg-info) may exist in-tree. Prefer rebuilding via `python -m build` rather than editing generated files in build/ or dist/.
- Threading: core uses a thread-pool with a default of 16 threads; tests or debugging runs may want a smaller number to simplify output.
- PE parsing: rely on pefile for import parsing; defensive handling required for malformed or packed binaries.

Relevant files to inspect when changing behavior
- CLI behavior and flags: win_depends/cli.py
- Main analysis logic: win_depends/core.py
- Data model: win_depends/nodedata.py, win_depends/edgedata.py, win_depends/graph.py
- Output formatting: win_depends/printer.py
- Packaging: pyproject.toml

If updating this file
- Keep the "Build / install / run" section minimal and factual (don't add generic dev workflow text).
- Sync the CLI version and pyproject.toml version entries when releasing.

Questions?
- Reply if you want this file extended to cover recommended dev tooling (linters, test runner, CI) and I can include suggested commands and sample configs.