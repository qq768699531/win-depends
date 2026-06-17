from win_depends.nodedata import NodeData
from win_depends.edgedata import EdgeData


def test_nodedata_label_and_flags():
    node_data = NodeData(
        is_system=True,
        is_orphan=True,
        is_forward=True,
        forward_to=[r"C:\path\to\libB.dll"],
    )
    label = node_data.label(r"C:\path\to\libA.dll")
    assert "libA.dll" in label
    assert "libB.dll" in label
    assert "[SYS]" in label
    assert "(orphan)" in label
    assert "->" in label or "forward" in label


def test_edgedata_statuses():
    e_missing = EdgeData(is_delay=False, is_missing=True, is_valid=False)
    assert "❌" in "".join(e_missing.status_emojis())
    assert "[MISSING]" in "".join(e_missing.status_flags())
    assert e_missing.status_color() == "red"

    e_invalid = EdgeData(is_delay=False, is_missing=False, is_valid=False)
    assert "❗" in "".join(e_invalid.status_emojis())
    assert "[INVALID]" in "".join(e_invalid.status_flags())
    assert e_invalid.status_color() == "orange"

    e_delay = EdgeData(is_delay=True, is_missing=False, is_valid=True)
    assert "⏳" in "".join(e_delay.status_emojis())
    assert "[DELAY]" in "".join(e_delay.status_flags())
    assert e_delay.status_color() == "blue"

    e_cycle = EdgeData(is_delay=False, is_missing=False, is_valid=True, in_cycle=True)
    assert "🔁" in "".join(e_cycle.status_emojis())
