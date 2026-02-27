#!/usr/bin/env python3
"""OpenComp Headless Backend — Blender headless entry point.

This script is the main entry point for the Blender headless backend.
It starts the IPC server, registers command handlers, and runs the
main loop via bpy.app.timers.

Usage:
    blender --background --python opencomp_server/headless.py

Or with GPU:
    blender --background --gpu-backend egl --python opencomp_server/headless.py
"""

import sys
import pathlib

print("[Headless] Script starting...", flush=True)

# Add parent directory to path so we can import opencomp_server
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
print(f"[Headless] Added to path: {REPO_ROOT}", flush=True)

import bpy
print("[Headless] Imported bpy", flush=True)

from opencomp_server.server import start_server, stop_server, get_server
print("[Headless] Imported server", flush=True)
from opencomp_server.shm_output import create_shm_output, close_shm_output, get_shm_output
print("[Headless] Imported shm_output", flush=True)
from opencomp_server.protocol import (
    response_ok, response_error, response_graph_state, response_node_types,
    response_viewer_buffer, event_viewer_updated,
)
print("[Headless] All imports complete", flush=True)


# ── Command Handlers ────────────────────────────────────────────────────────

def handle_get_graph_state(request_id: str, **kwargs):
    """Get the current node graph state."""
    tree = _get_tree()
    if tree is None:
        return response_graph_state(request_id, [], [])

    nodes = []
    for node in tree.nodes:
        node_data = {
            'id': node.name,
            'type': node.bl_idname,
            'label': node.label or node.bl_label,
            'x': node.location.x,
            'y': -node.location.y,  # Invert Y for screen coords
            'inputs': [{'name': s.name, 'type': s.bl_idname} for s in node.inputs],
            'outputs': [{'name': s.name, 'type': s.bl_idname} for s in node.outputs],
            'params': _get_node_params(node),
        }
        nodes.append(node_data)

    connections = []
    for link in tree.links:
        connections.append({
            'from_node': link.from_node.name,
            'from_port': link.from_socket.name,
            'to_node': link.to_node.name,
            'to_port': link.to_socket.name,
        })

    return response_graph_state(request_id, nodes, connections)


def handle_node_create(request_id: str, node_type: str, x: float, y: float, **kwargs):
    """Create a new node."""
    tree = _get_tree(create=True)
    if tree is None:
        return response_error(request_id, "Failed to create node tree")

    try:
        node = tree.nodes.new(type=node_type)
        node.location = (x, -y)  # Invert Y
        return response_ok(request_id, node_id=node.name)
    except Exception as e:
        return response_error(request_id, f"Failed to create node: {e}")


def handle_node_delete(request_id: str, node_id: str, **kwargs):
    """Delete a node."""
    tree = _get_tree()
    if tree is None:
        return response_error(request_id, "No node tree")

    node = tree.nodes.get(node_id)
    if not node:
        return response_error(request_id, f"Node not found: {node_id}")

    tree.nodes.remove(node)
    return response_ok(request_id)


def handle_node_move(request_id: str, node_id: str, x: float, y: float, **kwargs):
    """Move a node to new position."""
    tree = _get_tree()
    if tree is None:
        return response_error(request_id, "No node tree")

    node = tree.nodes.get(node_id)
    if not node:
        return response_error(request_id, f"Node not found: {node_id}")

    node.location = (x, -y)
    return response_ok(request_id)


def handle_node_set_param(request_id: str, node_id: str, param: str, value, **kwargs):
    """Set a node parameter."""
    tree = _get_tree()
    if tree is None:
        return response_error(request_id, "No node tree")

    node = tree.nodes.get(node_id)
    if not node:
        return response_error(request_id, f"Node not found: {node_id}")

    if not hasattr(node, param):
        return response_error(request_id, f"Unknown parameter: {param}")

    try:
        setattr(node, param, value)
        return response_ok(request_id)
    except Exception as e:
        return response_error(request_id, f"Failed to set parameter: {e}")


def handle_connect(request_id: str, from_node: str, from_port: str,
                   to_node: str, to_port: str, **kwargs):
    """Connect two node ports."""
    tree = _get_tree()
    if tree is None:
        return response_error(request_id, "No node tree")

    source = tree.nodes.get(from_node)
    target = tree.nodes.get(to_node)

    if not source or not target:
        return response_error(request_id, "Node(s) not found")

    # Find sockets
    output = None
    for out in source.outputs:
        if out.name == from_port:
            output = out
            break

    input_ = None
    for inp in target.inputs:
        if inp.name == to_port:
            input_ = inp
            break

    if not output or not input_:
        return response_error(request_id, "Socket(s) not found")

    tree.links.new(output, input_)
    return response_ok(request_id)


def handle_disconnect(request_id: str, from_node: str, from_port: str,
                      to_node: str, to_port: str, **kwargs):
    """Disconnect two node ports."""
    tree = _get_tree()
    if tree is None:
        return response_error(request_id, "No node tree")

    for link in list(tree.links):
        if (link.from_node.name == from_node and
            link.from_socket.name == from_port and
            link.to_node.name == to_node and
            link.to_socket.name == to_port):
            tree.links.remove(link)
            return response_ok(request_id)

    return response_error(request_id, "Link not found")


def _get_upstream_nodes(node, visited=None):
    """Get all upstream nodes in evaluation order (topological)."""
    if visited is None:
        visited = set()

    result = []
    for input_socket in node.inputs:
        if input_socket.is_linked:
            for link in input_socket.links:
                upstream = link.from_node
                if upstream.name not in visited:
                    visited.add(upstream.name)
                    # Recursively get upstream nodes first
                    result.extend(_get_upstream_nodes(upstream, visited))
                    result.append(upstream)
    return result


def handle_evaluate(request_id: str, viewer_node_id: str, **kwargs):
    """Trigger evaluation and render to viewer."""
    print(f"[Headless] Evaluate request for: {viewer_node_id}", flush=True)

    tree = _get_tree()
    if tree is None:
        print("[Headless] No node tree!", flush=True)
        return response_error(request_id, "No node tree")

    viewer = tree.nodes.get(viewer_node_id)
    if not viewer:
        print(f"[Headless] Viewer not found: {viewer_node_id}", flush=True)
        print(f"[Headless] Available nodes: {[n.name for n in tree.nodes]}", flush=True)
        return response_error(request_id, f"Viewer not found: {viewer_node_id}")

    print(f"[Headless] Found viewer node: {viewer.name}, type: {viewer.bl_idname}", flush=True)

    try:
        # Import evaluator from opencomp_core
        from opencomp_core.gpu_pipeline.texture_pool import get_texture_pool
        from opencomp_core.node_graph.tree import _node_textures
        pool = get_texture_pool()

        # Get all upstream nodes and evaluate them first
        upstream_nodes = _get_upstream_nodes(viewer)
        print(f"[Headless] Upstream nodes to evaluate: {[n.name for n in upstream_nodes]}", flush=True)

        # Evaluate each upstream node and store its texture
        for node in upstream_nodes:
            if hasattr(node, 'evaluate'):
                print(f"[Headless] Evaluating upstream node: {node.name}", flush=True)
                tex = node.evaluate(pool)
                if tex is not None:
                    _node_textures[node.name] = tex
                    print(f"[Headless] Stored texture for {node.name}: {tex.width}x{tex.height}", flush=True)
                else:
                    print(f"[Headless] Node {node.name} returned None", flush=True)

        # Now evaluate the viewer node
        print("[Headless] Calling viewer.evaluate()...", flush=True)
        texture = viewer.evaluate(pool)
        print(f"[Headless] Evaluate returned: {texture}", flush=True)

        if texture:
            print(f"[Headless] Texture size: {texture.width}x{texture.height}", flush=True)
            # Find the source node (last upstream node, typically the Read node)
            source_node = upstream_nodes[-1].name if upstream_nodes else None
            print(f"[Headless] Source node for SHM: {source_node}", flush=True)

            # Write to shared memory
            shm = get_shm_output()
            if shm:
                width, height = shm.write_from_gpu_texture(texture, source_node=source_node)
                print(f"[Headless] Wrote to SHM: {width}x{height}", flush=True)

                # Send event to client
                server = get_server()
                if server:
                    server.send_event(event_viewer_updated(viewer_node_id, width, height))

                return response_ok(request_id, width=width, height=height)

        print("[Headless] No texture returned!", flush=True)
        return response_ok(request_id, width=0, height=0)

    except Exception as e:
        import traceback
        print(f"[Headless] Evaluation error: {e}", flush=True)
        traceback.print_exc()
        return response_error(request_id, f"Evaluation failed: {e}")


def handle_get_viewer_buffer(request_id: str, viewer_node_id: str, **kwargs):
    """Get shared memory info for viewer buffer."""
    shm = get_shm_output()
    if not shm:
        return response_error(request_id, "Shared memory not initialized")

    # Read current dimensions from header (would need to implement)
    # For now, return the SHM name and client can read header
    return response_viewer_buffer(
        request_id,
        shm_name=shm.name,
        width=0,  # Client reads from SHM header
        height=0,
        channels=4,
        dtype="float32",
    )


def handle_get_node_types(request_id: str, **kwargs):
    """Get available node types organized by category."""
    categories = {
        'Input/Output': [
            {'type': 'OC_N_read', 'label': 'Read', 'icon': 'FILE_IMAGE'},
            {'type': 'OC_N_write', 'label': 'Write', 'icon': 'FILE_TICK'},
            {'type': 'OC_N_viewer', 'label': 'Viewer', 'icon': 'RESTRICT_VIEW_OFF'},
        ],
        'Color': [
            {'type': 'OC_N_grade', 'label': 'Grade', 'icon': 'COLOR'},
            {'type': 'OC_N_cdl', 'label': 'CDL', 'icon': 'COLORSET_03_VEC'},
            {'type': 'OC_N_constant', 'label': 'Constant', 'icon': 'IMAGE_RGB'},
        ],
        'Filter': [
            {'type': 'OC_N_blur', 'label': 'Blur', 'icon': 'SMOOTHCURVE'},
            {'type': 'OC_N_sharpen', 'label': 'Sharpen', 'icon': 'SHARPCURVE'},
        ],
        'Merge': [
            {'type': 'OC_N_over', 'label': 'Over', 'icon': 'SELECT_SUBTRACT'},
            {'type': 'OC_N_merge', 'label': 'Merge', 'icon': 'SELECT_EXTEND'},
            {'type': 'OC_N_shuffle', 'label': 'Shuffle', 'icon': 'UV_SYNC_SELECT'},
        ],
        'Transform': [
            {'type': 'OC_N_transform', 'label': 'Transform', 'icon': 'ORIENTATION_LOCAL'},
            {'type': 'OC_N_crop', 'label': 'Crop', 'icon': 'SELECT_SET'},
        ],
        'Draw': [
            {'type': 'OC_N_roto', 'label': 'Roto', 'icon': 'MESH_CIRCLE'},
        ],
        'Utility': [
            {'type': 'OC_N_reroute', 'label': 'Reroute', 'icon': 'CON_FOLLOWPATH'},
        ],
    }
    return response_node_types(request_id, categories)


def handle_new_project(request_id: str, **kwargs):
    """Create a new project."""
    # Clear existing tree
    tree = _get_tree()
    if tree:
        tree.nodes.clear()
    return response_ok(request_id)


def handle_open_project(request_id: str, path: str, **kwargs):
    """Open a project file."""
    try:
        bpy.ops.wm.open_mainfile(filepath=path)
        return response_ok(request_id)
    except Exception as e:
        return response_error(request_id, f"Failed to open: {e}")


def handle_save_project(request_id: str, path: str, **kwargs):
    """Save project to file."""
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path)
        return response_ok(request_id)
    except Exception as e:
        return response_error(request_id, f"Failed to save: {e}")


# ── Helper Functions ────────────────────────────────────────────────────────

def _get_tree(create: bool = False):
    """Get or create the OpenComp node tree."""
    for tree in bpy.data.node_groups:
        if tree.bl_idname == 'OC_NT_compositor':
            return tree

    if create:
        return bpy.data.node_groups.new('OpenComp', 'OC_NT_compositor')

    return None


def _get_node_params(node) -> dict:
    """Extract editable parameters from a node."""
    params = {}

    # Get RNA properties
    for prop in node.bl_rna.properties:
        if prop.identifier in ('rna_type', 'name', 'label', 'location', 'select',
                               'show_options', 'show_preview', 'hide', 'mute',
                               'show_texture', 'color', 'use_custom_color',
                               'width', 'width_hidden', 'height', 'parent',
                               'inputs', 'outputs', 'internal_links'):
            continue

        if prop.is_readonly:
            continue

        try:
            value = getattr(node, prop.identifier)
            # Convert to JSON-serializable
            if hasattr(value, '__iter__') and not isinstance(value, str):
                value = list(value)
            params[prop.identifier] = value
        except Exception:
            pass

    return params


# ── Timer and Main Loop ─────────────────────────────────────────────────────

def _poll_server() -> float:
    """Timer callback to poll the IPC server."""
    server = get_server()
    if server and server.poll():
        return 1 / 60  # 60Hz
    return None  # Stop timer


def main():
    """Main entry point for headless backend."""
    import time

    print("[Headless] Entering main()", flush=True)

    print("=" * 60, flush=True)
    print("  OpenComp Headless Backend", flush=True)
    print("=" * 60, flush=True)

    # Enable opencomp_core add-on
    try:
        bpy.ops.preferences.addon_enable(module='opencomp_core')
        print("[Headless] Enabled opencomp_core add-on", flush=True)
    except Exception as e:
        print(f"[Headless] Warning: Could not enable add-on: {e}", flush=True)

    # Create shared memory output
    print("[Headless] Creating shared memory output...", flush=True)
    create_shm_output()
    print("[Headless] Shared memory created", flush=True)

    # Start IPC server
    print("[Headless] Starting IPC server...", flush=True)
    server = start_server()
    print("[Headless] IPC server started", flush=True)

    # Register command handlers
    server.register_handler('get_graph_state', handle_get_graph_state)
    server.register_handler('node_create', handle_node_create)
    server.register_handler('node_delete', handle_node_delete)
    server.register_handler('node_move', handle_node_move)
    server.register_handler('node_set_param', handle_node_set_param)
    server.register_handler('connect', handle_connect)
    server.register_handler('disconnect', handle_disconnect)
    server.register_handler('evaluate', handle_evaluate)
    server.register_handler('get_viewer_buffer', handle_get_viewer_buffer)
    server.register_handler('get_node_types', handle_get_node_types)
    server.register_handler('new_project', handle_new_project)
    server.register_handler('open_project', handle_open_project)
    server.register_handler('save_project', handle_save_project)

    print("[Headless] Registered command handlers", flush=True)
    print("[Headless] Ready for connections", flush=True)
    print("=" * 60, flush=True)

    # Keep Blender running in background mode
    # We manually poll the server in a loop instead of using timers
    # because timers don't work reliably in --background mode
    try:
        while True:
            server.poll()
            time.sleep(1 / 60)  # 60Hz polling
    except KeyboardInterrupt:
        print("[Headless] Shutting down...")
    finally:
        cleanup()


def cleanup():
    """Cleanup on shutdown."""
    stop_server()
    close_shm_output()


# Register cleanup handler
import atexit
atexit.register(cleanup)

# Run main - always run when loaded by Blender (not as module import)
# Note: __name__ is not "__main__" when run via blender --python
print(f"[Headless] __name__ = {__name__}, bpy in modules = {'bpy' in sys.modules}", flush=True)
if __name__ == "__main__" or "bpy" in sys.modules:
    print("[Headless] Calling main()...", flush=True)
    main()
