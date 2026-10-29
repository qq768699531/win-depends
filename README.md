# win_depends

[![CI](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml/badge.svg)](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/win-depends)](https://pypi.org/project/win-depends/)

`win_depends` analyzes Windows DLL and EXE dependencies. It resolves local and
system DLLs, checks imported symbols, and can report missing or unused files,
print dependency trees, and export graphs in DOT format.

## Features

- Analyze normal, delayed, and bound imports.
- Check whether imported symbols are available from resolved DLLs.
- Detect missing dependencies, invalid imports, and orphan DLLs.
- Resolve forwarded exports and Windows API-set contracts.
- Print dependency trees or export dependency graphs as DOT.
- Analyze files concurrently with a configurable thread pool.

Dependency parsing uses a thread pool (`--threads N`, default: `16`) rather
than starting Python worker processes in the analyzed directory. This avoids
worker startup conflicts with bundled modules such as `_socket.pyd` that were
built for a different Python version.

The analyzer parses PE files as data; it does not load the target binaries as
Python modules or execute them. Directory targets include DLL and EXE files
directly inside that directory; subdirectories are not scanned recursively.
For a directory target, dependency roots are inferred from the analyzed graph;
a DLL is not automatically treated as an application entry point merely
because it is in the directory. Cycles without a root are conservatively
treated as entry points.

## Installation

Install from the package index configured for your environment:

```powershell
python -m pip install win_depends
```

The package provides the `win_depends` command-line program. Check that the
Python Scripts directory is on `PATH` if the command is not found.

## Quick start

Most invocations should request at least one output mode:

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

The target must be a `.dll`, `.exe`, or a directory containing those files.
When no output option is supplied, the command only reports the analysis
location and elapsed time.

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

Dependency lookup checks the target directory first, then system search paths.
Windows API-set contracts are resolved to their host DLL when possible.
System DLLs can be resolved during normal analysis; `--detect-system` controls
whether their dependencies are also traversed.

## Delay-loaded dependencies

With `--check-missing`, a missing DLL that is imported only through a
delay-loaded path is shown under
`Missing dependencies (delay-loaded; warning only)`. Its downstream
dependencies are treated the same way when they are reachable only through
that delayed path. If any normal, non-delay-loaded path also requires the same
DLL, it remains a missing-dependency error. Duplicate missing files are listed
once, with importing files and delayed paths shown.

A warning is not proof that the affected feature will work when it attempts to
load the DLL. Validate that feature at runtime as part of application testing.
The diagnostic output does not change the command's existing exit-code
behavior.

## Development

Run the test suite and build a wheel with:

```powershell
python -m pip install . pytest pytest-cov
python -m pytest -q
python -m pip install build
python -m build --wheel
```

GitHub Actions runs the tests on Windows with Python 3.11 and builds a wheel
for pushes and pull requests. Windows runners are required for the Windows
API-set memory layout and path-handling tests.
See the [changelog](CHANGELOG.md) for release notes and unreleased changes.
Maintainers can follow the [release guide](RELEASE.md) to publish matching
GitHub Releases and PyPI distributions.

The PyPI badge reflects the latest version available on the public package
index, not an internal index or an unpublished Git tag. It may show an error
before the first public release and can take time to refresh after publication.
