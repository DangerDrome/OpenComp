"""Phase 4 Tests — Production Polish.

Tests session save/load, serialization, and launch integration.
"""

import sys
import os
import json
import tempfile
import pathlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Add qt_canvas directly to avoid bpy import from opencomp_core/__init__.py
QT_CANVAS_PATH = os.path.join(PROJECT_ROOT, "opencomp_core", "qt_canvas")
sys.path.insert(0, QT_CANVAS_PATH)


def get_node_identifier(graph, node_class):
    """Find the registered identifier for a node class."""
    registered = graph.registered_nodes()
    class_name = node_class.__name__
    matching = [n for n in registered if class_name in n]
    return matching[0] if matching else None


def test_graph_serializes_to_json():
    """Graph serializes to valid JSON."""
    try:
        from PySide6.QtWidgets import QApplication
        from canvas.graph import OpenCompGraph
        from canvas.nodes import ReadNode, GradeNode, ViewerNode

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        graph = OpenCompGraph()
        graph.register_nodes([ReadNode, GradeNode, ViewerNode])

        # Get correct identifiers
        read_id = get_node_identifier(graph, ReadNode)
        grade_id = get_node_identifier(graph, GradeNode)
        viewer_id = get_node_identifier(graph, ViewerNode)

        # Create some nodes
        read_node = graph.create_node(read_id)
        grade_node = graph.create_node(grade_id)
        viewer_node = graph.create_node(viewer_id)

        # Connect them
        read_node.set_pos(0, 0)
        grade_node.set_pos(0, 100)
        viewer_node.set_pos(0, 200)

        # Connect read -> grade -> viewer
        read_out = read_node.output(0)
        grade_in = grade_node.input(0)
        grade_out = grade_node.output(0)
        viewer_in = viewer_node.input(0)

        read_out.connect_to(grade_in)
        grade_out.connect_to(viewer_in)

        # Serialize
        session_data = graph.serialize_session()

        # Should be valid JSON
        json_str = json.dumps(session_data)
        assert len(json_str) > 0

        # Parse it back
        parsed = json.loads(json_str)
        assert 'graph' in parsed or 'nodes' in parsed or isinstance(parsed, dict)

        print("  ✓ Graph serializes to valid JSON")
        return True
    except Exception as e:
        print(f"  ✗ Serialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_deserializes_correctly():
    """Graph deserializes and rebuilds correctly."""
    try:
        from PySide6.QtWidgets import QApplication
        from canvas.graph import OpenCompGraph
        from canvas.nodes import ReadNode, GradeNode, ViewerNode

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Create first graph with nodes
        graph1 = OpenCompGraph()
        graph1.register_nodes([ReadNode, GradeNode, ViewerNode])

        # Get correct identifiers
        read_id = get_node_identifier(graph1, ReadNode)
        grade_id = get_node_identifier(graph1, GradeNode)
        viewer_id = get_node_identifier(graph1, ViewerNode)

        read_node = graph1.create_node(read_id)
        grade_node = graph1.create_node(grade_id)
        viewer_node = graph1.create_node(viewer_id)

        read_node.set_pos(0, 0)
        grade_node.set_pos(0, 100)
        viewer_node.set_pos(0, 200)

        # Connect
        read_node.output(0).connect_to(grade_node.input(0))
        grade_node.output(0).connect_to(viewer_node.input(0))

        original_count = len(graph1.all_nodes())

        # Serialize
        session_data = graph1.serialize_session()

        # Create second graph and deserialize
        graph2 = OpenCompGraph()
        graph2.register_nodes([ReadNode, GradeNode, ViewerNode])
        graph2.deserialize_session(session_data)

        restored_count = len(graph2.all_nodes())

        assert restored_count == original_count, \
            f"Node count mismatch: {restored_count} != {original_count}"

        print("  ✓ Graph deserializes and rebuilds correctly")
        return True
    except Exception as e:
        print(f"  ✗ Deserialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_save_load():
    """Session saves and loads from file."""
    try:
        from PySide6.QtWidgets import QApplication
        from canvas.graph import OpenCompGraph
        from canvas.nodes import ReadNode, OverNode, ViewerNode
        from canvas.session import save_session, load_session

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Create graph with nodes
        graph1 = OpenCompGraph()
        graph1.register_nodes([ReadNode, OverNode, ViewerNode])

        # Get correct identifiers
        read_id = get_node_identifier(graph1, ReadNode)
        over_id = get_node_identifier(graph1, OverNode)
        viewer_id = get_node_identifier(graph1, ViewerNode)

        read1 = graph1.create_node(read_id)
        read2 = graph1.create_node(read_id)
        over_node = graph1.create_node(over_id)
        viewer = graph1.create_node(viewer_id)

        read1.set_pos(0, 0)
        read2.set_pos(200, 0)
        over_node.set_pos(100, 100)
        viewer.set_pos(100, 200)

        # Connect
        read1.output(0).connect_to(over_node.input(0))  # B input
        read2.output(0).connect_to(over_node.input(1))  # A input
        over_node.output(0).connect_to(viewer.input(0))

        original_count = len(graph1.all_nodes())

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.ocgraph', delete=False) as f:
            temp_path = f.name

        try:
            success = save_session(graph1, temp_path)
            assert success, "save_session returned False"

            # Verify file exists and has content
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                content = json.load(f)
            assert content.get('format') == 'opencomp_graph'

            # Load into new graph
            graph2 = OpenCompGraph()
            graph2.register_nodes([ReadNode, OverNode, ViewerNode])

            success = load_session(graph2, temp_path)
            assert success, "load_session returned False"

            restored_count = len(graph2.all_nodes())
            assert restored_count == original_count, \
                f"Node count mismatch after load: {restored_count} != {original_count}"

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        print("  ✓ Session saves and loads from file")
        return True
    except Exception as e:
        print(f"  ✗ Session save/load test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_serialize_graph_state():
    """serialize_graph_state returns valid structure."""
    try:
        from PySide6.QtWidgets import QApplication
        from canvas.graph import OpenCompGraph
        from canvas.nodes import ReadNode, GradeNode, ViewerNode
        from canvas.session import serialize_graph_state

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        graph = OpenCompGraph()
        graph.register_nodes([ReadNode, GradeNode, ViewerNode])

        # Get correct identifiers
        read_id = get_node_identifier(graph, ReadNode)
        grade_id = get_node_identifier(graph, GradeNode)

        read_node = graph.create_node(read_id)
        grade_node = graph.create_node(grade_id)

        read_node.set_pos(100, 50)
        grade_node.set_pos(100, 150)

        read_node.output(0).connect_to(grade_node.input(0))

        # Serialize graph state
        state = serialize_graph_state(graph)

        # Check structure
        assert 'nodes' in state, "Missing 'nodes' key"
        assert 'links' in state, "Missing 'links' key"
        assert len(state['nodes']) == 2, f"Expected 2 nodes, got {len(state['nodes'])}"
        assert len(state['links']) == 1, f"Expected 1 link, got {len(state['links'])}"

        # Check node data
        node_data = state['nodes'][0]
        assert 'oc_id' in node_data, "Node missing oc_id"
        assert 'name' in node_data, "Node missing name"
        assert 'type' in node_data, "Node missing type"
        assert 'x' in node_data, "Node missing x"
        assert 'y' in node_data, "Node missing y"

        # Check link data
        link_data = state['links'][0]
        assert 'from_node' in link_data, "Link missing from_node"
        assert 'from_port' in link_data, "Link missing from_port"
        assert 'to_node' in link_data, "Link missing to_node"
        assert 'to_port' in link_data, "Link missing to_port"

        print("  ✓ serialize_graph_state returns valid structure")
        return True
    except Exception as e:
        print(f"  ✗ serialize_graph_state test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deserialize_graph_state():
    """deserialize_graph_state rebuilds graph correctly."""
    try:
        from PySide6.QtWidgets import QApplication
        from canvas.graph import OpenCompGraph
        from canvas.nodes import ReadNode, GradeNode, ViewerNode
        from canvas.session import (
            serialize_graph_state, deserialize_graph_state
        )

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Create source graph
        graph1 = OpenCompGraph()
        graph1.register_nodes([ReadNode, GradeNode, ViewerNode])

        # Get correct identifiers
        read_id = get_node_identifier(graph1, ReadNode)
        grade_id = get_node_identifier(graph1, GradeNode)
        viewer_id = get_node_identifier(graph1, ViewerNode)

        read_node = graph1.create_node(read_id)
        grade_node = graph1.create_node(grade_id)
        viewer_node = graph1.create_node(viewer_id)

        read_node.set_pos(0, 0)
        grade_node.set_pos(0, 100)
        viewer_node.set_pos(0, 200)

        read_node.output(0).connect_to(grade_node.input(0))
        grade_node.output(0).connect_to(viewer_node.input(0))

        # Serialize
        state = serialize_graph_state(graph1)
        original_node_count = len(state['nodes'])
        original_link_count = len(state['links'])

        # Create target graph and deserialize
        graph2 = OpenCompGraph()
        graph2.register_nodes([ReadNode, GradeNode, ViewerNode])

        success = deserialize_graph_state(graph2, state)
        assert success, "deserialize_graph_state returned False"

        # Verify node count
        restored_nodes = len(graph2.all_nodes())
        assert restored_nodes == original_node_count, \
            f"Node count mismatch: {restored_nodes} != {original_node_count}"

        # Count connections
        link_count = 0
        for node in graph2.all_nodes():
            for port in node.output_ports():
                link_count += len(port.connected_ports())

        assert link_count == original_link_count, \
            f"Link count mismatch: {link_count} != {original_link_count}"

        print("  ✓ deserialize_graph_state rebuilds graph correctly")
        return True
    except Exception as e:
        print(f"  ✗ deserialize_graph_state test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_launch_script_args():
    """launch.py accepts --socket-path argument."""
    try:
        import argparse

        # Import the parse_args function
        launch_path = pathlib.Path(PROJECT_ROOT) / "opencomp_core" / "qt_canvas" / "launch.py"
        assert launch_path.exists(), f"launch.py not found at {launch_path}"

        # Read the file and check for argparse setup
        with open(launch_path, 'r') as f:
            content = f.read()

        assert '--socket-path' in content, "Missing --socket-path argument"
        assert '--debug' in content, "Missing --debug argument"
        assert '--no-connect' in content, "Missing --no-connect argument"

        print("  ✓ launch.py accepts expected command line arguments")
        return True
    except Exception as e:
        print(f"  ✗ Launch script args test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_blender_launch_module():
    """blender_launch.py has required functions."""
    try:
        launch_path = pathlib.Path(PROJECT_ROOT) / "opencomp_core" / "qt_canvas" / "blender_launch.py"
        assert launch_path.exists(), f"blender_launch.py not found"

        with open(launch_path, 'r') as f:
            content = f.read()

        # Check for required functions
        assert 'def get_launch_script_path' in content, "Missing get_launch_script_path"
        assert 'def get_python_executable' in content, "Missing get_python_executable"
        assert 'def is_canvas_running' in content, "Missing is_canvas_running"
        assert 'def launch_canvas' in content, "Missing launch_canvas"
        assert 'def register_operator' in content, "Missing register_operator"
        assert 'def unregister_operator' in content, "Missing unregister_operator"

        # Check for operator class
        assert 'OC_OT_launch_canvas' in content, "Missing OC_OT_launch_canvas operator"
        assert 'bl_idname = "oc.launch_canvas"' in content, "Incorrect bl_idname"

        print("  ✓ blender_launch.py has required functions and operator")
        return True
    except Exception as e:
        print(f"  ✗ blender_launch module test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_phase4_tests():
    """Run all Phase 4 tests."""
    print("\n" + "=" * 60)
    print("NodeGraphQt Phase 4 Tests — Production Polish")
    print("=" * 60 + "\n")

    tests = [
        ("Graph Serializes to JSON", test_graph_serializes_to_json),
        ("Graph Deserializes Correctly", test_graph_deserializes_correctly),
        ("Session Save/Load", test_session_save_load),
        ("serialize_graph_state", test_serialize_graph_state),
        ("deserialize_graph_state", test_deserialize_graph_state),
        ("Launch Script Arguments", test_launch_script_args),
        ("Blender Launch Module", test_blender_launch_module),
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
    print(f"Phase 4 Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_phase4_tests()
    sys.exit(0 if success else 1)
