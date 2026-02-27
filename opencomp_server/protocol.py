"""OpenComp Server Protocol — IPC message definitions.

JSON-based protocol over Unix domain sockets.
All messages are newline-delimited JSON objects.

Request format:
    {"cmd": "command_name", "id": "unique_request_id", ...params}

Response format:
    {"status": "ok"|"error", "id": "request_id", ...data}

Event format (server-initiated):
    {"event": "event_name", ...data}
"""

import json
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

# Socket path
SOCKET_PATH = "/tmp/opencomp_server.sock"

# Shared memory settings
SHM_NAME = "/opencomp_viewer"
SHM_MAX_SIZE = 4096 * 4096 * 4 * 4  # 4K x 4K RGBA32F max


# ── Message Encoding ────────────────────────────────────────────────────────

def encode_message(msg: Dict[str, Any]) -> bytes:
    """Encode a message dict to newline-terminated JSON bytes."""
    return json.dumps(msg, separators=(',', ':')).encode('utf-8') + b'\n'


def decode_message(data: bytes) -> Optional[Dict[str, Any]]:
    """Decode JSON bytes to a message dict."""
    try:
        return json.loads(data.decode('utf-8').strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ── Request Validation ──────────────────────────────────────────────────────

COMMANDS = {
    # Connection
    'ping': [],
    'get_version': [],

    # Graph operations
    'get_graph_state': [],
    'node_create': ['node_type', 'x', 'y'],
    'node_delete': ['node_id'],
    'node_move': ['node_id', 'x', 'y'],
    'node_set_param': ['node_id', 'param', 'value'],

    # Connection operations
    'connect': ['from_node', 'from_port', 'to_node', 'to_port'],
    'disconnect': ['from_node', 'from_port', 'to_node', 'to_port'],

    # Evaluation
    'evaluate': ['viewer_node_id'],
    'get_viewer_buffer': ['viewer_node_id'],

    # Node registry
    'get_node_types': [],

    # Project
    'new_project': [],
    'open_project': ['path'],
    'save_project': ['path'],
}


def validate_request(msg: Dict[str, Any]) -> Optional[str]:
    """Validate a request message.

    Returns:
        None if valid, error message string if invalid.
    """
    cmd = msg.get('cmd')
    if not cmd:
        return "Missing 'cmd' field"

    if cmd not in COMMANDS:
        return f"Unknown command: {cmd}"

    required_params = COMMANDS[cmd]
    for param in required_params:
        if param not in msg:
            return f"Missing required parameter: {param}"

    return None


# ── Response Builders ───────────────────────────────────────────────────────

def response_ok(request_id: str, **data) -> Dict[str, Any]:
    """Build a success response."""
    return {"status": "ok", "id": request_id, **data}


def response_error(request_id: str, message: str) -> Dict[str, Any]:
    """Build an error response."""
    return {"status": "error", "id": request_id, "message": message}


def response_pong(request_id: str) -> Dict[str, Any]:
    """Build a pong response."""
    return {"status": "ok", "id": request_id, "pong": True}


def response_version(request_id: str, version: str) -> Dict[str, Any]:
    """Build a version response."""
    return {"status": "ok", "id": request_id, "version": version}


def response_graph_state(
    request_id: str,
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build a graph state response."""
    return {
        "status": "ok",
        "id": request_id,
        "nodes": nodes,
        "connections": connections,
    }


def response_node_types(
    request_id: str,
    categories: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Build a node types response."""
    return {"status": "ok", "id": request_id, "categories": categories}


def response_viewer_buffer(
    request_id: str,
    shm_name: str,
    width: int,
    height: int,
    channels: int = 4,
    dtype: str = "float32"
) -> Dict[str, Any]:
    """Build a viewer buffer response with shared memory info."""
    return {
        "status": "ok",
        "id": request_id,
        "shm_name": shm_name,
        "width": width,
        "height": height,
        "channels": channels,
        "dtype": dtype,
        "byte_size": width * height * channels * 4,  # float32 = 4 bytes
    }


# ── Event Builders ──────────────────────────────────────────────────────────

def event_viewer_updated(viewer_node_id: str, width: int, height: int) -> Dict[str, Any]:
    """Build a viewer updated event."""
    return {
        "event": "viewer_updated",
        "viewer_node_id": viewer_node_id,
        "width": width,
        "height": height,
    }


def event_graph_changed() -> Dict[str, Any]:
    """Build a graph changed event."""
    return {"event": "graph_changed"}


def event_error(message: str) -> Dict[str, Any]:
    """Build an error event."""
    return {"event": "error", "message": message}
