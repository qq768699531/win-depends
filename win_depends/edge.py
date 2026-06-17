import os


class DependencyEdge:
    def __init__(self, parent, child, is_delay, is_missing, is_valid):
        self.parent = parent
        self.child = child
        self.is_delay = is_delay
        self.is_missing = is_missing
        self.is_valid = is_valid
        self.in_cycle = False

    def __hash__(self):
        return hash((self.parent, self.child))

    def __eq__(self, other):
        return (
            isinstance(other, DependencyEdge)
            and self.parent == other.parent
            and self.child == other.child
        )

    def status_emojis(self):
        flags = []
        if self.is_missing:
            flags.append("❌")
        elif not self.is_valid:
            flags.append("❗")
        if self.is_delay:
            flags.append("⏳")
        if self.in_cycle:
            flags.append("🔁")
        return flags

    def status_flags(self):
        flags = []
        if self.is_missing:
            flags.append("[MISSING]")
        elif not self.is_valid:
            flags.append("[INVALID]")
        if self.is_delay:
            flags.append("[DELAY]")
        return flags

    def status_color(self):
        if self.is_missing:
            return "red"
        elif not self.is_valid:
            return "orange"
        if self.is_delay:
            return "blue"
        return "black"
