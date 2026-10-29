import csv
import html
import io
import json
import re
from importlib.resources import files
from pathlib import Path

import html5lib
import pydot
import pytest

from win_depends import exporter
from win_depends.edgedata import EdgeData
from win_depends.graph import DependencyGraph
from win_depends.nodedata import NodeData
from win_depends.printer import print_invalid, print_missing, print_orphan, print_tree


@pytest.fixture
def rich_graph():
    graph = DependencyGraph()
    root = 'C:\\路径\\app,"<&>\r\n.exe'
    first, second = r"C:\one\same.dll", r"C:\two\same.dll"
    virtual = 'api-ms-</script><img src=x onerror="bad">&.dll'
    graph.add_node(
        first,
        NodeData(
            is_system=True,
            is_forward=True,
            forward_to=['目标,"<&>\r\n.dll', r"C:\host.dll", r"C:\host.dll"],
        ),
    )
    graph.add_node(virtual, NodeData(is_virtual=True, is_forward=True))
    graph.add_node(r"C:\孤立\orphan.dll", NodeData(is_orphan=True))
    graph.add_edge(root, first)
    graph.add_edge(first, second, EdgeData(is_delay=True))
    graph.add_edge(second, first)
    graph.add_edge(second, second)
    graph.add_edge(second, virtual, EdgeData(is_valid=False))
    graph.add_edge(first, "missing.dll", EdgeData(is_missing=True, is_valid=False))
    graph.add_edge(virtual, "optional.dll", EdgeData(is_missing=True, is_delay=True))
    graph.graph.graph["entry_points"] = [root]
    graph.detect_cycle()
    return graph


def read_export(graph, tmp_path, fmt):
    target = tmp_path / f"dependencies.{fmt}"
    exporter.export(graph, target)
    return target.read_bytes().decode("utf-8")


def html_payload(text, name):
    match = re.search(rf"{name} = new vis\.DataSet\((.*?)\);", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def html_options(text):
    start = text.index("var options = ", text.index("edges = new vis.DataSet"))
    end = text.index(";", start)
    return json.loads(text[start + len("var options = ") : end])


def html_title_record(title):
    assert title.startswith("<pre>") and title.endswith("</pre>")
    return json.loads(html.unescape(title[5:-6]))


def test_json_schema_and_all_attributes(rich_graph, tmp_path):
    text = read_export(rich_graph, tmp_path, "json")
    document = json.loads(text)
    assert set(document) == {"schema_version", "entry_points", "nodes", "edges"}
    assert document["schema_version"] == 1
    assert document["entry_points"] == ['C:\\路径\\app,"<&>\r\n.exe']
    nodes = {node["id"]: node for node in document["nodes"]}
    assert set(nodes) == set(rich_graph.graph)
    assert len({node["id"] for node in document["nodes"]}) == len(document["nodes"])
    assert [node["id"] for node in document["nodes"]] == sorted(nodes)
    for node in document["nodes"]:
        assert set(node) == set(exporter.NODE_FIELDS)
        assert node["id"] == node["path"]
        assert isinstance(node["name"], str)
        for key in ("is_system", "is_forward", "is_virtual", "is_orphan"):
            assert type(node[key]) is bool
        assert isinstance(node["forward_to"], list)
        assert node["forward_to"] == sorted(set(node["forward_to"]))
    assert nodes[r"C:\one\same.dll"]["name"] == nodes[r"C:\two\same.dll"]["name"]
    assert nodes[r"C:\one\same.dll"]["is_system"]
    assert nodes[r"C:\one\same.dll"]["is_forward"]
    assert nodes[r"C:\孤立\orphan.dll"]["is_orphan"]
    assert any(node["is_virtual"] for node in document["nodes"])
    assert "路径" in text
    edges = document["edges"]
    assert [(e["source"], e["target"]) for e in edges] == sorted(rich_graph.graph.edges)
    for edge in edges:
        assert set(edge) == set(exporter.EDGE_FIELDS)
        assert edge["source"] in nodes and edge["target"] in nodes
        assert all(type(edge[key]) is bool for key in exporter.EDGE_FIELDS[2:])
        expected_cycle = edge["source"] in {
            r"C:\one\same.dll",
            r"C:\two\same.dll",
        } and edge["target"] in {r"C:\one\same.dll", r"C:\two\same.dll"}
        assert edge["in_cycle"] == expected_cycle
    assert any(e["is_missing"] and e["is_delay"] for e in edges)
    assert any(not e["is_valid"] and not e["is_missing"] for e in edges)


def test_csv_round_trip_schema_and_crlf(rich_graph, tmp_path):
    text = read_export(rich_graph, tmp_path, "csv")
    rows = list(csv.DictReader(io.StringIO(text, newline="")))
    document = exporter._graph_document(rich_graph)
    assert tuple(rows[0]) == exporter.CSV_FIELDS
    assert len(rows) == len(document["nodes"]) + len(document["edges"])
    assert all(None not in row and None not in row.values() for row in rows)
    for row, node in zip(rows, document["nodes"]):
        assert row["record_type"] == "node"
        assert {k: row[k] for k in ("id", "path", "name")} == {
            k: node[k] for k in ("id", "path", "name")
        }
        assert json.loads(row["forward_to"]) == node["forward_to"]
        for key in ("is_system", "is_forward", "is_virtual", "is_orphan"):
            assert json.loads(row[key]) is node[key]
        assert json.loads(row["is_entry_point"]) == (
            node["id"] in document["entry_points"]
        )
        assert all(row[k] == "" for k in exporter.EDGE_FIELDS)
    for row, edge in zip(rows[len(document["nodes"]) :], document["edges"]):
        assert row["record_type"] == "edge"
        assert all(row[k] == "" for k in (*exporter.NODE_FIELDS, "is_entry_point"))
        assert row["source"] == edge["source"] and row["target"] == edge["target"]
        assert all(json.loads(row[k]) is edge[k] for k in exporter.EDGE_FIELDS[2:])
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")
    assert '""' in text


def test_html_parses_and_preserves_data(rich_graph, tmp_path):
    text = read_export(rich_graph, tmp_path, "html")
    parser = html5lib.HTMLParser(strict=False, namespaceHTMLElements=False)
    document = parser.parse(text)
    assert document.find("head/meta").attrib["charset"] == "utf-8"
    assert document.find("body") is not None
    assert not any(
        any(key.lower().startswith("on") for key in element.attrib)
        for element in document.iter()
    )
    external_resources = [
        value
        for element in document.iter()
        for key in ("src", "href")
        if (value := element.attrib.get(key, "")).startswith("http")
    ]
    assert len(external_resources) == 2
    assert all("cdn.jsdelivr.net/npm/bootstrap" in url for url in external_resources)
    model = exporter._graph_document(rich_graph)
    nodes = html_payload(text, "nodes")
    edges = html_payload(text, "edges")
    assert len(nodes) == len(model["nodes"])
    assert len(edges) == len(model["edges"])
    assert [node["label"] for node in nodes] == [
        node["name"] for node in model["nodes"]
    ]
    assert [html_title_record(node["title"]) for node in nodes] == model["nodes"]
    assert [html_title_record(edge["title"]) for edge in edges] == model["edges"]
    assert '"arrows": {"to": {"enabled": true, "scaleFactor": 0.65}}' in text


def test_dot_parser_preserves_nodes_references_and_attributes(rich_graph, tmp_path):
    text = read_export(rich_graph, tmp_path, "dot")
    parsed = pydot.graph_from_dot_data(text)
    assert parsed is not None and len(parsed) == 1
    graph = parsed[0]
    assert graph.get_type() == "digraph"
    nodes = {
        json.loads(node.get_name()): node.get_attributes()
        for node in graph.get_nodes()
        if node.get_name().startswith('"')
    }
    model = exporter._graph_document(rich_graph)
    assert set(nodes) == set(rich_graph.graph)
    for node in exporter._nodes_with_entry_points(model):
        attrs = nodes[node["id"]]
        for key, value in node.items():
            if key != "id":
                attribute = "label" if key == "name" else key
                assert json.loads(attrs[attribute]) == exporter._cell(value)
    edges = {
        (json.loads(edge.get_source()), json.loads(edge.get_destination())): edge
        for edge in graph.get_edges()
    }
    assert set(edges) == set(rich_graph.graph.edges)
    for edge in model["edges"]:
        attrs = edges[edge["source"], edge["target"]].get_attributes()
        assert all(
            json.loads(attrs[k]) == exporter._cell(edge[k])
            for k in exporter.EDGE_FIELDS[2:]
        )


def test_txt_layout_and_quoted_values(rich_graph, tmp_path):
    text = read_export(rich_graph, tmp_path, "txt")
    model = exporter._graph_document(rich_graph)
    assert text.startswith("Dependency graph (schema version 1)\n")
    nodes, edges = text.split(f"\nDependencies ({len(model['edges'])}):\n")
    node_rows = nodes.split(f"Nodes ({len(model['nodes'])}):\n")[1].splitlines()
    edge_rows = edges.splitlines()
    assert len(node_rows) == len(model["nodes"])
    assert len(edge_rows) == len(model["edges"])
    for row, node in zip(node_rows, model["nodes"]):
        assert row.startswith(f"  id={json.dumps(node['id'], ensure_ascii=False)};")
        assert all(
            f"{key}=" in row for key in (*exporter.NODE_FIELDS, "is_entry_point")
        )
    for row, edge in zip(edge_rows, model["edges"]):
        assert row.startswith(
            f"  {json.dumps(edge['source'], ensure_ascii=False)} -> "
            f"{json.dumps(edge['target'], ensure_ascii=False)};"
        )
        assert all(f"{key}=" in row for key in exporter.EDGE_FIELDS[2:])


@pytest.mark.parametrize("fmt", exporter.FORMATS)
@pytest.mark.parametrize("isolated", [False, True])
def test_empty_and_isolated_graphs(fmt, isolated, tmp_path):
    graph = DependencyGraph()
    if isolated:
        graph.add_node("孤立.dll", NodeData(is_orphan=True))
    text = read_export(graph, tmp_path, fmt)
    if fmt == "html":
        assert len(html_payload(text, "nodes")) == int(isolated)
        if isolated:
            assert html_title_record(html_payload(text, "nodes")[0]["title"])["id"] == (
                "孤立.dll"
            )
    else:
        assert ("孤立.dll" in text) == isolated
    if fmt == "json":
        model = json.loads(text)
        assert len(model["nodes"]) == int(isolated)
        assert model["edges"] == [] and model["entry_points"] == []
    elif fmt == "csv":
        assert len(list(csv.reader(io.StringIO(text)))) == 1 + int(isolated)
    elif fmt == "dot":
        parsed = pydot.graph_from_dot_data(text)[0]
        assert len(parsed.get_edges()) == 0
        assert len(
            [n for n in parsed.get_nodes() if n.get_name().startswith('"')]
        ) == int(isolated)
    elif fmt == "html":
        html5lib.HTMLParser(strict=False).parse(text)
    else:
        assert f"Nodes ({int(isolated)}):" in text and "Dependencies (0):" in text


@pytest.mark.parametrize("fmt", exporter.FORMATS)
def test_case_insensitive_deterministic_and_report_independent(
    rich_graph, tmp_path, fmt, capsys
):
    original = read_export(rich_graph, tmp_path, fmt)
    print_missing(rich_graph)
    print_invalid(rich_graph)
    print_orphan(rich_graph)
    print_tree(rich_graph)
    capsys.readouterr()
    assert read_export(rich_graph, tmp_path, fmt.upper()) == original
    reversed_graph = DependencyGraph()
    for path in reversed(list(rich_graph.graph)):
        reversed_graph.add_node(path, rich_graph.node_data(path))
    for source, target in reversed(list(rich_graph.graph.edges)):
        reversed_graph.add_edge(
            source, target, rich_graph.graph.edges[source, target]["data"]
        )
    reversed_graph.graph.graph.update(rich_graph.graph.graph)
    assert read_export(reversed_graph, tmp_path, fmt) == original
    rich_graph.add_node("earlier-than-some-IDs.dll")
    model = exporter._graph_document(rich_graph)
    assert {node["id"] for node in model["nodes"]} >= set(reversed_graph.graph)


@pytest.mark.parametrize("suffix", ["", ".xml", ".json.bak", "."])
def test_unsupported_format_never_touches_existing_file(tmp_path, suffix):
    target = tmp_path / f"output{suffix}"
    target.write_bytes(b"keep")
    with pytest.raises(
        ValueError, match="supported formats: .csv, .json, .html, .dot, .txt"
    ):
        exporter.export(DependencyGraph(), target)
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "failure", ["open", "write", "flush", "fsync", "replace", "encoding"]
)
def test_atomic_failures_leave_destination_untouched(
    monkeypatch, tmp_path, existing, failure
):
    target = tmp_path / "output.json"
    if existing:
        target.write_bytes(b"keep")
    graph = DependencyGraph()

    def fail(*args, **kwargs):
        raise OSError("simulated failure")

    if failure in {"open", "write", "flush"}:
        original_open = Path.open

        class FailingStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def write(self, payload):
                self.stream.write(payload[:4])
                if failure == "write":
                    fail()

            def flush(self):
                fail()

        def fake_open(path, mode="r", *args, **kwargs):
            if mode != "xb":
                return original_open(path, mode, *args, **kwargs)
            if failure == "open":
                raise PermissionError("simulated permission denial")
            return FailingStream(original_open(path, mode, *args, **kwargs))

        monkeypatch.setattr(Path, "open", fake_open)
    elif failure == "encoding":
        graph.add_node("unpaired-surrogate-\ud800.dll")
    else:
        monkeypatch.setattr(exporter.os, failure, fail)
    with pytest.raises((OSError, UnicodeError)):
        exporter.export(graph, target)
    assert target.exists() == existing
    if existing:
        assert target.read_bytes() == b"keep"
    assert not list(tmp_path.glob(".win-depends-*.tmp"))


def test_success_replaces_existing_file(tmp_path):
    target = tmp_path / "output.json"
    target.write_bytes(b"old")
    exporter.export(DependencyGraph(), target)
    assert json.loads(target.read_text(encoding="utf-8"))["nodes"] == []
    assert not list(tmp_path.glob(".win-depends-*.tmp"))


def test_cycle_flags_are_recomputed_for_self_loops_and_removed_cycles():
    graph = DependencyGraph()
    graph.add_edge("a", "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", "b")
    graph.add_edge("c", "tail")
    graph.detect_cycle()
    exporter._graph_document(graph)
    assert {
        (s, t) for s, t, attrs in graph.graph.edges(data=True) if attrs["data"].in_cycle
    } == {("a", "a"), ("b", "c"), ("c", "b")}
    graph.graph.remove_edge("c", "b")
    graph.detect_cycle()
    model = exporter._graph_document(graph)
    assert sum(edge["in_cycle"] for edge in model["edges"]) == 1


def test_staging_name_collision_does_not_remove_existing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "uuid4", lambda: type("UUID", (), {"hex": "fixed"})())
    staging = tmp_path / ".win-depends-fixed.tmp"
    staging.write_bytes(b"not ours")
    with pytest.raises(FileExistsError):
        exporter.export(DependencyGraph(), tmp_path / "output.json")
    assert staging.read_bytes() == b"not ours"


@pytest.mark.parametrize("value", ['comma,"quote"', "LF\nline", "CR\rline", "制表\t符"])
def test_csv_embedded_special_characters_round_trip(tmp_path, value):
    graph = DependencyGraph()
    graph.add_node(value)
    text = read_export(graph, tmp_path, "csv")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    rows = list(reader)
    assert len(rows) == 2
    assert len(rows[0]) == len(rows[1]) == len(exporter.CSV_FIELDS)
    assert rows[1][1] == rows[1][2] == value
    assert text.endswith("\r\n")


@pytest.mark.parametrize(
    "path",
    [
        "line\ncarriage\rnull\x00control\x01tab\t.dll",
        "DEL\x7fC1\x85noncharacter\ufdd0\uffff\U0001fffe.dll",
        "路径😀.dll",
    ],
)
def test_html_control_characters_use_valid_unambiguous_json(tmp_path, path):
    graph = DependencyGraph()
    graph.add_node(path)
    text = read_export(graph, tmp_path, "html")
    parser = html5lib.HTMLParser(strict=False, namespaceHTMLElements=False)
    parser.parse(text)
    node = html_payload(text, "nodes")[0]
    assert node["label"] == path
    assert html_title_record(node["title"])["id"] == path


def test_html_pyvis_payload_contains_nodes_edges_and_status_styles(
    rich_graph, tmp_path
):
    text = read_export(rich_graph, tmp_path, "html")
    parser = html5lib.HTMLParser(strict=False, namespaceHTMLElements=False)
    parser.parse(text)
    model = exporter._graph_document(rich_graph)
    nodes = html_payload(text, "nodes")
    edges = html_payload(text, "edges")
    assert len(nodes) == len(model["nodes"]) == 7
    assert len(edges) == len(model["edges"]) == 7
    assert [node["id"] for node in nodes] == list(range(len(nodes)))
    assert [html_title_record(node["title"]) for node in nodes] == model["nodes"]
    assert [html_title_record(edge["title"]) for edge in edges] == model["edges"]
    node_by_path = {html_title_record(node["title"])["id"]: node for node in nodes}
    edge_by_pair = {
        (
            html_title_record(edge["title"])["source"],
            html_title_record(edge["title"])["target"],
        ): edge
        for edge in edges
    }
    node_id_by_path = {
        html_title_record(node["title"])["id"]: node["id"] for node in nodes
    }
    assert all(edge["arrows"] == "to" for edge in edges)
    for (source, target), edge in edge_by_pair.items():
        assert edge["from"] == node_id_by_path[source]
        assert edge["to"] == node_id_by_path[target]
    assert (
        node_by_path[r"C:\one\same.dll"]["id"] != node_by_path[r"C:\two\same.dll"]["id"]
    )
    assert node_by_path[r"C:\孤立\orphan.dll"]["shapeProperties"] == {
        "borderDashes": True
    }
    assert node_by_path[r"C:\one\same.dll"]["color"]["background"] == "#e2e8f0"
    assert node_by_path["missing.dll"]["color"]["background"] == "#fee2e2"
    assert edge_by_pair[(r"C:\one\same.dll", r"C:\two\same.dll")]["dashes"]
    assert edge_by_pair[(r"C:\one\same.dll", "missing.dll")]["color"] == "#dc2626"
    assert (
        edge_by_pair[
            (r"C:\two\same.dll", 'api-ms-</script><img src=x onerror="bad">&.dll')
        ]["color"]
        == "#b45309"
    )
    assert edge_by_pair[(r"C:\two\same.dll", r"C:\one\same.dll")]["color"] == (
        "#9333ea"
    )


def test_pyvis_options_load_from_bundled_package_json(tmp_path):
    resource = files("win_depends").joinpath("pyvis_options.json")
    assert resource.is_file()
    options = json.loads(resource.read_text(encoding="utf-8"))
    rendered = read_export(DependencyGraph(), tmp_path, "html")
    assert html_options(rendered) == options
    assert options["layout"]["hierarchical"]["direction"] == "LR"
    assert options["physics"]["stabilization"]["iterations"] == 300
    assert options["interaction"]["navigationButtons"]


def test_html_script_injection_is_inert_and_round_trips(tmp_path):
    value = '</script><script>alert("bad")</script><svg onload="bad">&\u2028\u2029'
    graph = DependencyGraph()
    graph.add_edge(value, "other")
    text = read_export(graph, tmp_path, "html")
    parser = html5lib.HTMLParser(strict=False, namespaceHTMLElements=False)
    tree = parser.parse(text)
    baseline = read_export(DependencyGraph(), tmp_path, "html")
    baseline_tree = html5lib.HTMLParser(
        strict=False, namespaceHTMLElements=False
    ).parse(baseline)
    assert len(tree.findall(".//script")) == len(baseline_tree.findall(".//script"))
    nodes = html_payload(text, "nodes")
    assert nodes[0]["label"] == 'script><svg onload="bad">&\u2028\u2029'
    title = nodes[0]["title"]
    assert html_title_record(title)["id"] == value
    assert "&lt;/script&gt;" in title
    assert '</script><script>alert("bad")' not in text
    assert not tree.findall(".//img")
    assert not any(
        key.lower().startswith("on")
        for element in tree.iter()
        for key in element.attrib
    )


def test_html_full_sized_graph_has_no_truncated_edges(tmp_path):
    graph = DependencyGraph()
    for index in range(304):
        graph.add_node(f"binary-{index:03}.dll")
    pairs = (
        (f"binary-{source:03}.dll", f"binary-{target:03}.dll")
        for source in range(304)
        for target in range(source + 1, min(source + 8, 304))
    )
    for index, (source, target) in enumerate(pairs):
        if index == 1707:
            break
        graph.add_edge(source, target)
    text = read_export(graph, tmp_path, "html")
    parser = html5lib.HTMLParser(strict=False, namespaceHTMLElements=False)
    parser.parse(text)
    assert len(html_payload(text, "nodes")) == 304
    assert len(html_payload(text, "edges")) == 1707


def test_dense_cycles_do_not_enumerate_simple_cycles(monkeypatch):
    import networkx

    def fail(*args, **kwargs):
        pytest.fail("cycle flags must not enumerate cycles")

    monkeypatch.setattr(networkx, "simple_cycles", fail)
    graph = DependencyGraph()
    for source in range(20):
        for target in range(20):
            graph.add_edge(str(source), str(target))
    graph.detect_cycle()
    model = exporter._graph_document(graph)
    assert len(model["edges"]) == 400
    assert all(edge["in_cycle"] for edge in model["edges"])


def test_reports_read_finalized_cycles_without_detection(monkeypatch, capsys):
    import networkx

    original = networkx.strongly_connected_components
    calls = []

    def counted(graph):
        calls.append(frozenset(graph.edges))
        return original(graph)

    monkeypatch.setattr(networkx, "strongly_connected_components", counted)
    graph = DependencyGraph()
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")
    graph.detect_cycle()
    print_tree(graph)
    exporter._graph_document(graph)
    assert len(calls) == 1

    # Manual graph mutations require explicit finalization before reporting.
    graph.add_edge("a", "b", EdgeData())
    graph.add_node("isolated")
    graph.detect_cycle()
    assert all(edge["in_cycle"] for edge in exporter._graph_document(graph)["edges"])
    assert len(calls) == 2

    graph.add_node("c")
    graph.graph.remove_edge("b", "a")
    graph.graph.add_edge("b", "c", data=EdgeData())
    graph.detect_cycle()
    assert not any(
        edge["in_cycle"] for edge in exporter._graph_document(graph)["edges"]
    )
    assert len(calls) == 3
    print_tree(graph)
    assert len(calls) == 3
    capsys.readouterr()
