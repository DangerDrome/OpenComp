"""OpenComp Server — Unix socket IPC server for Electron frontend.

This server runs inside Blender's Python environment in headless mode.
It receives commands from the Electron app, executes them via opencomp_core,
and sends responses back.

Usage:
    blender --background --python opencomp_server/headless.py
"""

import socket
import select
import pathlib
import uuid
from typing import Optional, Dict, Any, Callable

from .protocol import (
    SOCKET_PATH,
    encode_message, decode_message,
    validate_request,
    response_ok, response_error, response_pong, response_version,
    response_graph_state, response_node_types, response_viewer_buffer,
    event_viewer_updated, event_graph_changed,
)


class OpenCompServer:
    """Unix domain socket server for IPC with Electron frontend."""

    def __init__(self, socket_path: str = SOCKET_PATH):
        self.socket_path = pathlib.Path(socket_path)
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self._recv_buffer = b''
        self._running = False

        # Command handlers (registered by headless.py)
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, cmd: str, handler: Callable):
        """Register a command handler.

        Args:
            cmd: Command name.
            handler: Callable that takes (request_id, **params) and returns response dict.
        """
        self._handlers[cmd] = handler

    def start(self):
        """Start the IPC server."""
        # Clean up stale socket file
        self.socket_path.unlink(missing_ok=True)

        # Create Unix domain socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.setblocking(False)
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(1)

        self._running = True
        print(f"[OpenComp Server] Listening on {self.socket_path}")

    def stop(self):
        """Stop the IPC server."""
        self._running = False

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
        print("[OpenComp Server] Stopped")

    def poll(self) -> bool:
        """Poll for incoming connections and messages.

        Call this from a bpy.app.timers callback.
        Non-blocking — returns immediately if no data.

        Returns:
            True if server is still running, False if stopped.
        """
        if not self._running or self.server_socket is None:
            return False

        # Accept new connection if available
        if self.client_socket is None:
            self._accept_connection()

        # Process messages from client
        if self.client_socket:
            self._process_messages()

        return True

    def send_event(self, event: Dict[str, Any]):
        """Send an event to the connected client."""
        if self.client_socket:
            try:
                self.client_socket.sendall(encode_message(event))
            except Exception:
                pass

    def _accept_connection(self):
        """Accept a new client connection (non-blocking)."""
        try:
            ready, _, _ = select.select([self.server_socket], [], [], 0)
            if ready:
                self.client_socket, _ = self.server_socket.accept()
                self.client_socket.setblocking(False)
                self._recv_buffer = b''
                print("[OpenComp Server] Client connected")
        except Exception:
            pass

    def _process_messages(self):
        """Process all pending messages from client."""
        # Read available data
        try:
            ready, _, _ = select.select([self.client_socket], [], [], 0)
            if ready:
                data = self.client_socket.recv(65536)
                if not data:
                    # Client disconnected
                    print("[OpenComp Server] Client disconnected")
                    self.client_socket.close()
                    self.client_socket = None
                    return
                self._recv_buffer += data
        except BlockingIOError:
            pass
        except (ConnectionResetError, BrokenPipeError):
            print("[OpenComp Server] Connection lost")
            self.client_socket = None
            return

        # Parse complete messages (newline-delimited)
        while b'\n' in self._recv_buffer:
            line, self._recv_buffer = self._recv_buffer.split(b'\n', 1)
            msg = decode_message(line)
            if msg:
                response = self._handle_request(msg)
                self._send_response(response)

    def _send_response(self, response: Dict[str, Any]):
        """Send a response to the client."""
        if self.client_socket:
            try:
                self.client_socket.sendall(encode_message(response))
            except Exception:
                pass

    def _handle_request(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request message and return a response."""
        request_id = msg.get('id', str(uuid.uuid4()))
        cmd = msg.get('cmd', '')

        # Validate request
        error = validate_request(msg)
        if error:
            return response_error(request_id, error)

        # Handle built-in commands
        if cmd == 'ping':
            return response_pong(request_id)

        if cmd == 'get_version':
            from . import __version__
            return response_version(request_id, __version__)

        # Dispatch to registered handler
        handler = self._handlers.get(cmd)
        if handler:
            try:
                # Extract params (exclude cmd and id)
                params = {k: v for k, v in msg.items() if k not in ('cmd', 'id')}
                return handler(request_id, **params)
            except Exception as e:
                return response_error(request_id, str(e))

        return response_error(request_id, f"No handler for command: {cmd}")


# ── Module-level server instance ────────────────────────────────────────────

_server: Optional[OpenCompServer] = None


def get_server() -> Optional[OpenCompServer]:
    """Get the global server instance."""
    return _server


def start_server(socket_path: str = SOCKET_PATH) -> OpenCompServer:
    """Start the global server instance."""
    global _server
    if _server is not None:
        return _server

    _server = OpenCompServer(socket_path)
    _server.start()
    return _server


def stop_server():
    """Stop the global server instance."""
    global _server
    if _server:
        _server.stop()
        _server = None
