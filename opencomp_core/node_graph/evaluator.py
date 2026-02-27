"""OpenComp graph evaluator — topological sort, dirty propagation, evaluation.

Uses Kahn's algorithm for topological sorting.
DirtyTracker propagates dirty state downstream.
Evaluator orchestrates safe per-node evaluation.
"""

from collections import deque
from .. import console


class CycleDetectedError(Exception):
    """Raised when a cycle is detected in the node graph."""
    pass


def topological_sort(graph):
    """Kahn's algorithm for topological sorting.

    Args:
        graph: dict of {node_id: {"inputs": [upstream_node_id, ...]}}

    Returns:
        list of node_ids in evaluation order (upstream first)

    Raises:
        CycleDetectedError: if the graph contains a cycle
    """
    # Build in-degree counts and adjacency (downstream) lists
    in_degree = {node: 0 for node in graph}
    downstream = {node: [] for node in graph}

    for node, data in graph.items():
        for dep in data["inputs"]:
            if dep in graph:
                downstream[dep].append(node)
                in_degree[node] += 1

    # Start with zero-in-degree nodes
    queue = deque(node for node, deg in in_degree.items() if deg == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for child in downstream[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(result) != len(graph):
        raise CycleDetectedError("Cycle detected in node graph")

    return result


class DirtyTracker:
    """Tracks dirty state for nodes in the graph.

    When a node is marked dirty, all downstream dependents are also dirtied.
    """

    def __init__(self):
        self._dirty = set()
        # _dependents[A] = [B, C] means B and C depend on A
        self._dependents = {}

    def add_dependency(self, dependent, dependency):
        """Register that `dependent` depends on `dependency`."""
        if dependency not in self._dependents:
            self._dependents[dependency] = []
        self._dependents[dependency].append(dependent)

    def mark_dirty(self, node_id):
        """Mark node and all downstream dependents as dirty."""
        if node_id in self._dirty:
            return
        self._dirty.add(node_id)
        for dep in self._dependents.get(node_id, []):
            self.mark_dirty(dep)

    def is_dirty(self, node_id):
        """Check if a node is dirty."""
        return node_id in self._dirty

    def mark_clean(self, node_id):
        """Mark a single node as clean."""
        self._dirty.discard(node_id)


class Evaluator:
    """Evaluates the node graph in topological order.

    Wraps evaluation with error handling so one failing node
    does not crash the entire graph.
    """

    def __init__(self):
        self._results = {}

    def evaluate_safe(self, node_id, texture_pool):
        """Evaluate a node safely, returning None on any error.

        In a full graph evaluation, the node object would be looked up
        and its evaluate() method called. For standalone use, returns
        the cached result or None.
        """
        try:
            return self._results.get(node_id, None)
        except Exception as e:
            console.error(f"Evaluator error for {node_id}: {e}", "Evaluator")
            return None
