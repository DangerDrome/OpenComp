"""OpenComp IPC Client — Qt side Unix socket client.

Sends commands to Blender, receives responses.
Runs in a QThread to avoid blocking the Qt event loop.
"""

import socket
import time
from typing import Optional, Dict, Any

from qtpy.QtCore import QThread, Signal, QMutex, QWaitCondition

from .protocol import (
    SOCKET_PATH,
    encode_message, decode_message,
    validate_response,
    cmd_ping,
)


class IpcClient(QThread):
    """Unix socket client for IPC with Blender.

    Runs in a separate thread, emits signals when responses arrive.
    """

    # Signals
    connected = Signal()
    disconnected = Signal()
    message_received = Signal(dict)
    error = Signal(str)

    def __init__(self, socket_path: str = SOCKET_PATH, parent=None):
        super().__init__(parent)
        self.socket_path = socket_path
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._recv_buffer = b''

        # For synchronous request/response
        self._response_mutex = QMutex()
        self._response_condition = QWaitCondition()
        self._pending_response: Optional[dict] = None

    def run(self):
        """Thread main loop — connect and read messages."""
        self._running = True

        while self._running:
            if self._socket is None:
                if not self._try_connect():
                    # Wait before retry
                    time.sleep(1.0)
                    continue

            # Read messages
            try:
                data = self._socket.recv(4096)
                if not data:
                    # Server disconnected
                    self._handle_disconnect()
                    continue

                self._recv_buffer += data

                # Parse complete messages
                while b'\n' in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split(b'\n', 1)
                    msg = decode_message(line)
                    if msg and validate_response(msg):
                        self._handle_response(msg)

            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError, OSError):
                self._handle_disconnect()

    def _try_connect(self) -> bool:
        """Attempt to connect to the server.

        Returns:
            True if connected, False otherwise.
        """
        try:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.settimeout(0.1)  # 100ms read timeout
            self._socket.connect(self.socket_path)
            self._recv_buffer = b''
            self.connected.emit()
            return True
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            self._socket = None
            return False

    def _handle_disconnect(self):
        """Handle server disconnection."""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
        self._recv_buffer = b''
        self.disconnected.emit()

    def _handle_response(self, msg: dict):
        """Handle an incoming response message."""
        # Check if this is a response to a synchronous request
        self._response_mutex.lock()
        self._pending_response = msg
        self._response_condition.wakeAll()
        self._response_mutex.unlock()

        # Also emit signal for async handling
        self.message_received.emit(msg)

    def stop(self):
        """Stop the client thread."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
        self.wait(2000)  # Wait up to 2 seconds for thread to finish

    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self._socket is not None

    def send_command(self, msg: dict, timeout_ms: int = 5000) -> Optional[dict]:
        """Send a command and wait for response (synchronous).

        Args:
            msg: Command message dict.
            timeout_ms: Timeout in milliseconds.

        Returns:
            Response dict or None on timeout/error.
        """
        if not self._socket:
            return None

        # Clear pending response
        self._response_mutex.lock()
        self._pending_response = None
        self._response_mutex.unlock()

        # Send command
        try:
            self._socket.sendall(encode_message(msg))
        except:
            self.error.emit("Failed to send command")
            return None

        # Wait for response
        self._response_mutex.lock()
        if self._pending_response is None:
            self._response_condition.wait(self._response_mutex, timeout_ms)
        response = self._pending_response
        self._pending_response = None
        self._response_mutex.unlock()

        return response

    def send_async(self, msg: dict) -> bool:
        """Send a command without waiting for response (asynchronous).

        Args:
            msg: Command message dict.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._socket:
            return False

        try:
            self._socket.sendall(encode_message(msg))
            return True
        except:
            return False

    def ping(self, timeout_ms: int = 1000) -> bool:
        """Send a ping and wait for pong.

        Args:
            timeout_ms: Timeout in milliseconds.

        Returns:
            True if pong received, False otherwise.
        """
        response = self.send_command(cmd_ping(), timeout_ms)
        return response is not None and response.get('status') == 'pong'


class IpcClientSync:
    """Synchronous IPC client for simpler use cases.

    Use this when you don't need the async QThread approach.
    """

    def __init__(self, socket_path: str = SOCKET_PATH):
        self.socket_path = socket_path
        self._socket: Optional[socket.socket] = None

    def connect(self, timeout: float = 5.0) -> bool:
        """Connect to the server.

        Args:
            timeout: Connection timeout in seconds.

        Returns:
            True if connected, False otherwise.
        """
        try:
            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.settimeout(timeout)
            self._socket.connect(self.socket_path)
            return True
        except:
            self._socket = None
            return False

    def close(self):
        """Close the connection."""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None

    def send_command(self, msg: dict, timeout: float = 5.0) -> Optional[dict]:
        """Send a command and wait for response.

        Args:
            msg: Command message dict.
            timeout: Timeout in seconds.

        Returns:
            Response dict or None on timeout/error.
        """
        if not self._socket:
            return None

        try:
            self._socket.settimeout(timeout)
            self._socket.sendall(encode_message(msg))

            # Read response
            data = b''
            while b'\n' not in data:
                chunk = self._socket.recv(4096)
                if not chunk:
                    return None
                data += chunk

            line, _ = data.split(b'\n', 1)
            return decode_message(line)

        except:
            return None

    def ping(self) -> bool:
        """Send ping and check for pong."""
        response = self.send_command(cmd_ping())
        return response is not None and response.get('status') == 'pong'

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._socket is not None
