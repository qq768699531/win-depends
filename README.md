# win_depends

[![CI](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml/badge.svg)](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/win-depends)](https://pypi.org/project/win-depends/)

Analyze Windows DLL/EXE dependencies, find missing DLLs and unresolved imports.

## Installation

```powershell
python -m pip install win_depends
```

## Usage

Pass a DLL, EXE, or directory and select the reports to generate:

```powershell
# Report missing dependencies for one executable
win_depends .\build\bin\MyApp.exe --print-missing

# Show a dependency tree and missing or invalid dependencies
win_depends .\build\bin\MyApp.exe --print-tree --print-missing --print-invalid

# Find local orphan DLLs and limit analysis depth
win_depends .\build\bin --print-orphan --print-tree -d 3

# Save the dependency graph
win_depends .\build\bin\MyApp.exe -o .\dependencies.html
```

Directory scans include only directly contained DLL/EXE files, not subdirectories.

## Options

| Option | Description |
| --- | --- |
| `--print-missing` | List dependencies that could not be resolved. |
| `--print-invalid` | List dependencies whose imported symbols could not be satisfied. |
| `--print-orphan` | List local DLLs that are not dependencies of another analyzed file. |
| `--print-tree` | Print the analyzed dependency tree. |
| `-d N`, `--depth N` | Limit graph construction depth. Entry points are depth 0; default: unlimited. |
| `-o FILE`, `--out FILE` | Save the graph as CSV, JSON, HTML, DOT or TXT, inferred from the file extension. |
| `--detect-system` | Traverse system DLLs as well as local dependencies. Off by default. |
| `-t N`, `--threads N` | Set the analysis thread count. Default: `16`. |
| `-V`, `--verbose` | Print additional diagnostic details. |
| `-v`, `--version` | Print the installed version. |
| `-h`, `--help` | Show command help. |

[Changelog](CHANGELOG.md) · [Release guide](RELEASE.md) · [Roadmap](ROADMAP.md)
