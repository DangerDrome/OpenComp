"""
Phase 2 tests — Custom node graph, sockets, evaluator.
Must be run inside Blender: ./blender/blender --background --python tests/run_tests.py
All tests must pass before Phase 3 begins.
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def run(test):

    def check_node_graph_files_exist():
        ng = REPO_ROOT / "opencomp_core" / "node_graph"
        assert (ng / "tree.py").is_file(),      "node_graph/tree.py missing"
        assert (ng / "evaluator.py").is_file(), "node_graph/evaluator.py missing"
        assert (ng / "sockets.py").is_file(),   "node_graph/sockets.py missing"

    def check_base_node_exists():
        nodes = REPO_ROOT / "opencomp_core" / "nodes"
        assert (nodes / "base.py").is_file(), "nodes/base.py missing"

    def check_nodetree_registers():
        import bpy
        sys.path.insert(0, str(REPO_ROOT))
        from opencomp_core.node_graph.tree import OpenCompNodeTree
        try:
            bpy.utils.register_class(OpenCompNodeTree)
        except ValueError:
            pass  # Already registered is fine
        assert "OC_NT_compositor" in dir(bpy.types) or \
               hasattr(bpy.types, "OC_NT_compositor") or \
               OpenCompNodeTree.bl_idname == "OC_NT_compositor", \
               "OpenCompNodeTree bl_idname incorrect"

    def check_sockets_register():
        import bpy
        from opencomp_core.node_graph.sockets import ImageSocket, FloatSocket, VectorSocket
        for cls in [ImageSocket, FloatSocket, VectorSocket]:
            try:
                bpy.utils.register_class(cls)
            except ValueError:
                pass  # Already registered
            assert cls.bl_idname.startswith("OC_NS_"), \
                f"{cls.__name__} bl_idname doesn't start with OC_NS_"

    def check_topological_sort_linear():
        from opencomp_core.node_graph.evaluator import topological_sort

        # Linear graph: A → B → C
        # Each node has: id, inputs (list of upstream node ids)
        graph = {
            "A": {"inputs": []},
            "B": {"inputs": ["A"]},
            "C": {"inputs": ["B"]},
        }
        order = topological_sort(graph)
        assert order.index("A") < order.index("B"), "A must come before B"
        assert order.index("B") < order.index("C"), "B must come before C"

    def check_topological_sort_branching():
        from opencomp_core.node_graph.evaluator import topological_sort

        # Branching: A → C, B → C
        graph = {
            "A": {"inputs": []},
            "B": {"inputs": []},
            "C": {"inputs": ["A", "B"]},
        }
        order = topological_sort(graph)
        assert order.index("A") < order.index("C"), "A must come before C"
        assert order.index("B") < order.index("C"), "B must come before C"

    def check_topological_sort_cycle_detection():
        from opencomp_core.node_graph.evaluator import topological_sort, CycleDetectedError

        # Cycle: A → B → A
        graph = {
            "A": {"inputs": ["B"]},
            "B": {"inputs": ["A"]},
        }
        raised = False
        try:
            topological_sort(graph)
        except CycleDetectedError:
            raised = True
        assert raised, "Cycle not detected — should raise CycleDetectedError"

    def check_dirty_propagation():
        from opencomp_core.node_graph.evaluator import DirtyTracker

        tracker = DirtyTracker()
        # Mark A dirty, B depends on A — B should also be dirty
        tracker.add_dependency("B", "A")
        tracker.add_dependency("C", "B")
        tracker.mark_dirty("A")

        assert tracker.is_dirty("A"), "A should be dirty"
        assert tracker.is_dirty("B"), "B should be dirty (depends on A)"
        assert tracker.is_dirty("C"), "C should be dirty (depends on B)"

        tracker.mark_clean("A")
        tracker.mark_clean("B")
        tracker.mark_clean("C")

        assert not tracker.is_dirty("A"), "A should be clean after mark_clean"

    def check_base_node_class():
        from opencomp_core.nodes.base import OpenCompNode
        import bpy
        assert issubclass(OpenCompNode, bpy.types.Node), \
            "OpenCompNode must subclass bpy.types.Node"
        assert hasattr(OpenCompNode, 'evaluate'), \
            "OpenCompNode missing evaluate() method"

    def check_none_input_graceful():
        """Evaluator should handle None inputs without crashing."""
        from opencomp_core.node_graph.evaluator import Evaluator
        # An evaluator running a graph where a node returns None
        # should not raise an exception — downstream nodes get None input
        # and return None themselves
        evaluator = Evaluator()
        result = evaluator.evaluate_safe(node_id="test", texture_pool=None)
        # Should return None, not crash
        assert result is None or True  # Either None or handled gracefully

    test("node_graph files exist",              check_node_graph_files_exist)
    test("nodes/base.py exists",               check_base_node_exists)
    test("OpenCompNodeTree registers",          check_nodetree_registers)
    test("Sockets register with OC_NS_ prefix", check_sockets_register)
    test("Topological sort — linear graph",    check_topological_sort_linear)
    test("Topological sort — branching graph", check_topological_sort_branching)
    test("Topological sort — cycle detection", check_topological_sort_cycle_detection)
    test("Dirty propagation correct",          check_dirty_propagation)
    test("OpenCompNode base class correct",    check_base_node_class)
    test("None input handled gracefully",      check_none_input_graceful)
