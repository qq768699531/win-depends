import os
from collections import defaultdict
from .node import DependencyNode
from .edge import DependencyEdge


class DependencyGraph:
    def __init__(self):
        self.children = defaultdict(list[DependencyNode])
        self.parents = defaultdict(list[DependencyNode])
        self.nodes = {}
        self.edges = {}

    def add_edge(
        self,
        parent_path: str,
        child_path: str,
        is_delay=False,
        is_missing=False,
        is_valid=True,
    ):
        parent = self.get_node(parent_path)
        child = self.get_node(child_path)
        key = (parent, child)
        self.edges[key] = DependencyEdge(parent, child, is_delay, is_missing, is_valid)
        self.children[parent].append(child)
        self.parents[child].append(parent)

    def get_node(self, path: str) -> DependencyNode:
        if path not in self.nodes:
            self.nodes[path] = DependencyNode(path, False)
        return self.nodes[path]

    def _mark_cycles(self):
        for edge in self.edges.values():
            edge.in_cycle = False
        visited = set()
        stack = []

        def dfs(node):
            if node in stack:
                idx = stack.index(node)
                cycle_path = stack[idx:] + [node]
                if len(cycle_path) > 2:
                    for i in range(len(cycle_path) - 1):
                        edge = self.edges.get((cycle_path[i], cycle_path[i + 1]))
                        if edge:
                            edge.in_cycle = True
                return
            if node in visited:
                return
            visited.add(node)
            stack.append(node)
            for child in self.children.get(node, []):
                dfs(child)
            stack.pop()

        for node in self.nodes.values():
            if node not in visited:
                dfs(node)

    def print_tree(self, max_depth=8):
        self._mark_cycles()
        roots = [n for n in self.nodes.values() if not self.parents[n]]
        visited = set()

        def node_label(node, parent=None):
            label = str(node)
            if parent:
                edge = self.edges.get((parent, node))
                if edge:
                    label += "".join(sorted(edge.status_emojis()))
            return label

        def recurse(node, prefix="", is_last=True, depth=0, path=None, parent=None):
            if path is None:
                path = set()
            print(
                f"{prefix}{'└── ' if is_last else '├── '}{node_label(node, parent)}",
                flush=True,
            )
            if node in path or (max_depth and depth >= max_depth):
                return
            path.add(node)
            children = self.children.get(node, [])
            for i, child in enumerate(children):
                recurse(
                    child,
                    prefix + ("    " if is_last else "│   "),
                    i == len(children) - 1,
                    depth + 1,
                    path,
                    node,
                )
            path.remove(node)
            visited.add(node)

        nodes_to_print = (
            roots if roots else [n for n in self.nodes.values() if n not in visited]
        )
        for i, node in enumerate(nodes_to_print):
            if node not in visited:
                recurse(node, "", i == len(nodes_to_print) - 1, 0, None, None)

    def export_dot(self):
        lines = ["digraph G {"]
        for edge in self.edges.values():
            attrs = []
            status = " ".join(edge.status_flags())
            color = edge.status_color()
            if color and color != "black":
                attrs.append(f'color="{color}"')
            if edge.delay_loaded and color == "blue":
                attrs.append('style="dashed"')
            if status:
                attrs.append(f'label="{status}"')
            attr_str = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(
                f'    "{os.path.basename(edge.parent.name)}" -> "{os.path.basename(edge.child.name)}"{attr_str};'
            )
        lines.append("}")
        return "\n".join(lines)
