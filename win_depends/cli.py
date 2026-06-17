import argparse
import os
import sys
import time
from .core import build_dependency_graph
from .printer import print_orphan, print_missing, print_invalid, print_tree, export_dot


def main():
    parser = argparse.ArgumentParser(description="Analyze DLL/EXE dependencies.")
    parser.add_argument("-v", "--version", action="version", version="1.0.1")
    parser.add_argument("target", help="Target DLL/EXE file or directory.")
    parser.add_argument(
        "--tree",
        nargs="?",
        const=-1,
        type=int,
        metavar="LEVEL",
        help="Print dependency tree up to specified depth (default: unlimited).",
    )
    parser.add_argument(
        "--graph", action="store_true", help="Print dependency graph in DOT format."
    )
    parser.add_argument("--dot", metavar="FILENAME", help="Write DOT graph to file.")
    parser.add_argument(
        "--check-missing", action="store_true", help="Check for missing dependencies."
    )
    parser.add_argument(
        "--check-invalid",
        action="store_true",
        help="Check if dependencies are loadable.",
    )
    parser.add_argument(
        "--check-orphan",
        action="store_true",
        help="Check for orphan local DLL/EXE files.",
    )
    parser.add_argument(
        "--detect-system",
        action="store_true",
        help="Analyze system DLLs (default: off; only analyzes files in current directory).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=16,
        metavar="N",
        help="Number of threads to use in the thread pool (default: 16).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output for debugging.",
    )

    args = parser.parse_args()

    start = time.perf_counter()

    target = args.target
    is_dir = os.path.isdir(target)
    abs_target = os.path.abspath(target)
    base_dir = abs_target if is_dir else os.path.dirname(abs_target)

    if not (
        is_dir or (os.path.isfile(target) and target.lower().endswith((".dll", ".exe")))
    ):
        print(f"Error: '{target}' is not a valid DLL/EXE file or directory.")
        sys.exit(1)

    dep_graph = build_dependency_graph(
        target,
        detect_system=args.detect_system,
        verbose=args.verbose,
        threads=args.threads,
    )

    print(f"Analyzing dependencies in: {base_dir}")

    if args.check_orphan:
        print_orphan(dep_graph)
    if args.check_missing:
        print_missing(dep_graph)
    if args.check_invalid:
        print_invalid(dep_graph)
    if args.tree is not None:
        print_tree(dep_graph, max_depth=args.tree)
    if args.graph:
        dot = export_dot(dep_graph)
        if args.dot:
            with open(args.dot, "w", encoding="utf-8") as f:
                f.write(dot)
            print(f"DOT graph written to: {args.dot}")
        else:
            print(dot)

    print(f"Total time: {time.perf_counter() - start:.2f}s")


if __name__ == "__main__":
    main()
