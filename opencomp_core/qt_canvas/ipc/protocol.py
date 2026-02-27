"""OpenComp IPC Protocol — Message schemas for Qt ↔ Blender communication.

All messages are newline-delimited JSON over Unix domain sockets.
Socket path: /tmp/opencomp_ipc.sock
"""

import json
from typing import Optional, List, Any

# Default socket path
SOCKET_PATH = "/tmp/opencomp_ipc.sock"


# ── Command Messages (Qt → Blender) ─────────────────────────────────────────

def cmd_ping() -> dict:
    """Create a ping command."""
    return {"cmd": "ping"}


def cmd_node_created(node_id: str, node_type: str, x: float, y: float) -> dict:
    """Create a node_created command.

    Args:
        node_id: Unique node ID (oc_id from Qt).
        node_type: Node type like 'OC_N_grade'.
        x: X position in graph.
        y: Y position in graph.
    """
    return {
        "cmd": "node_created",
        "node_id": node_id,
        "node_type": node_type,
        "x": x,
        "y": y
    }


def cmd_node_deleted(node_id: str) -> dict:
    """Create a node_deleted command.

    Args:
        node_id: Unique node ID to delete.
    """
    return {
        "cmd": "node_deleted",
        "node_id": node_id
    }


def cmd_port_connected(from_node: str, from_port: str,
                       to_node: str, to_port: str) -> dict:
    """Create a port_connected command.

    Args:
        from_node: Source node ID (output side).
        from_port: Source port name.
        to_node: Target node ID (input side).
        to_port: Target port name.
    """
    return {
        "cmd": "port_connected",
        "from_node": from_node,
        "from_port": from_port,
        "to_node": to_node,
        "to_port": to_port
    }


def cmd_port_disconnected(from_node: str, from_port: str,
                          to_node: str, to_port: str) -> dict:
    """Create a port_disconnected command.

    Args:
        from_node: Source node ID (output side).
        from_port: Source port name.
        to_node: Target node ID (input side).
        to_port: Target port name.
    """
    return {
        "cmd": "port_disconnected",
        "from_node": from_node,
        "from_port": from_port,
        "to_node": to_node,
        "to_port": to_port
    }


def cmd_param_changed(node_id: str, param: str, value: Any) -> dict:
    """Create a param_changed command.

    Args:
        node_id: Node ID to update.
        param: Parameter name.
        value: New value (must be JSON-serializable).
    """
    return {
        "cmd": "param_changed",
        "node_id": node_id,
        "param": param,
        "value": value
    }


def cmd_eval_request(viewer_node_id: str) -> dict:
    """Create an eval_request command.

    Args:
        viewer_node_id: ID of the viewer node to evaluate.
    """
    return {
        "cmd": "eval_request",
        "viewer_node_id": viewer_node_id
    }


def cmd_get_graph_state() -> dict:
    """Create a get_graph_state command."""
    return {"cmd": "get_graph_state"}


# ── Response Messages (Blender → Qt) ────────────────────────────────────────

def response_ok(cmd: str, **kwargs) -> dict:
    """Create an OK response.

    Args:
        cmd: The command that succeeded.
        **kwargs: Additional response data.
    """
    return {"status": "ok", "cmd": cmd, **kwargs}


def response_error(cmd: str, message: str) -> dict:
    """Create an error response.

    Args:
        cmd: The command that failed.
        message: Error description.
    """
    return {"status": "error", "cmd": cmd, "message": message}


def response_pong() -> dict:
    """Create a pong response."""
    return {"status": "pong"}


def response_eval_complete(node_id: str, width: int, height: int) -> dict:
    """Create an eval_complete response.

    Args:
        node_id: ID of the evaluated viewer node.
        width: Output image width.
        height: Output image height.
    """
    return {
        "status": "eval_complete",
        "node_id": node_id,
        "width": width,
        "height": height
    }


def response_graph_state(nodes: List[dict], links: List[dict]) -> dict:
    """Create a graph_state response.

    Args:
        nodes: List of node data dicts.
        links: List of link data dicts.
    """
    return {
        "status": "graph_state",
        "nodes": nodes,
        "links": links
    }


# ── Message Encoding/Decoding ───────────────────────────────────────────────

def encode_message(msg: dict) -> bytes:
    """Encode a message dict to bytes for transmission.

    Args:
        msg: Message dictionary.

    Returns:
        UTF-8 encoded JSON with newline terminator.
    """
    return (json.dumps(msg) + '\n').encode('utf-8')


def decode_message(data: bytes) -> Optional[dict]:
    """Decode a message from bytes.

    Args:
        data: UTF-8 encoded JSON bytes (with or without newline).

    Returns:
        Message dict or None if invalid.
    """
    try:
        text = data.decode('utf-8').strip()
        if not text:
            return None
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def validate_command(msg: dict) -> bool:
    """Validate a command message structure.

    Args:
        msg: Message to validate.

    Returns:
        True if valid command, False otherwise.
    """
    if not isinstance(msg, dict):
        return False
    if 'cmd' not in msg:
        return False

    cmd = msg.get('cmd')
    valid_commands = {
        'ping', 'node_created', 'node_deleted',
        'port_connected', 'port_disconnected',
        'param_changed', 'eval_request', 'get_graph_state'
    }
    return cmd in valid_commands


def validate_response(msg: dict) -> bool:
    """Validate a response message structure.

    Args:
        msg: Message to validate.

    Returns:
        True if valid response, False otherwise.
    """
    if not isinstance(msg, dict):
        return False
    return 'status' in msg
