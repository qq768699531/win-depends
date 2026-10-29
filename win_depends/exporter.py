"""Complete graph exports using the version 1 data model documented in README."""

import csv
import html
import io
import json
import os
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from pyvis.network import Network

from .edgedata import EdgeData
from .graph import DependencyGraph

__all__ = ["export"]

FORMATS = ("csv", "json", "html", "dot", "txt")
NODE_FIELDS = (
    "id",
    "path",
    "name",
    "is_system",
    "is_forward",
    "is_virtual",
    "is_orphan",
    "forward_to",
)
EDGE_FIELDS = ("source", "target", "is_missing", "is_valid", "is_delay", "in_cycle")
CSV_FIELDS = ("record_type", *NODE_FIELDS, "is_entry_point", *EDGE_FIELDS)


def _output_format(filename):
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in FORMATS:
        raise ValueError(
            "Unsupported output extension; supported formats: "
            + ", ".join(f".{name}" for name in FORMATS)
        )
    return suffix


def _graph_document(graph: DependencyGraph):
    g = graph.graph
    nodes = []
    for path in sorted(g.nodes):
        data = g.nodes[path]["data"]
        nodes.append(
            {
                "id": path,
                "path": path,
                "name": os.path.basename(path),
                "is_system": data.is_system,
                "is_forward": data.is_forward,
                "is_virtual": data.is_virtual,
                "is_orphan": data.is_orphan,
                "forward_to": sorted(set(data.forward_to)),
            }
        )
    edges = []
    for source, target in sorted(g.edges):
        data = g.edges[source, target]["data"]
        edges.append(
            {
                "source": source,
                "target": target,
                "is_missing": data.is_missing,
                "is_valid": data.is_valid,
                "is_delay": data.is_delay,
                "in_cycle": data.in_cycle,
            }
        )
    return {
        "schema_version": 1,
        "entry_points": sorted(set(g.graph.get("entry_points", [])) & set(g.nodes)),
        "nodes": nodes,
        "edges": edges,
    }


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _cell(value):
    return value if isinstance(value, str) else _json(value)


def _nodes_with_entry_points(document):
    entry_points = set(document["entry_points"])
    return [
        {**node, "is_entry_point": node["id"] in entry_points}
        for node in document["nodes"]
    ]


def _csv(document):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for kind, records in (
        ("node", _nodes_with_entry_points(document)),
        ("edge", document["edges"]),
    ):
        for record in records:
            writer.writerow(
                {"record_type": kind, **{key: _cell(v) for key, v in record.items()}}
            )
    return stream.getvalue()


def _dot(document):
    lines = ["digraph G {"]
    for node in _nodes_with_entry_points(document):
        attrs = {key: value for key, value in node.items() if key not in {"id", "name"}}
        attrs["label"] = node["name"]
        attributes = ", ".join(f"{key}={_json(_cell(v))}" for key, v in attrs.items())
        lines.append(f"    {_json(node['id'])} [{attributes}];")
    for edge in document["edges"]:
        data = EdgeData(**{key: edge[key] for key in EDGE_FIELDS[2:]})
        attrs = {key: edge[key] for key in EDGE_FIELDS[2:]}
        attrs.update(label=" ".join(data.status_flags()), color=data.status_color())
        if data.is_delay and data.status_color() == "blue":
            attrs["style"] = "dashed"
        attributes = ", ".join(f"{key}={_json(_cell(v))}" for key, v in attrs.items())
        lines.append(
            f"    {_json(edge['source'])} -> {_json(edge['target'])} [{attributes}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _html_title(value):
    details = json.dumps(value, ensure_ascii=False, indent=2)
    # PyVis switches hover templates when the raw title contains "href".
    escaped = html.escape(details, quote=True).replace("href", "h&#114;ef")
    return "<pre>" + escaped + "</pre>"


def _html(document):
    network = Network(
        height="78vh",
        width="100%",
        directed=True,
        bgcolor="#f8fafc",
        font_color="#172033",
        cdn_resources="in_line",
    )
    options = json.loads(
        files("win_depends").joinpath("pyvis_options.json").read_text(encoding="utf-8")
    )
    network.set_options(json.dumps(options))

    node_ids = {node["id"]: index for index, node in enumerate(document["nodes"])}
    incoming_missing = {
        edge["target"] for edge in document["edges"] if edge["is_missing"]
    }
    entry_points = set(document["entry_points"])
    connected = {
        endpoint
        for edge in document["edges"]
        for endpoint in (edge["source"], edge["target"])
    }
    for node in document["nodes"]:
        if node["id"] in incoming_missing:
            background, border = "#fee2e2", "#dc2626"
        elif node["is_virtual"]:
            background, border = "#ede9fe", "#7c3aed"
        elif node["is_orphan"]:
            background, border = "#dcfce7", "#16a34a"
        elif node["is_system"]:
            background, border = "#e2e8f0", "#64748b"
        else:
            background, border = "#e0f2fe", "#0369a1"
        is_entry = node["id"] in entry_points
        is_isolated = node["id"] not in connected
        network.add_node(
            node_ids[node["id"]],
            label=node["name"],
            shape="box",
            title=_html_title(node),
            color={
                "background": background,
                "border": "#0f172a" if is_entry else border,
                "highlight": {"background": background, "border": "#2563eb"},
                "hover": {"background": background, "border": border},
            },
            borderWidth=3 if is_entry else 1,
            shapeProperties={"borderDashes": is_isolated},
        )
    for edge in document["edges"]:
        if edge["is_missing"]:
            color = "#dc2626"
        elif not edge["is_valid"]:
            color = "#b45309"
        elif edge["in_cycle"]:
            color = "#9333ea"
        else:
            color = "#64748b"
        network.add_edge(
            node_ids[edge["source"]],
            node_ids[edge["target"]],
            title=_html_title(edge),
            color=color,
            width=1.5,
            dashes=edge["is_delay"],
        )

    return network.generate_html()


def _txt(document):
    lines = [
        "Dependency graph (schema version 1)",
        "Direction: importer -> dependency",
        f"Entry points: {_json(document['entry_points'])}",
        "",
        f"Nodes ({len(document['nodes'])}):",
    ]
    for node in _nodes_with_entry_points(document):
        lines.append("  " + "; ".join(f"{key}={_json(v)}" for key, v in node.items()))
    lines.extend(["", f"Dependencies ({len(document['edges'])}):"])
    for edge in document["edges"]:
        attrs = "; ".join(f"{key}={_cell(edge[key])}" for key in EDGE_FIELDS[2:])
        lines.append(f"  {_json(edge['source'])} -> {_json(edge['target'])}; {attrs}")
    return "\n".join(lines) + "\n"


def export(graph: DependencyGraph, filename):
    """Serialize before touching disk; replace the destination only on success."""
    fmt = _output_format(filename)
    document = _graph_document(graph)
    if fmt == "json":
        text = (
            json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        )
    else:
        text = {"csv": _csv, "html": _html, "dot": _dot, "txt": _txt}[fmt](document)
    payload = text.encode("utf-8")
    destination = Path(filename)
    staging = destination.with_name(f".win-depends-{uuid4().hex}.tmp")
    created = False
    try:
        with staging.open("xb") as stream:
            created = True
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, destination)
    finally:
        if created:
            try:
                staging.unlink()
            except FileNotFoundError:
                pass
