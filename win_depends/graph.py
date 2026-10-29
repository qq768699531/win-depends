import networkx

from .edgedata import EdgeData
from .nodedata import NodeData


class DependencyGraph:
    def __init__(self):
        self._g = networkx.DiGraph()

    @property
    def graph(self):
        return self._g

    def ensure_node(self, path: str):
        if path not in self._g:
            self._g.add_node(path, data=NodeData())
        elif "data" not in self._g.nodes[path]:
            self._g.nodes[path]["data"] = NodeData()
        return path

    def node_data(self, path: str):
        self.ensure_node(path)
        return self._g.nodes[path]["data"]

    def detect_cycle(self):
        components = {
            path: index
            for index, members in enumerate(
                networkx.strongly_connected_components(self._g)
            )
            for path in members
        }
        for src, dst, attrs in self._g.edges(data=True):
            attrs["data"].in_cycle = components[src] == components[dst]

    @staticmethod
    def should_include(*, edge_data: EdgeData, is_system: bool, detect_system: bool):
        return not (is_system and not detect_system and not edge_data.is_missing)

    @staticmethod
    def should_expand(*, node_data: NodeData, edge_data: EdgeData):
        return (not edge_data.is_missing) and (not node_data.is_virtual)

    def add_node(self, path: str, data: NodeData | None = None):
        self.ensure_node(path)
        if data is not None:
            self._g.nodes[path]["data"] = data
        return path

    def add_edge(self, src: str, dst: str, data: EdgeData | None = None):
        self.ensure_node(src)
        self.ensure_node(dst)
        data = data or EdgeData()
        if self._g.has_edge(src, dst):
            data.is_delay = data.is_delay and self._g.edges[src, dst]["data"].is_delay
        self._g.add_edge(src, dst, data=data)
        return (src, dst)
