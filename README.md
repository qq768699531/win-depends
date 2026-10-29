# win_depends

[![CI](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml/badge.svg)](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/win-depends)](https://pypi.org/project/win-depends/)

Analyze Windows DLL/EXE dependencies, find missing DLLs and unresolved imports,
and export dependency graphs.

## Features

- Analyze normal, delayed, and bound imports.
- Check whether imported symbols are available from resolved DLLs.
- Detect missing dependencies, invalid imports, and orphan DLLs.
- Resolve forwarded exports and Windows API-set contracts.
- Print dependency trees or export dependency graphs as DOT.

## Installation

```powershell
python -m pip install win_depends
```

## Usage

Pass a DLL, EXE, or directory and select the reports to generate:

```powershell
# Report missing dependencies for one executable
win_depends .\build\bin\MyApp.exe --check-missing

# Show a dependency tree and check missing and invalid dependencies
win_depends .\build\bin\MyApp.exe --tree --check-missing --check-invalid

# Check DLLs in a directory and find local orphan DLLs
win_depends .\build\bin --check-orphan --tree 3

# Write a dependency graph in DOT format
win_depends .\build\bin\MyApp.exe --graph --dot .\dependencies.dot
```

Directory scans include only directly contained DLL/EXE files, not subdirectories.

## Options

| Option | Description |
| --- | --- |
| `--check-missing` | List dependencies that could not be resolved. |
| `--check-invalid` | List dependencies whose imported symbols could not be satisfied. |
| `--check-orphan` | List local DLLs that are not dependencies of another analyzed file. |
| `--tree [LEVEL]` | Print a dependency tree. Omit `LEVEL` for unlimited depth. |
| `--graph` | Print the dependency graph in DOT format. |
| `--dot FILE` | Write the DOT graph to `FILE`; use together with `--graph`. |
| `--detect-system` | Traverse system DLLs as well as local dependencies. Off by default. |
| `--threads N` | Set the analysis thread count. Default: `16`. |
| `--verbose` | Print additional diagnostic details. |
| `-v`, `--version` | Print the installed version. |
| `-h`, `--help` | Show command help. |

## Report notes

- DLL lookup uses the target directory, then `PATH`. Use `--detect-system` to
  include system DLLs in the dependency graph.
- Missing DLLs reachable only through delay-loaded imports are warnings.
  A normal import of the same DLL makes it an error. Verify affected features
  at runtime.
- Orphan DLLs may still be loaded dynamically; the report is not a deletion list.
- Reports do not set a failing exit code for missing or invalid dependencies.

[Changelog](CHANGELOG.md) · [Release guide](RELEASE.md)
