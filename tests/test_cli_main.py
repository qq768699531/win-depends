import sys
from win_depends import cli
import win_depends.core as core
from win_depends.graph import DependencyGraph


def test_cli_main_basic(monkeypatch, tmp_path, capsys):
    f = tmp_path / "a.dll"
    f.write_text("x")

    def fake_build(path, detect_system=False, verbose=False, threads=16):
        return DependencyGraph()

    monkeypatch.setattr(core, "build_dependency_graph", fake_build)
    monkeypatch.setattr(sys, "argv", ["win_depends", str(f)])

    # call main (should not raise)
    cli.main()
    out = capsys.readouterr().out
    assert "Analyzing dependencies in" in out
