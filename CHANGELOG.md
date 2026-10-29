# Changelog

Notable changes to `win_depends` are documented here.

## Unreleased

### Added

- Add GitHub Actions CI for automated tests and wheel builds.
- Expand the README with installation, CLI options, analysis behavior, and
  GitHub project status.
- Add a manual GitHub Release and PyPI publishing guide and a public PyPI
  version badge.

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
