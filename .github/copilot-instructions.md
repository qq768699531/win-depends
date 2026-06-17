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
- Data model: Node / Edge / Graph classes (node.py, edge.py, graph.py) represent files and relationships. Graph exposes helpers: print_tree(max_depth), export_dot(), etc.
- Output: printer.py contains presentation helpers (print_orphan, print_missing, print_invalid) and DOT export is produced from Graph.
- Packaging: pyproject.toml is the canonical package metadata and build entry point. Third-party runtime deps: pefile, tqdm.

Key repository conventions and notes
- Single-package layout: package name and top-level module both `win_depends`. Keep module and console script names aligned.
- CLI version string is hardcoded in cli.py (`--version` uses "0.1.5") while pyproject.toml has version `0.1.5.2`. Keep these synchronized when releasing.
- Build artifacts (build/, dist/, *.egg-info) may exist in-tree. Prefer rebuilding via `python -m build` rather than editing generated files in build/ or dist/.
- Threading: core uses a thread-pool with a default of 16 threads; tests or debugging runs may want a smaller number to simplify output.
- PE parsing: rely on pefile for import parsing; defensive handling required for malformed or packed binaries.

Relevant files to inspect when changing behavior
- CLI behavior and flags: win_depends/cli.py
- Main analysis logic: win_depends/core.py
- Data model: win_depends/node.py, win_depends/edge.py, win_depends/graph.py
- Output formatting: win_depends/printer.py
- Packaging: pyproject.toml

If updating this file
- Keep the "Build / install / run" section minimal and factual (don't add generic dev workflow text).
- Sync the CLI version and pyproject.toml version entries when releasing.

Questions?
- Reply if you want this file extended to cover recommended dev tooling (linters, test runner, CI) and I can include suggested commands and sample configs.