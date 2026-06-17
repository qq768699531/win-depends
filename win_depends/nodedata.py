import os


class NodeData:
    def __init__(
        self,
        *,
        is_system: bool = False,
        is_forward: bool = False,
        forward_to: list[str] | None = None,
        is_virtual: bool = False,
        is_orphan: bool = False,
    ):
        self.is_system = is_system
        self.is_forward = is_forward
        self.forward_to = list(forward_to) if forward_to else []
        self.is_virtual = is_virtual
        self.is_orphan = is_orphan

    def label(self, path: str):
        flags = []
        if self.is_forward and self.forward_to:
            flags.append(f" -> {', '.join(self.forward_to)} ")
        if self.is_system:
            flags.append("[SYS]")
        if self.is_orphan:
            flags.append("(orphan)")
        return f"{os.path.basename(path)}{''.join(flags)}"
