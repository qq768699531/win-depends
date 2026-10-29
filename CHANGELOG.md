# Changelog

Notable changes to `win_depends` are documented here.

## Unreleased

### Changed

- Keep the README focused on installation, usage and basic parameters;
  consolidate migration and report behavior notes in this changelog.

## 1.1.0

### Added

- Add `-t` for `--threads`, `-V` for verbose output and `--depth`/`-d` for construction-time depth
  limits using shortest paths from depth-zero input files.
- Replace `--tree [LEVEL]` with `--print-tree`; depth limits now affect analysis
  and every output rather than only the printed tree.
  Directory inputs treat every directly contained DLL/EXE as depth 0;
  nodes at the depth limit are retained without further dependency expansion.

- Export the complete analyzed dependency graph with `--out FILE` (short form
  `-o FILE`), inferring
  CSV, JSON, interactive HTML, Graphviz DOT or plain TXT from a
  case-insensitive extension.
- Document version 1 CSV/JSON data models, including explicit nodes, unique
  path-based IDs, directed edges, entry points and all analysis attributes.
- Add parser-backed export tests for quoting, Unicode, duplicate basenames,
  isolated nodes, empty graphs, cycles and report-independent content, as well
  as atomic write failures and CLI errors.
- Render HTML exports with PyVis's embedded vis-network resources,
  including directed arrows, built-in zoom/pan/drag, status styling and hover
  details; load network options from a bundled JSON resource. Its standard
  template retains Bootstrap CDN references.
- Add GitHub Actions CI for automated tests and wheel builds.
- Expand the README with installation, CLI options, analysis behavior, and
  GitHub project status.
- Add a manual GitHub Release and PyPI publishing guide and a public PyPI
  version badge.

### Fixed

- Export isolated nodes and distinguish binaries sharing a basename.
- Compute cycle flags independently of tree rendering, including self-loops,
  using strongly connected components instead of enumerating all cycles.
  Finalize them after graph construction; reports and exports read the
  finalized flags without repeating detection.
- Handle empty directory scans as empty graphs instead of indexing an empty
  root list.
- Keep format selection and extension validation inside the single export
  entry point; fail explicitly on encoding,
  permission or write errors; atomically replace destinations only on success.
- Run GitHub Actions on Windows so API-set memory and Windows path tests use
  the platform supported by the analyzer.

### Removed

- **Breaking CLI change:** replace `--check-missing`, `--check-invalid` and
  `--check-orphan` with `--print-missing`, `--print-invalid` and `--print-orphan`.
  These options display analysis results; they do not enable detection.
- **Breaking CLI change:** remove `--graph` and `--dot`. Migrate
  `--graph --dot FILE` to `--out FILE`. Graph content is no longer serialized
  to the terminal; use a file viewer for terminal-only graph use cases.
- Remove GitLab CI configuration and switch the Flake8 hook to its GitHub
  repository. GitHub Actions is the sole CI entry point.

### Report behavior

- DLL lookup checks the target directory, then `PATH`. `--detect-system`
  includes system DLLs in the analyzed graph.
- Orphan DLLs may still be loaded dynamically; the report is not a deletion list.
- Missing and invalid dependency reports do not set a failing exit code.

## 1.0.3

### Changed

- Report missing delay-loaded dependencies, and dependencies reachable only
  through delayed paths, as warnings rather than missing-file errors.
- Keep a missing DLL classified as an error if any non-delay-loaded path
  requires it.
- Deduplicate missing files and include importing files and delayed paths in
  the report.
- Preserve the required status when a DLL is imported both normally and with
  delay loading.
- Delay-loading warnings do not guarantee runtime availability; verify the
  affected features when those DLLs are loaded.
