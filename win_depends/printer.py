import os
import networkx as nx
from .graph import DependencyGraph


def _forward_suffix(node_path: str, node_data):
    if node_data.is_forward and node_data.forward_to:
        forward_display = ", ".join(node_data.forward_to)
        if forward_display != node_path:
            return f"  [FORWARD -> {forward_display}]"
    return ""


def _node_label(node_path: str, node_data):
    return node_data.label(node_path)


def _mark_cycle_flags(graph: DependencyGraph):
    g = graph.graph
    for _, _, edge_attrs in g.edges(data=True):
        edge_attrs["data"].in_cycle = False
    for cycle_paths in nx.simple_cycles(g):
        if len(cycle_paths) < 2:
            continue
        cycle_pairs = list(zip(cycle_paths, cycle_paths[1:] + [cycle_paths[0]]))
        for src, dst in cycle_pairs:
            g.edges[src, dst]["data"].in_cycle = True


def print_orphan(graph: DependencyGraph):
    g = graph.graph
    orphans = []
    for node_path, node_attrs in g.nodes(data=True):
        if node_attrs["data"].is_orphan:
            orphans.append(node_path)

    orphans.sort(key=lambda n: n.lower())
    if orphans:
        print("🧩 Orphan DLLs:")
        for node_path in orphans:
            print(f"  🧩 {os.path.basename(node_path)}")
    else:
        print("🧩 No orphan DLLs.")


def print_missing(graph: DependencyGraph):
    g = graph.graph
    missing = []
    for _, child_path, edge_attrs in g.edges(data=True):
        if edge_attrs["data"].is_missing:
            missing.append(child_path)

    missing.sort(key=lambda x: x.lower())
    if not missing:
        print("✅ No missing dependencies.")
        return
    print("❌ Missing dependencies:")
    for node_path in missing:
        node_data = g.nodes[node_path]["data"]
        print(f"  ❌ {os.path.basename(node_path)}{_forward_suffix(node_path, node_data)}")
        for parent_path in g.predecessors(node_path):
            print(f"    ↳ Required by: {os.path.basename(parent_path)}")


def print_invalid(graph: DependencyGraph):
    g = graph.graph
    invalid = []
    for parent_path, child_path, edge_attrs in g.edges(data=True):
        edge_data = edge_attrs["data"]
        if edge_data.is_valid is False and edge_data.is_missing is False:
            invalid.append((parent_path, child_path))

    if not invalid:
        print("✅ No invalid files.")
        return
    print("❗ Invalid files (failed to parse):")
    for parent_path, child_path in invalid:
        parent_name = os.path.basename(parent_path)
        child_name = os.path.basename(child_path)
        child_data = g.nodes[child_path]["data"]
        print(f"  ❗ {parent_name} -> {child_name}{_forward_suffix(child_path, child_data)}")


def print_tree(graph: DependencyGraph, max_depth=8):
    g = graph.graph
    _mark_cycle_flags(graph)
    visited = set()
    depth_limit = None if max_depth is None or max_depth < 0 else max_depth

    def print_from_root(root_path: str):
        dfs_successors = nx.dfs_successors(g, source=root_path, depth_limit=depth_limit)

        def recurse(node_path, prefix="", is_last=True, depth=0, parent_path=None):
            node_data = g.nodes[node_path]["data"]
            label = _node_label(node_path, node_data)
            if parent_path is not None:
                edge_data = g.edges[parent_path, node_path]["data"]
                label += "".join(sorted(edge_data.status_emojis()))
            print(f"{prefix}{'└── ' if is_last else '├── '}{label}", flush=True)
            visited.add(node_path)
            if depth_limit is not None and depth >= depth_limit:
                return
            children = sorted(dfs_successors.get(node_path, []), key=str.lower)
            for i, child_path in enumerate(children):
                recurse(
                    child_path,
                    prefix + ("    " if is_last else "│   "),
                    i == len(children) - 1,
                    depth + 1,
                    node_path,
                )

        recurse(root_path)

    roots = sorted(
        (path for path in g.nodes if g.in_degree(path) == 0),
        key=str.lower,
    )
    start_points = roots or sorted(g.nodes, key=str.lower)
    for root in start_points:
        if root not in visited:
            print_from_root(root)


def export_dot(graph: DependencyGraph):
    g = graph.graph
    lines = ["digraph G {"]
    for src, dst, edge_attrs in g.edges(data=True):
        edge_data = edge_attrs["data"]
        attrs = []
        status = " ".join(edge_data.status_flags())
        color = edge_data.status_color()
        if color and color != "black":
            attrs.append(f'color="{color}"')
        if edge_data.is_delay and color == "blue":
            attrs.append('style="dashed"')
        if status:
            attrs.append(f'label="{status}"')
        attr_str = f" [{', '.join(attrs)}]" if attrs else ""
        lines.append(
            f'    "{os.path.basename(src)}" -> "{os.path.basename(dst)}"{attr_str};'
        )
    lines.append("}")
    return "\n".join(lines)
