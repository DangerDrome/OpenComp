"""OpenComp Qt Canvas — Session save/load.

Handles serialization and deserialization of node graph sessions.
"""

import json
import pathlib
from typing import Optional, Dict, List, Any


def save_session(graph, filepath: str) -> bool:
    """Save the current graph session to a file.

    Args:
        graph: OpenCompGraph instance.
        filepath: Path to save the session (.ocgraph file).

    Returns:
        True if successful, False otherwise.
    """
    try:
        # NodeGraphQt has built-in JSON serialization
        session_data = graph.serialize_session()

        # Add OpenComp-specific metadata
        session = {
            'version': '1.0',
            'format': 'opencomp_graph',
            'data': session_data,
        }

        # Write to file
        path = pathlib.Path(filepath)
        with open(path, 'w') as f:
            json.dump(session, f, indent=2)

        print(f"[OpenComp] Session saved to {filepath}")
        return True

    except Exception as e:
        print(f"[OpenComp] Failed to save session: {e}")
        return False


def load_session(graph, filepath: str) -> bool:
    """Load a graph session from a file.

    Args:
        graph: OpenCompGraph instance.
        filepath: Path to the session file (.ocgraph).

    Returns:
        True if successful, False otherwise.
    """
    try:
        path = pathlib.Path(filepath)
        if not path.exists():
            print(f"[OpenComp] Session file not found: {filepath}")
            return False

        with open(path, 'r') as f:
            session = json.load(f)

        # Validate format
        if session.get('format') != 'opencomp_graph':
            print(f"[OpenComp] Invalid session format")
            return False

        # Restore session using NodeGraphQt's deserialize
        session_data = session.get('data', {})
        graph.deserialize_session(session_data)

        print(f"[OpenComp] Session loaded from {filepath}")
        return True

    except Exception as e:
        print(f"[OpenComp] Failed to load session: {e}")
        return False


def serialize_graph_state(graph) -> Dict[str, Any]:
    """Serialize the current graph state to a dict.

    This is used for IPC communication to sync state with Blender.

    Args:
        graph: OpenCompGraph instance.

    Returns:
        Dictionary containing nodes and links data.
    """
    nodes = []
    links = []

    for node in graph.all_nodes():
        node_data = {
            'oc_id': node.get_oc_id(),
            'name': node.name(),
            'type': f"{node.__class__.__identifier__}.{node.__class__.NODE_NAME}",
            'x': node.pos()[0],
            'y': node.pos()[1],
            'properties': {},
        }

        # Get custom properties
        try:
            for prop_name in node.model.custom_properties:
                node_data['properties'][prop_name] = node.get_property(prop_name)
        except:
            pass

        nodes.append(node_data)

    # Serialize connections
    for node in graph.all_nodes():
        for output_port in node.output_ports():
            for connected_port in output_port.connected_ports():
                link_data = {
                    'from_node': node.get_oc_id(),
                    'from_port': output_port.name(),
                    'to_node': connected_port.node().get_oc_id(),
                    'to_port': connected_port.name(),
                }
                links.append(link_data)

    return {
        'nodes': nodes,
        'links': links,
    }


def _find_registered_node_type(graph, node_type: str) -> Optional[str]:
    """Find the registered node identifier matching the stored type.

    Args:
        graph: OpenCompGraph instance.
        node_type: Stored type like 'opencomp.io.Read'.

    Returns:
        The actual registered identifier or None.
    """
    registered = graph.registered_nodes()

    # Try exact match first
    if node_type in registered:
        return node_type

    # Extract class name from the stored type (last part after the dot)
    parts = node_type.split('.')
    class_name = parts[-1] if parts else node_type

    # Search for matching registered node
    for reg_type in registered:
        if class_name in reg_type:
            return reg_type

    return None


def deserialize_graph_state(graph, state: Dict[str, Any]) -> bool:
    """Deserialize a graph state dict into the graph.

    Args:
        graph: OpenCompGraph instance.
        state: Dictionary containing nodes and links data.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Clear existing graph
        graph.clear_session()

        nodes = state.get('nodes', [])
        links = state.get('links', [])

        # Create nodes
        oc_id_to_node = {}
        for node_data in nodes:
            stored_type = node_data.get('type')
            node_type = _find_registered_node_type(graph, stored_type)

            if not node_type:
                print(f"[OpenComp] Unknown node type: {stored_type}")
                continue

            node = graph.create_node(node_type)

            if node is None:
                print(f"[OpenComp] Failed to create node: {node_type}")
                continue

            # Restore position
            x = node_data.get('x', 0)
            y = node_data.get('y', 0)
            node.set_pos(x, y)

            # Restore oc_id
            oc_id = node_data.get('oc_id')
            if oc_id:
                node.set_oc_id(oc_id)
                oc_id_to_node[oc_id] = node

            # Restore properties
            props = node_data.get('properties', {})
            for prop_name, prop_value in props.items():
                try:
                    node.set_property(prop_name, prop_value)
                except:
                    pass

        # Create links
        for link_data in links:
            from_oc_id = link_data.get('from_node')
            from_port_name = link_data.get('from_port')
            to_oc_id = link_data.get('to_node')
            to_port_name = link_data.get('to_port')

            from_node = oc_id_to_node.get(from_oc_id)
            to_node = oc_id_to_node.get(to_oc_id)

            if not from_node or not to_node:
                continue

            # Find ports
            from_port = None
            for port in from_node.output_ports():
                if port.name() == from_port_name:
                    from_port = port
                    break

            to_port = None
            for port in to_node.input_ports():
                if port.name() == to_port_name:
                    to_port = port
                    break

            if from_port and to_port:
                from_port.connect_to(to_port)

        print(f"[OpenComp] Graph state restored: {len(nodes)} nodes, {len(links)} links")
        return True

    except Exception as e:
        print(f"[OpenComp] Failed to deserialize graph state: {e}")
        import traceback
        traceback.print_exc()
        return False
