import json
import sys

import pytest

import win_depends.core as core
from win_depends import cli, exporter
from win_depends.edgedata import EdgeData
from win_depends.graph import DependencyGraph
from win_depends.nodedata import NodeData


def test_cli_main_basic(monkeypatch, tmp_path, capsys):
    f = tmp_path / "a.dll"
    f.write_text("x")

    def fake_build(path, detect_system=False, verbose=False, threads=16, depth=None):
        return DependencyGraph()

    monkeypatch.setattr(cli, "build_dependency_graph", fake_build)
    monkeypatch.setattr(sys, "argv", ["win_depends", str(f)])

    # call main (should not raise)
    cli.main()
    out = capsys.readouterr().out
    assert "Analyzing dependencies in" in out


def test_cli_main_no_check_forward_flag(monkeypatch, tmp_path):
    f = tmp_path / "a.dll"
    f.write_text("x")

    def fake_build(path, detect_system=False, verbose=False, threads=16, depth=None):
        return DependencyGraph()

    monkeypatch.setattr(cli, "build_dependency_graph", fake_build)
    monkeypatch.setattr(sys, "argv", ["win_depends", str(f), "--check-forward"])

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected argparse to reject --check-forward")


@pytest.mark.parametrize("fmt", exporter.FORMATS)
def test_cli_export_is_independent_of_all_reports(monkeypatch, tmp_path, capsys, fmt):
    target = tmp_path / "app.exe"
    target.write_bytes(b"")
    graph = DependencyGraph()
    graph.add_edge(str(target), "a.dll")
    graph.add_edge("a.dll", "b.dll", EdgeData(is_delay=True))
    graph.add_edge("b.dll", "a.dll")
    graph.add_edge("b.dll", "missing.dll", EdgeData(is_missing=True))
    graph.add_edge("b.dll", "invalid.dll", EdgeData(is_valid=False))
    graph.add_node("orphan.dll", NodeData(is_orphan=True))
    graph.graph.graph["entry_points"] = [str(target)]
    calls = []

    def fake_build(path, **options):
        calls.append((path, options))
        return graph

    monkeypatch.setattr(cli, "build_dependency_graph", fake_build)
    first = tmp_path / f"first.{fmt}"
    second = tmp_path / f"second.{fmt.upper()}"
    options = ["--detect-system", "--threads", "2", "--verbose"]
    monkeypatch.setattr(
        sys, "argv", ["win_depends", str(target), *options, "-o", str(first)]
    )
    cli.main()
    output = capsys.readouterr()
    assert "Dependency graph written to:" in output.out
    assert "b.dll" not in output.out
    assert output.err == ""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "win_depends",
            str(target),
            *options,
            "--print-missing",
            "--print-invalid",
            "--print-orphan",
            "--print-tree",
            "--out",
            str(second),
        ],
    )
    cli.main()
    output = capsys.readouterr().out
    assert "Missing dependencies" in output and "Invalid files" in output
    assert "Orphan DLLs" in output
    assert first.read_bytes() == second.read_bytes()
    assert "b.dll" in second.read_text(encoding="utf-8")
    assert (
        calls
        == [
            (
                str(target),
                {"detect_system": True, "verbose": True, "threads": 2, "depth": None},
            )
        ]
        * 2
    )


@pytest.mark.parametrize("option", ["--out", "-o"])
@pytest.mark.parametrize("filename", ["no-suffix", "file.xml", "file.json.bak", ""])
def test_cli_reports_exporter_suffix_error(
    monkeypatch, tmp_path, filename, option, capsys
):
    target = tmp_path / "app.exe"
    target.write_bytes(b"")
    monkeypatch.setattr(
        cli, "build_dependency_graph", lambda *args, **kwargs: DependencyGraph()
    )
    monkeypatch.setattr(sys, "argv", ["win_depends", str(target), option, filename])
    with pytest.raises(
        ValueError, match="supported formats: .csv, .json, .html, .dot, .txt"
    ):
        cli.main()
    output = capsys.readouterr()
    assert "written to" not in output.out


@pytest.mark.parametrize(
    "options",
    [
        ["--graph"],
        ["--dot", "old.dot"],
        ["--graph", "--dot", "old.dot"],
        ["--check-missing"],
        ["--check-invalid"],
        ["--check-orphan"],
        ["--tree"],
        ["--out"],
        ["-o"],
    ],
)
def test_cli_removed_options_and_missing_output_argument(monkeypatch, options, capsys):
    monkeypatch.setattr(sys, "argv", ["win_depends", "app.exe", *options])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert capsys.readouterr().err


@pytest.mark.parametrize("failure", ["parent", "directory", "permission", "encoding"])
def test_cli_export_failures_are_nonzero(monkeypatch, tmp_path, capsys, failure):
    target = tmp_path / "app.exe"
    target.write_bytes(b"")
    destination = tmp_path / "output.json"
    graph = DependencyGraph()
    if failure == "parent":
        destination = tmp_path / "absent" / "output.json"
    elif failure == "directory":
        destination.mkdir()
    elif failure == "encoding":
        graph.add_node("\ud800.dll")
    else:

        def fail(*args, **kwargs):
            raise PermissionError("permission denied")

        monkeypatch.setattr(exporter.os, "replace", fail)
    monkeypatch.setattr(cli, "build_dependency_graph", lambda *args, **kwargs: graph)
    monkeypatch.setattr(
        sys, "argv", ["win_depends", str(target), "--out", str(destination)]
    )
    error = {
        "parent": FileNotFoundError,
        "directory": OSError,
        "permission": PermissionError,
        "encoding": UnicodeError,
    }[failure]
    with pytest.raises(error):
        cli.main()
    output = capsys.readouterr()
    assert "written to" not in output.out and "Total time" not in output.out
    assert not destination.is_file()
    assert not list(tmp_path.glob(".win-depends-*.tmp"))


def test_cli_empty_directory_exports_real_empty_graph(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "build_dependency_graph", core.build_dependency_graph)
    output = tmp_path / "empty.json"
    monkeypatch.setattr(
        sys, "argv", ["win_depends", str(tmp_path), "--out", str(output)]
    )
    cli.main()
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document == {
        "schema_version": 1,
        "entry_points": [],
        "nodes": [],
        "edges": [],
    }
    assert "written to" in capsys.readouterr().out


def test_cli_invalid_target_preserves_error_exit(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["win_depends", str(tmp_path / "absent.exe")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert "not a valid DLL/EXE" in capsys.readouterr().out


@pytest.mark.parametrize("depth_option", ["--depth", "-d"])
@pytest.mark.parametrize("verbose_option", ["--verbose", "-V"])
@pytest.mark.parametrize("threads_option", ["--threads", "-t"])
def test_cli_analysis_options(
    monkeypatch, tmp_path, depth_option, verbose_option, threads_option
):
    target = tmp_path / "app.exe"
    target.write_bytes(b"")
    calls = []

    def fake_build(path, **options):
        calls.append(options)
        return DependencyGraph()

    monkeypatch.setattr(cli, "build_dependency_graph", fake_build)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "win_depends",
            str(target),
            depth_option,
            "0",
            verbose_option,
            threads_option,
            "2",
            "--print-tree",
        ],
    )
    cli.main()
    assert calls == [
        {"depth": 0, "verbose": True, "detect_system": False, "threads": 2}
    ]


def test_cli_negative_depth_rejected_before_analysis(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["win_depends", "app.exe", "-d", "-1"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
