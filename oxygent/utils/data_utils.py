from collections import defaultdict


def add_post_and_child_node_ids(nodes):
    """Adds `post_node_ids` and `child_node_ids` fields to each node.

    Each node will gain:
    - post_node_ids: A list of node_ids for which this node is a pre_node.
    - child_node_ids: A list of node_ids that are direct children of this node (based on father_node_id).

    Args:
        nodes (List[Dict]): Each node dictionary must contain 'node_id' and 'pre_node_ids' fields.

    Returns:
        None. Modifies the input `nodes` list in place.
    """
    # Build a mapping from node_id to node
    node_map = {n["node_id"]: n for n in nodes}
    # Initialize post_node_ids and child_node_ids
    for n in nodes:
        n["post_node_ids"] = []
        n["child_node_ids"] = []
    # Populate post_node_ids based on pre_node_ids
    for n in nodes:
        for pre in n["pre_node_ids"]:
            if pre and pre in node_map:
                node_map[pre]["post_node_ids"].append(n["node_id"])
        father_node_id = n["father_node_id"]
        if father_node_id and father_node_id in node_map:
            node_map[father_node_id]["child_node_ids"].append(n["node_id"])


def build_tree(input_data):
    """Builds a tree structure from the input list of nodes."""
    node_dict = {node["node_id"]: node.copy() for node in input_data}
    for node in node_dict.values():
        node["nodes"] = []

    roots = [node for node in node_dict.values() if not node["from_node_id"]]

    children_map = _build_children_map(node_dict)

    root = roots[0]
    return _build_node_entry(root, children_map)


def _build_children_map(node_dict):
    children_map = defaultdict(list)
    for node in node_dict.values():
        if node["from_node_id"]:
            children_map[node["from_node_id"]].append(node)
    return children_map


def _build_node_entry(node, children_map):
    return {
        "node_id": node["node_id"],
        "node_name": node["node_name"],
        "node_type": node["node_type"],
        "nodes": _build_subtree(node, children_map),
    }


def _build_subtree(parent, children_map):
    children = children_map.get(parent["node_id"], [])
    non_parallel, parallel_groups = _group_children(children)
    parallel_list = _process_parallel_groups(parallel_groups)

    all_children = _merge_and_sort_children(non_parallel, parallel_list)

    nodes = []
    for _, item in all_children:
        if isinstance(item, list):  # Parallel group
            nodes.append([_build_node_entry(n, children_map) for n in item])
        else:
            nodes.append(_build_node_entry(item, children_map))
    return nodes


def _group_children(children):
    parallel_groups = defaultdict(list)
    non_parallel = []
    for child in children:
        if "parallel_id" in child:
            parallel_groups[child["parallel_id"]].append(child)
        else:
            non_parallel.append(child)
    return non_parallel, parallel_groups


def _process_parallel_groups(parallel_groups):
    parallel_list = []
    for group in parallel_groups.values():
        group_sorted = sorted(group, key=lambda x: x["order"])
        min_order = group_sorted[0]["order"]
        parallel_list.append((min_order, group_sorted))
    return parallel_list


def _merge_and_sort_children(non_parallel, parallel_list):
    all_children = [(child["order"], child) for child in non_parallel] + parallel_list
    all_children.sort(key=lambda x: x[0])
    return all_children
