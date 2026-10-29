# Next release: file exports

Status: implemented and locally verified for version `1.1.0`, not yet published.

## CLI changes

Replace `--graph` and `--dot` with `--out FILE` (short form `-o FILE`).
Infer the output format from
the filename extension; do not introduce a separate format option.

Implemented usage:

```powershell
win_depends MyApp.exe --out dependencies.json
win_depends MyApp.exe --out dependencies.csv
win_depends MyApp.exe --out dependencies.html
win_depends MyApp.exe --out dependencies.dot
win_depends MyApp.exe --out dependencies.txt
win_depends MyApp.exe -o dependencies.json
win_depends MyApp.exe --print-missing --print-tree --depth 2 --out dependencies.json
```

`--out` always exports the complete analyzed dependency graph. Report options
such as `--print-missing` and `--print-tree` control terminal output only; they do not
filter or truncate the exported graph. Analysis options such as
`--detect-system` and `--depth` still determine which dependencies are analyzed.
Do not print serialized graph content to the terminal.

Removing the old options is a breaking CLI change. Document the migration
from `--graph --dot FILE` to `--out FILE` in the release notes.

## Format requirements

All formats must retain isolated nodes, dependency direction, and relevant
node and edge attributes. Same-named binaries must remain distinct.
The exported data must not depend on whether a terminal report was requested.

| Extension | Requirements |
| --- | --- |
| `.csv` | Follow RFC 4180: a header row, consistent columns, CRLF record endings, and correctly quoted commas, quotes, and embedded newlines. Represent nodes and edges with an explicit record type so isolated nodes are not lost. |
| `.json` | Follow RFC 8259: one JSON document with node and edge collections, unique node identifiers, valid references, and native JSON booleans. |
| `.html` | Produce readable interactive HTML with escaped data. Use PyVis with embedded vis-network resources; the standard template retains Bootstrap CDN references. |
| `.dot` | Produce valid Graphviz DOT for a directed graph. Declare every node, use unique identifiers rather than basenames, and correctly escape labels and attributes. |
| `.txt` | Produce readable UTF-8 plain text with documented, consistent node and dependency sections. TXT has no universal graph standard; do not describe it as a standardized interchange format. |

Use UTF-8 across formats, deterministic ordering, and case-insensitive extension
recognition. Preserve missing, invalid, delayed, system, virtual, orphan, and
forwarded-dependency information where applicable.

## Validation and failures

- Reject missing or unsupported extensions with a nonzero exit code and a
  message listing supported formats. Format selection and validation belong
  to the exporter, not the CLI.
- Surface permission, encoding, and write failures explicitly; do not report
  a successful export or leave a success-shaped partial file.
- Verify exports using format-aware readers or validators, not only string
  comparisons. Check CSV quoting, JSON structure and references, HTML payload
  escaping, DOT parsing, and the documented TXT layout.
- Test empty graphs, isolated nodes, cycles, duplicate basenames, Unicode,
  special characters, and missing or delayed dependencies.
- Confirm that combining `--out` with terminal reports leaves export content
  unchanged. A construction depth limit applies equally to all outputs.

## Delivery status

Delivered together: CLI changes, all five exporters, regression tests, and user
documentation. The version 1 CSV columns and JSON schema shape were documented
in README before implementing the shared graph document and exporters.
CSV and JSON syntax standards alone do not define a dependency graph data model.

Coverage includes parser-backed CSV/JSON/HTML/DOT validation, TXT layout,
special characters and Unicode, empty and isolated graphs, duplicate basenames,
cycles and self-loops, report/depth-independent exports, CLI errors, and atomic
write/encoding failures. HTML uses PyVis's embedded vis-network resources,
interactive directed edges, and safely escaped hover data.

Release/version assignment and publication remain pending. No commit, push or
Git configuration change is part of this delivery.
