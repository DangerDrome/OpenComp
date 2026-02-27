"""OpenComp IPC Server — Blender side Unix socket server.

Receives commands from Qt canvas, applies them to OpenCompNodeTree,
and sends responses back.

Auto-starts when add-on registers, polls via bpy.app.timers at 60Hz.
"""

import socket
import pathlib
import select
from typing import Optional, Dict

from .protocol import (
    SOCKET_PATH,
    decode_message, encode_message,
    response_ok, response_error, response_pong,
    response_graph_state,
    validate_command,
)
from ... import console

# Server state
_server: Optional['IpcServer'] = None


class IpcServer:
    """Unix domain socket server for IPC with Qt canvas."""

    def __init__(self, socket_path: str = SOCKET_PATH):
        self.socket_path = pathlib.Path(socket_path)
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self._recv_buffer = b''
        self._node_id_map: Dict[str, str] = {}  # oc_id -> bpy node name

    def start(self):
        """Start the IPC server."""
        # Clean up stale socket file
        self.socket_path.unlink(missing_ok=True)

        # Create Unix domain socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.setblocking(False)
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(1)

        console.launched(f"IPC Server at {self.socket_path}")

    def stop(self):
        """Stop the IPC server."""
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None

        # Clean up socket file
        self.socket_path.unlink(missing_ok=True)
        console.closed("IPC Server")

    def poll(self):
        """Poll for incoming connections and messages.

        Call this from a bpy.app.timers callback at 60Hz.
        Non-blocking — returns immediately if no data.
        """
        if self.server_socket is None:
            return

        # Accept new connection if available
        if self.client_socket is None:
            self._accept_connection()

        # Process messages from client
        if self.client_socket:
            self._process_messages()

    def _accept_connection(self):
        """Accept a new client connection (non-blocking)."""
        try:
            ready, _, _ = select.select([self.server_socket], [], [], 0)
            if ready:
                self.client_socket, _ = self.server_socket.accept()
                self.client_socket.setblocking(False)
                self._recv_buffer = b''
                self._node_id_map.clear()
                console.success("IPC client connected", "IPC")
        except Exception:
            pass

    def _process_messages(self):
        """Process all pending messages from client."""
        # Read available data
        try:
            ready, _, _ = select.select([self.client_socket], [], [], 0)
            if ready:
                data = self.client_socket.recv(4096)
                if not data:
                    # Client disconnected
                    console.info("IPC client disconnected", "IPC")
                    self.client_socket.close()
                    self.client_socket = None
                    return
                self._recv_buffer += data
        except BlockingIOError:
            pass
        except (ConnectionResetError, BrokenPipeError):
            console.warning("IPC connection lost", "IPC")
            self.client_socket = None
            return

        # Parse complete messages (newline-delimited)
        while b'\n' in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split(b'\n', 1)
            msg = decode_message(line)
            if msg and validate_command(msg):
                response = self._handle_command(msg)
                self._send_response(response)

    def _send_response(self, response: dict):
        """Send a response to the client."""
        if self.client_socket:
            try:
                self.client_socket.sendall(encode_message(response))
            except Exception:
                pass

    def _handle_command(self, msg: dict) -> dict:
        """Handle a command message and return a response.

        Args:
            msg: Command message dict.

        Returns:
            Response dict.
        """
        cmd = msg.get('cmd')

        try:
            if cmd == 'ping':
                return response_pong()

            elif cmd == 'node_created':
                return self._handle_node_created(msg)

            elif cmd == 'node_deleted':
                return self._handle_node_deleted(msg)

            elif cmd == 'port_connected':
                return self._handle_port_connected(msg)

            elif cmd == 'port_disconnected':
                return self._handle_port_disconnected(msg)

            elif cmd == 'param_changed':
                return self._handle_param_changed(msg)

            elif cmd == 'eval_request':
                return self._handle_eval_request(msg)

            elif cmd == 'get_graph_state':
                return self._handle_get_graph_state(msg)

            else:
                return response_error(cmd, f"Unknown command: {cmd}")

        except Exception as e:
            return response_error(cmd, str(e))

    def _get_tree(self):
        """Get the OpenCompNodeTree."""
        import bpy
        for tree in bpy.data.node_groups:
            if tree.bl_idname == 'OC_NT_compositor':
                return tree
        return None

    def _handle_node_created(self, msg: dict) -> dict:
        """Handle node_created command."""
        node_id = msg.get('node_id')
        node_type = msg.get('node_type')
        x = msg.get('x', 0)
        y = msg.get('y', 0)

        tree = self._get_tree()
        if tree is None:
            return response_error('node_created', 'No OpenComp tree found')

        # Create the node
        try:
            node = tree.nodes.new(type=node_type)
            node.location = (x, -y)  # Qt Y is inverted
            node.name = node_id[:8]  # Use first 8 chars of UUID

            # Store mapping
            self._node_id_map[node_id] = node.name

            return response_ok('node_created', bpy_name=node.name)
        except Exception as e:
            return response_error('node_created', str(e))

    def _handle_node_deleted(self, msg: dict) -> dict:
        """Handle node_deleted command."""
        node_id = msg.get('node_id')

        tree = self._get_tree()
        if tree is None:
            return response_error('node_deleted', 'No OpenComp tree found')

        bpy_name = self._node_id_map.get(node_id)
        if not bpy_name:
            return response_error('node_deleted', f'Unknown node: {node_id}')

        node = tree.nodes.get(bpy_name)
        if node:
            tree.nodes.remove(node)
            del self._node_id_map[node_id]
            return response_ok('node_deleted')
        else:
            return response_error('node_deleted', f'Node not found: {bpy_name}')

    def _handle_port_connected(self, msg: dict) -> dict:
        """Handle port_connected command."""
        from_node_id = msg.get('from_node')
        from_port = msg.get('from_port')
        to_node_id = msg.get('to_node')
        to_port = msg.get('to_port')

        tree = self._get_tree()
        if tree is None:
            return response_error('port_connected', 'No OpenComp tree found')

        # Get node names
        from_name = self._node_id_map.get(from_node_id)
        to_name = self._node_id_map.get(to_node_id)

        if not from_name or not to_name:
            return response_error('port_connected', 'Unknown node(s)')

        from_node = tree.nodes.get(from_name)
        to_node = tree.nodes.get(to_name)

        if not from_node or not to_node:
            return response_error('port_connected', 'Node(s) not found')

        # Find sockets by name
        output = None
        for out in from_node.outputs:
            if out.name == from_port or out.identifier == from_port:
                output = out
                break

        input_ = None
        for inp in to_node.inputs:
            if inp.name == to_port or inp.identifier == to_port:
                input_ = inp
                break

        if not output or not input_:
            return response_error('port_connected', 'Socket(s) not found')

        # Create link
        tree.links.new(output, input_)
        return response_ok('port_connected')

    def _handle_port_disconnected(self, msg: dict) -> dict:
        """Handle port_disconnected command."""
        from_node_id = msg.get('from_node')
        from_port = msg.get('from_port')
        to_node_id = msg.get('to_node')
        to_port = msg.get('to_port')

        tree = self._get_tree()
        if tree is None:
            return response_error('port_disconnected', 'No OpenComp tree found')

        # Find and remove matching link
        for link in list(tree.links):
            from_match = (self._node_id_map.get(from_node_id) == link.from_node.name
                         and link.from_socket.name == from_port)
            to_match = (self._node_id_map.get(to_node_id) == link.to_node.name
                       and link.to_socket.name == to_port)
            if from_match and to_match:
                tree.links.remove(link)
                return response_ok('port_disconnected')

        return response_error('port_disconnected', 'Link not found')

    def _handle_param_changed(self, msg: dict) -> dict:
        """Handle param_changed command."""
        node_id = msg.get('node_id')
        param = msg.get('param')
        value = msg.get('value')

        tree = self._get_tree()
        if tree is None:
            return response_error('param_changed', 'No OpenComp tree found')

        bpy_name = self._node_id_map.get(node_id)
        if not bpy_name:
            return response_error('param_changed', f'Unknown node: {node_id}')

        node = tree.nodes.get(bpy_name)
        if not node:
            return response_error('param_changed', f'Node not found: {bpy_name}')

        # Set property
        try:
            if hasattr(node, param):
                setattr(node, param, value)
                return response_ok('param_changed')
            else:
                return response_error('param_changed', f'Unknown param: {param}')
        except Exception as e:
            return response_error('param_changed', str(e))

    def _handle_eval_request(self, msg: dict) -> dict:
        """Handle eval_request command."""
        viewer_node_id = msg.get('viewer_node_id')

        # Trigger evaluation (will be implemented in Phase 3)
        # For now, just acknowledge
        return response_ok('eval_request', node_id=viewer_node_id)

    def _handle_get_graph_state(self, msg: dict) -> dict:
        """Handle get_graph_state command."""
        tree = self._get_tree()
        if tree is None:
            return response_graph_state([], [])

        nodes = []
        links = []

        # Serialize nodes
        for node in tree.nodes:
            # Find oc_id (reverse lookup)
            oc_id = None
            for k, v in self._node_id_map.items():
                if v == node.name:
                    oc_id = k
                    break

            nodes.append({
                'bpy_name': node.name,
                'oc_id': oc_id,
                'type': node.bl_idname,
                'x': node.location.x,
                'y': -node.location.y,  # Invert Y for Qt
            })

        # Serialize links
        for link in tree.links:
            links.append({
                'from_node': link.from_node.name,
                'from_port': link.from_socket.name,
                'to_node': link.to_node.name,
                'to_port': link.to_socket.name,
            })

        return response_graph_state(nodes, links)


# ── Timer callback for bpy.app.timers ───────────────────────────────────────

def _poll_socket() -> float:
    """Timer callback to poll the IPC socket.

    Returns:
        Interval until next call (1/60 second for 60Hz).
    """
    global _server
    if _server:
        _server.poll()
    return 1 / 60  # 60Hz


def start_server():
    """Start the IPC server and register timer."""
    global _server
    import bpy

    if _server is not None:
        return  # Already running

    _server = IpcServer()
    _server.start()

    # Register timer for polling
    if not bpy.app.timers.is_registered(_poll_socket):
        bpy.app.timers.register(_poll_socket)


def stop_server():
    """Stop the IPC server and unregister timer."""
    global _server
    import bpy

    if bpy.app.timers.is_registered(_poll_socket):
        bpy.app.timers.unregister(_poll_socket)

    if _server:
        _server.stop()
        _server = None


def is_running() -> bool:
    """Check if the IPC server is running."""
    return _server is not None and _server.server_socket is not None
