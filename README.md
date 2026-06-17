# win\_depends

🧩 **win\_depends** is a lightweight tool to analyze DLL and EXE dependencies on Windows. It supports recursive dependency resolution, detection of missing or unused files, and exports to DOT graph format.

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
* ✅ Parallel dependency analysis for faster performance
* ✅ Optional detection of system DLLs via `--detect-system`
* ✅ Detect missing dependent files
* ✅ Detect unused files in directory
* ✅ Tree-style output of dependencies
* ✅ Export to DOT format for graph visualization

---

## 🧪 Sample Output

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
