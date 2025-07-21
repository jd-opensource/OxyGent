"""
Unit tests for oxygent.utils.data_utils
"""

from oxygent.utils.data_utils import add_post_and_child_node_ids, build_tree


# ──────────────────────────────────────────────────────────────────────────────
# add_post_and_child_node_ids
# ──────────────────────────────────────────────────────────────────────────────
def test_add_post_and_child_node_ids_basic():
    """
    A ─┬─► B        (pre-edge)
        └─► C        (pre-edge)
        │
        └── D        (father-child)
    """
    nodes = [
        {"node_id": "A", "pre_node_ids": [], "father_node_id": ""},
        {"node_id": "B", "pre_node_ids": ["A"], "father_node_id": ""},
        {"node_id": "C", "pre_node_ids": ["A"], "father_node_id": ""},
        {"node_id": "D", "pre_node_ids": [], "father_node_id": "A"},
    ]

    add_post_and_child_node_ids(nodes)

    a = next(n for n in nodes if n["node_id"] == "A")
    b = next(n for n in nodes if n["node_id"] == "B")
    c = next(n for n in nodes if n["node_id"] == "C")
    d = next(n for n in nodes if n["node_id"] == "D")

    assert set(a["post_node_ids"]) == {"B", "C"}
    assert a["child_node_ids"] == ["D"]

    for leaf in (b, c, d):
        assert leaf["post_node_ids"] == []
        assert leaf["child_node_ids"] == []


def test_add_post_and_child_missing_pre():
    nodes = [
        {"node_id": "X", "pre_node_ids": ["no_exist"], "father_node_id": ""},
        {"node_id": "Y", "pre_node_ids": ["X"], "father_node_id": "no_exist"},
    ]
    add_post_and_child_node_ids(nodes)  
    x = nodes[0]
    assert x["post_node_ids"] == ["Y"]          
    assert x["child_node_ids"] == []           


# ──────────────────────────────────────────────────────────────────────────────
# build_tree
# ──────────────────────────────────────────────────────────────────────────────
def _sorted_nodes(node):
    if isinstance(node, list):
        return sorted([_sorted_nodes(n) for n in node], key=lambda x: json_key(x))
    out = {k: v for k, v in node.items() if k != "nodes"}
    out["nodes"] = [_sorted_nodes(n) for n in node["nodes"]]
    return out


def json_key(item):
    """deterministic sort key"""
    if isinstance(item, dict):
        return item["node_id"]
    return str(item)


def test_build_tree_with_parallel_groups():
    """
    root
      ├─ a (order1)
      ├─ [b,c] parallel 
      └─ d (order4)
    """
    input_nodes = [
        {
            "node_id": "root",
            "node_name": "root",
            "node_type": "agent",
            "from_node_id": None,
            "order": 0,
        },
        {
            "node_id": "a",
            "node_name": "a",
            "node_type": "tool",
            "from_node_id": "root",
            "order": 1,
        },
        {
            "node_id": "b",
            "node_name": "b",
            "node_type": "tool",
            "from_node_id": "root",
            "parallel_id": "p1",
            "order": 2,
        },
        {
            "node_id": "c",
            "node_name": "c",
            "node_type": "tool",
            "from_node_id": "root",
            "parallel_id": "p1",
            "order": 3,
        },
        {
            "node_id": "d",
            "node_name": "d",
            "node_type": "tool",
            "from_node_id": "root",
            "order": 4,
        },
    ]

    expected = {
        "node_id": "root",
        "node_name": "root",
        "node_type": "agent",
        "nodes": [
            {
                "node_id": "a",
                "node_name": "a",
                "node_type": "tool",
                "nodes": [],
            },
            [  # parallel group
                {
                    "node_id": "b",
                    "node_name": "b",
                    "node_type": "tool",
                    "nodes": [],
                },
                {
                    "node_id": "c",
                    "node_name": "c",
                    "node_type": "tool",
                    "nodes": [],
                },
            ],
            {
                "node_id": "d",
                "node_name": "d",
                "node_type": "tool",
                "nodes": [],
            },
        ],
    }

    tree = build_tree(input_nodes)
    assert _sorted_nodes(tree) == _sorted_nodes(expected)
