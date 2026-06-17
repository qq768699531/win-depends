import os
from functools import lru_cache


class DependencyNode:
    def __init__(self, path: str, is_system: bool):
        # 假定path已为绝对路径
        self.path: str = path
        self.forward_to: str = path
        self.is_forward: bool = False
        self.is_system: bool = is_system
        self.is_orphan: bool = False

    def __repr__(self):
        flags = []
        if self.is_forward:
            flags.append(f" -> {self.forward_to} ")
        if self.is_system:
            flags.append("[SYS]")
        if self.is_orphan:
            flags.append("(orphan)")
        return f"{os.path.basename(self.path)}{''.join(flags)}"

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return isinstance(other, DependencyNode) and self.path == other.path
