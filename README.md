# win_depends

[![CI](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml/badge.svg)](https://github.com/qq768699531/win-depends/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/win-depends)](https://pypi.org/project/win-depends/)

Analyze Windows DLL/EXE dependencies, find missing DLLs and unresolved imports,
and export dependency graphs.

## Installation

```powershell
python -m pip install win_depends
```

## Usage

Pass a DLL, EXE, or directory and select the reports to generate:

```powershell
# Report missing dependencies for one executable
win_depends .\build\bin\MyApp.exe --print-missing

# Show a dependency tree and check missing and invalid dependencies
win_depends .\build\bin\MyApp.exe --print-tree --print-missing --print-invalid

# Check DLLs in a directory and find local orphan DLLs
win_depends .\build\bin --print-orphan --print-tree -d 3

# Export a complete graph (format inferred from the extension)
win_depends .\build\bin\MyApp.exe --out .\dependencies.json
win_depends .\build\bin\MyApp.exe --out .\dependencies.csv
win_depends .\build\bin\MyApp.exe --out .\dependencies.html
win_depends .\build\bin\MyApp.exe --out .\dependencies.dot
win_depends .\build\bin\MyApp.exe --out .\dependencies.txt

# Short option: -o is equivalent to --out
win_depends .\build\bin\MyApp.exe -o .\dependencies.json

# Limit analysis depth for both terminal reports and export
win_depends .\build\bin\MyApp.exe --print-missing -d 2 --out .\dependencies.JSON
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
| `-o FILE`, `--out FILE` | Export the complete analyzed graph; `.csv`, `.json`, `.html`, `.dot` or `.txt` (case-insensitive). |
| `--detect-system` | Traverse system DLLs as well as local dependencies. Off by default. |
| `-t N`, `--threads N` | Set the analysis thread count. Default: `16`. |
| `-V`, `--verbose` | Print additional diagnostic details. |
| `-v`, `--version` | Print the installed version. |
| `-h`, `--help` | Show command help. |

## Report notes

- `--print-*` options display results already collected during analysis.
  They replace the removed `--check-*` options.
- DLL lookup uses the target directory, then `PATH`. Use `--detect-system` to
  include system DLLs in the dependency graph.
- Missing DLLs reachable only through delay-loaded imports are warnings.
  A normal import of the same DLL makes it an error. Verify affected features
  at runtime.
- Orphan DLLs may still be loaded dynamically; the report is not a deletion list.
- Reports do not set a failing exit code for missing or invalid dependencies.
- Without `--out`, terminal behavior is unchanged. With `--out`, reports still
  print normally, followed by a file confirmation; serialized graph data is
  never printed to the terminal.

## Export migration and errors

Version 1.1.0 removes `--graph` and `--dot` (breaking CLI change).
Replace `--graph --dot FILE` with `--out FILE`, for example:

```powershell
win_depends MyApp.exe --out dependencies.dot
```

`-o FILE` is an equivalent short form of `--out FILE`.

For the former `--graph` terminal-only use, export a file and view it with your
preferred viewer. CSV/JSON are interchange formats; TXT is a readable report;
DOT can be rendered by Graphviz. HTML opens in a modern browser as an interactive
directed dependency network.

Missing/unsupported output extensions raise an error listing supported formats.
Encoding, permission and write failures also propagate without being caught by
the CLI. Python reports the exception and exits nonzero, without a success message.
Parent directories must already exist. Data is serialized and UTF-8 encoded
before writing, then staged beside the destination and atomically replaced.
Failed exports leave any existing destination unchanged, not a truncated report.
The output directory must permit creating and replacing files.


## Export data model

Exports describe the complete analyzed directed graph, independently of terminal
reports. Analysis options such as `--depth` and `--detect-system` still apply.

`--print-tree` replaces `--tree` and takes no argument. `--depth` limits analysis,
not just display: depth 0 includes only input files, depth 1 adds their direct
dependencies. Directory inputs treat every directly contained DLL/EXE as depth 0.
Dependencies at the depth limit are retained but are not parsed for further
dependencies. When multiple paths reach a dependency, the shortest path applies.
All formats use UTF-8 and deterministic ordering by exact node ID, then by
`(source, target)` for edges. IDs are the graph's full path keys (or unresolved
DLL/API-set names), never basenames or traversal-dependent numbers.
Paths are retained as analyzed, without additional case or path normalization.
Different paths with the same basename therefore remain distinct.
Edges point from the importing binary to its dependency.

### JSON schema (schema_version 1)

The top-level object contains exactly:

- `schema_version`: integer `1`.
- `entry_points`: sorted array of node IDs for explicit analysis entry points;
  empty for directory scans.
- `nodes`: array of objects with string `id`, `path` (equal to `id`), and `name`
  (basename); boolean `is_system`, `is_forward`, `is_virtual`, `is_orphan`;
  and `forward_to`, a sorted, deduplicated array of forwarding target strings.
  Forwarding targets are annotations, not necessarily analyzed node IDs.
- `edges`: array of objects with string `source` and `target` referencing node
  IDs, and boolean `is_missing`, `is_valid`, `is_delay`, `in_cycle`.

Every node is included, even without edges. Missing/invalid/delayed status
belongs to an edge, not its target node. `in_cycle` is true exactly when that
edge belongs to a directed cycle, including self-loops.
JSON follows RFC 8259 and uses native booleans, not strings.

### CSV schema (schema_version 1)

CSV follows RFC 4180 with a header, CRLF record endings, and quoted fields when
needed. Columns, in order:

```text
record_type,id,path,name,is_system,is_forward,is_virtual,is_orphan,forward_to,is_entry_point,source,target,is_missing,is_valid,is_delay,in_cycle
```

Node rows (`record_type=node`) populate `id` through `is_entry_point`;
edge rows (`record_type=edge`) populate `source` through `in_cycle`.
Non-applicable cells are empty. Boolean cells are lowercase `true`/`false`.
`forward_to` is a JSON array encoded in one CSV cell, including `[]` for none.
`is_entry_point` records membership in JSON's `entry_points`.
Node rows precede edge rows; an empty graph contains only the header.

### Human-readable formats

DOT declares every node using the same unique IDs. Node and edge attributes
match JSON (`name` is represented by `label`, booleans are DOT strings and
`forward_to` is a JSON array string),
with `is_entry_point` on nodes, plus readable labels and edge status colors.
HTML uses PyVis and its bundled vis-network to display every node and directed
edge, including isolated nodes and duplicate basenames. Built-in hierarchical
layout and physics position the dependency network; arrows point from importer
to dependency, including self-loops. Missing, invalid and cyclic edges have
distinct colors; delayed edges are dashed. System, virtual, orphan, missing
target, entry-point and isolated-node styles are distinct. Hover a node or edge
to inspect its complete attributes, including full paths and forwarding targets.
Use vis-network's built-in zoom, pan, node dragging and navigation controls.

The HTML embeds PyVis's vis-network JavaScript and CSS resources and graph data.
The standard PyVis template also references Bootstrap assets from a CDN.
Embedded node and edge payloads use unique generated numeric IDs. Hover details
preserve the original path IDs. Titles and script data are escaped before
embedding; large attribute tables are not duplicated in the page.
TXT has `Nodes (N):` and `Dependencies (M):` sections with one JSON-quoted
ID/path/name per node and `source -> target` per edge, followed by all attributes.
Quoted strings safely represent embedded newlines; TXT is a readable report,
not a standardized interchange format.

[Changelog](CHANGELOG.md) · [Release guide](RELEASE.md) · [Roadmap](ROADMAP.md)
