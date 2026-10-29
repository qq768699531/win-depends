import argparse
import os
import sys
import time
from .core import build_dependency_graph
from .exporter import export
from .printer import print_orphan, print_missing, print_invalid, print_tree


def main():
    parser = argparse.ArgumentParser(description="Analyze DLL/EXE dependencies.")
    parser.add_argument("-v", "--version", action="version", version="1.1.0")
    parser.add_argument("target", help="Target DLL/EXE file or directory.")
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        metavar="N",
        help="Limit graph construction depth (entry points: 0; default: unlimited).",
    )
    parser.add_argument(
        "-o",
        "--out",
        metavar="FILE",
        help="Export the complete graph as CSV, JSON, HTML, DOT or TXT (by extension).",
    )
    parser.add_argument(
        "--print-tree",
        action="store_true",
        help="Print the analyzed dependency tree.",
    )
    parser.add_argument(
        "--print-missing",
        action="store_true",
        help="Print missing dependencies; delay-loaded chains are warnings only.",
    )
    parser.add_argument(
        "--print-invalid",
        action="store_true",
        help="Print dependencies with unresolved imports.",
    )
    parser.add_argument(
        "--print-orphan",
        action="store_true",
        help="Print orphan local DLL files.",
    )
    parser.add_argument(
        "--detect-system",
        action="store_true",
        help="Analyze system DLLs (default: off; only analyzes files in current directory).",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=16,
        metavar="N",
        help="Number of threads to use in the thread pool (default: 16).",
    )
    parser.add_argument(
        "-V",
        "--verbose",
        action="store_true",
        help="Print detailed output for debugging.",
    )

    args = parser.parse_args()
    if args.depth is not None and args.depth < 0:
        parser.error("--depth must be nonnegative")
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
        depth=args.depth,
    )

    print(f"Analyzing dependencies in: {base_dir}")

    if args.print_tree:
        print_tree(dep_graph)
    if args.print_orphan:
        print_orphan(dep_graph)
    if args.print_missing:
        print_missing(dep_graph)
    if args.print_invalid:
        print_invalid(dep_graph)
    if args.out is not None:
        export(dep_graph, args.out)
        print(f"Dependency graph written to: {args.out}")

    print(f"Total time: {time.perf_counter() - start:.2f}s")


if __name__ == "__main__":
    main()
