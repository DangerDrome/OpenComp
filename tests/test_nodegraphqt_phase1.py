"""Phase 1 Tests — Standalone Canvas Proof of Concept.

Tests that NodeGraphQt works correctly with OpenComp node types.
"""

import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_nodegraphqt_import():
    """NodeGraphQt imports without error."""
    try:
        from NodeGraphQt import NodeGraph, BaseNode
        assert NodeGraph is not None
        assert BaseNode is not None
        print("  ✓ NodeGraphQt imports successfully")
        return True
    except ImportError as e:
        print(f"  ✗ NodeGraphQt import failed: {e}")
        return False


def test_pyside6_import():
    """PySide6 imports without error."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        assert QApplication is not None
        print("  ✓ PySide6 imports successfully")
        return True
    except ImportError as e:
        print(f"  ✗ PySide6 import failed: {e}")
        return False


def test_opencomp_graph_instantiation():
    """OpenCompGraph instantiates correctly."""
    try:
        # Need QApplication for NodeGraphQt
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        from opencomp_core.qt_canvas.canvas.graph import OpenCompGraph
        graph = OpenCompGraph()
        assert graph is not None
        print("  ✓ OpenCompGraph instantiates correctly")
        return True
    except Exception as e:
        print(f"  ✗ OpenCompGraph instantiation failed: {e}")
        return False


def test_layout_direction():
    """Layout direction is vertical (top-to-bottom)."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        from opencomp_core.qt_canvas.canvas.graph import OpenCompGraph
        graph = OpenCompGraph()

        # Check layout direction is vertical (1)
        direction = graph.get_layout_direction()
        assert direction == 1, f"Expected 1 (vertical), got {direction}"
        print("  ✓ Layout direction is vertical (top-to-bottom)")
        return True
    except Exception as e:
        print(f"  ✗ Layout direction check failed: {e}")
        return False


def test_node_registration():
    """All OpenComp node types register without error."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        from opencomp_core.qt_canvas.canvas.graph import OpenCompGraph
        from opencomp_core.qt_canvas.canvas.nodes import register_nodes, NODE_CLASSES

        graph = OpenCompGraph()
        register_nodes(graph)

        # Check that all nodes are registered
        registered = graph.registered_nodes()
        assert len(registered) >= len(NODE_CLASSES), \
            f"Expected {len(NODE_CLASSES)} nodes, got {len(registered)}"

        print(f"  ✓ All {len(NODE_CLASSES)} node types registered successfully")
        return True
    except Exception as e:
        print(f"  ✗ Node registration failed: {e}")
        return False


def test_node_colors():
    """Each node type has correct color for its category."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        from opencomp_core.qt_canvas.canvas.graph import OpenCompGraph
        from opencomp_core.qt_canvas.canvas.nodes import (
            register_nodes, NODE_CLASSES, NODE_COLORS
        )

        graph = OpenCompGraph()
        register_nodes(graph)

        # Get registered node names to find correct identifier format
        registered = graph.registered_nodes()

        # Create one node of each type and check its color
        for node_class in NODE_CLASSES:
            # NodeGraphQt uses the full class name as identifier
            # Find matching registered node
            class_name = node_class.__name__
            matching = [n for n in registered if class_name in n]

            if not matching:
                print(f"  ✗ Node not registered: {class_name}")
                continue

            identifier = matching[0]
            node = graph.create_node(identifier)

            if node is None:
                print(f"  ✗ Failed to create node: {identifier}")
                return False

            # Get expected color
            expected = NODE_COLORS.get(node_class.CATEGORY)
            if expected:
                r, g, b = node.color()
                # Convert expected to 0-255
                exp_r, exp_g, exp_b = [int(c * 255) for c in expected]
                # Allow some tolerance due to rounding
                assert abs(r - exp_r) <= 2, f"{identifier}: red mismatch ({r} vs {exp_r})"
                assert abs(g - exp_g) <= 2, f"{identifier}: green mismatch ({g} vs {exp_g})"
                assert abs(b - exp_b) <= 2, f"{identifier}: blue mismatch ({b} vs {exp_b})"

            graph.delete_node(node)

        print("  ✓ All node types have correct category colors")
        return True
    except Exception as e:
        print(f"  ✗ Node color check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_window():
    """MainWindow creates without error."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        from opencomp_core.qt_canvas.ui.main_window import OpenCompMainWindow
        window = OpenCompMainWindow()
        assert window is not None
        assert window.graph is not None
        print("  ✓ MainWindow creates successfully")
        return True
    except Exception as e:
        print(f"  ✗ MainWindow creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_launch_exists():
    """launch.py exists and is valid Python."""
    try:
        launch_path = os.path.join(
            PROJECT_ROOT, 'opencomp_core', 'qt_canvas', 'launch.py'
        )
        assert os.path.exists(launch_path), "launch.py not found"

        # Check it's valid Python by compiling it
        with open(launch_path, 'r') as f:
            source = f.read()
        compile(source, launch_path, 'exec')

        print("  ✓ launch.py exists and is valid Python")
        return True
    except Exception as e:
        print(f"  ✗ launch.py check failed: {e}")
        return False


def run_phase1_tests():
    """Run all Phase 1 tests."""
    print("\n" + "=" * 60)
    print("NodeGraphQt Phase 1 Tests — Standalone Canvas")
    print("=" * 60 + "\n")

    tests = [
        ("NodeGraphQt Import", test_nodegraphqt_import),
        ("PySide6 Import", test_pyside6_import),
        ("OpenCompGraph Instantiation", test_opencomp_graph_instantiation),
        ("Layout Direction", test_layout_direction),
        ("Node Registration", test_node_registration),
        ("Node Colors", test_node_colors),
        ("MainWindow Creation", test_main_window),
        ("launch.py Exists", test_launch_exists),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"Testing: {name}")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test error: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Phase 1 Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_phase1_tests()
    sys.exit(0 if success else 1)
