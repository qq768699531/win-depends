# win\_depends

🧩 **win\_depends** is a lightweight tool to analyze DLL and EXE dependencies on Windows. It supports recursive dependency resolution, detection of missing or unused files, and exports to DOT graph format.

---

## 1.0.3

* `--check-missing` reports missing delay-loaded dependencies and their downstream
  dependencies as warnings instead of missing-file errors.
* A dependency still appears as an error if any non-delay-loaded path requires it.
* Missing files are deduplicated, with importing files and delayed paths shown.
* Duplicate normal/delayed imports retain the normal import's required status.

---

## 📦 Installation

```bash
pip install win_depends
```

---

## 🚀 Usage Example

Run the tool in a directory containing `.dll` and `.exe` files:

```bash
win_depends
```

You can also specify a path to a file or directory:

```bash
win_depends ./path/to/myapp.exe
win_depends ./build/bin/
```

Optional flags can customize the output, such as displaying a dependency tree:

````bash
win_depends ./build/bin --tree
```bash
win_depends
````

Optional flags can customize the output, such as displaying a dependency tree:

```bash
win_depends --tree
```

---

## 🔍 Features

* ✅ Analyze imports between `.dll` and `.exe` files, including delayed and bound imports
* ✅ Detect forwarded exports and surface forwarding targets directly in tree / missing / invalid outputs (DLL name only)
* ✅ Resolve `api-ms-*` / `ext-ms-*` contracts to host DLLs (for example `kernelbase.dll`) to avoid false missing reports
* ✅ Parallel dependency analysis for faster performance
* ✅ Automatic detection of system DLLs (always enabled)
* ✅ Detect missing dependent files; delay-loaded chains are reported as warnings
* ✅ Detect unused files in directory
* ✅ Tree-style output of dependencies
* ✅ Export to DOT format for graph visualization

---

## 🧪 Sample Output

Use `win_depends .\demo.exe --check-missing` to list missing dependencies.
Missing DLLs imported directly with delay loading, or reached only through a
delay-loaded ancestor, appear under
`Missing dependencies (delay-loaded; warning only)` with a warning marker.
If any non-delay-loaded path requires the same file, it remains an error.
Each file is listed once, with its importing files and delayed paths marked
`[DELAY-LOADED]`. These warnings do not guarantee that the affected feature will
work when the DLL is actually loaded. The command's exit-code behavior is unchanged.

For a single-file target, paths start at that file. For a directory target,
dependency roots are inferred from the full graph, so scanning a DLL does not
by itself make its dependencies mandatory. Rootless source cycles are treated
conservatively as entry points.

```bash
$ win_depends ./demo.exe --tree

└── demo.exe
    ├── user32.dll ❌
    ├── plugin.dll
    │   └── helper.dll
    └── kernel32.dll ❌

Missing dependencies:
  user32.dll
  kernel32.dll
```
