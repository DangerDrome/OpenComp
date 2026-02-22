"""Phase 2 Tests — IPC Bridge.

Tests Unix socket communication between Qt canvas and Blender.
"""

import sys
import os
import time
import pathlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_protocol_imports():
    """Protocol module imports correctly."""
    try:
        from opencomp_core.qt_canvas.ipc.protocol import (
            SOCKET_PATH,
            cmd_ping, cmd_node_created, cmd_node_deleted,
            cmd_port_connected, cmd_port_disconnected,
            cmd_param_changed, cmd_eval_request,
            encode_message, decode_message,
            validate_command, validate_response,
        )
        print("  ✓ Protocol module imports correctly")
        return True
    except Exception as e:
        print(f"  ✗ Protocol import failed: {e}")
        return False


def test_message_encoding():
    """Message encoding/decoding works correctly."""
    try:
        from opencomp_core.qt_canvas.ipc.protocol import (
            encode_message, decode_message, cmd_ping
        )

        # Test encode
        msg = cmd_ping()
        encoded = encode_message(msg)
        assert isinstance(encoded, bytes)
        assert encoded.endswith(b'\n')

        # Test decode
        decoded = decode_message(encoded)
        assert decoded == msg

        print("  ✓ Message encoding/decoding works")
        return True
    except Exception as e:
        print(f"  ✗ Message encoding test failed: {e}")
        return False


def test_command_validation():
    """Command validation works correctly."""
    try:
        from opencomp_core.qt_canvas.ipc.protocol import (
            validate_command, validate_response,
            cmd_ping, response_pong
        )

        # Valid command
        assert validate_command(cmd_ping()) == True
        assert validate_command({"cmd": "node_created", "node_id": "123"}) == True

        # Invalid commands
        assert validate_command({}) == False
        assert validate_command({"status": "ok"}) == False
        assert validate_command({"cmd": "invalid_cmd"}) == False

        # Valid response
        assert validate_response(response_pong()) == True
        assert validate_response({"status": "ok", "cmd": "test"}) == True

        # Invalid response
        assert validate_response({}) == False
        assert validate_response({"cmd": "ping"}) == False

        print("  ✓ Command/response validation works")
        return True
    except Exception as e:
        print(f"  ✗ Validation test failed: {e}")
        return False


def test_server_creation():
    """Server creates and starts correctly."""
    try:
        from opencomp_core.qt_canvas.ipc.server import IpcServer
        import pathlib

        test_socket = "/tmp/opencomp_test_ipc.sock"
        pathlib.Path(test_socket).unlink(missing_ok=True)

        server = IpcServer(test_socket)
        server.start()

        # Check socket file exists
        assert pathlib.Path(test_socket).exists(), "Socket file not created"

        server.stop()

        # Check socket file cleaned up
        assert not pathlib.Path(test_socket).exists(), "Socket file not cleaned up"

        print("  ✓ Server creates and starts correctly")
        return True
    except Exception as e:
        print(f"  ✗ Server creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_client_server_connection():
    """Client connects to server."""
    try:
        from opencomp_core.qt_canvas.ipc.server import IpcServer
        from opencomp_core.qt_canvas.ipc.client import IpcClientSync
        import pathlib

        test_socket = "/tmp/opencomp_test_ipc2.sock"
        pathlib.Path(test_socket).unlink(missing_ok=True)

        # Start server
        server = IpcServer(test_socket)
        server.start()

        # Connect client
        client = IpcClientSync(test_socket)
        connected = client.connect(timeout=2.0)
        assert connected, "Client failed to connect"

        # Accept connection on server side
        server.poll()

        # Clean up
        client.close()
        server.stop()

        print("  ✓ Client connects to server")
        return True
    except Exception as e:
        print(f"  ✗ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ping_pong():
    """Ping/pong round trip works."""
    try:
        from opencomp_core.qt_canvas.ipc.server import IpcServer
        from opencomp_core.qt_canvas.ipc.client import IpcClientSync
        from opencomp_core.qt_canvas.ipc.protocol import cmd_ping, encode_message, decode_message
        import pathlib
        import socket
        import threading

        test_socket = "/tmp/opencomp_test_ipc3.sock"
        pathlib.Path(test_socket).unlink(missing_ok=True)

        # Start server
        server = IpcServer(test_socket)
        server.start()

        # Poll server in a thread
        stop_polling = threading.Event()
        def poll_loop():
            while not stop_polling.is_set():
                server.poll()
                time.sleep(0.01)  # 100Hz polling

        poll_thread = threading.Thread(target=poll_loop)
        poll_thread.start()

        # Connect client directly (not via IpcClientSync, to avoid threading)
        client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_sock.settimeout(1.0)
        client_sock.connect(test_socket)

        # Give server time to accept
        time.sleep(0.05)

        # Send ping
        start = time.time()
        client_sock.sendall(encode_message(cmd_ping()))

        # Read response
        data = client_sock.recv(4096)
        elapsed = (time.time() - start) * 1000  # ms

        response = decode_message(data)

        assert response is not None, "No response received"
        assert response.get('status') == 'pong', f"Wrong response: {response}"

        # Clean up
        stop_polling.set()
        poll_thread.join(timeout=1.0)
        client_sock.close()
        server.stop()

        print(f"  ✓ Ping/pong round trip works ({elapsed:.1f}ms)")
        return True
    except Exception as e:
        print(f"  ✗ Ping/pong test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_server_cleanup():
    """Server cleans up socket file on shutdown."""
    try:
        from opencomp_core.qt_canvas.ipc.server import IpcServer
        import pathlib

        test_socket = "/tmp/opencomp_test_ipc4.sock"
        pathlib.Path(test_socket).unlink(missing_ok=True)

        server = IpcServer(test_socket)
        server.start()

        assert pathlib.Path(test_socket).exists()

        server.stop()

        assert not pathlib.Path(test_socket).exists()

        print("  ✓ Server cleans up socket file on shutdown")
        return True
    except Exception as e:
        print(f"  ✗ Cleanup test failed: {e}")
        return False


def run_phase2_tests():
    """Run all Phase 2 tests."""
    print("\n" + "=" * 60)
    print("NodeGraphQt Phase 2 Tests — IPC Bridge")
    print("=" * 60 + "\n")

    tests = [
        ("Protocol Imports", test_protocol_imports),
        ("Message Encoding", test_message_encoding),
        ("Command Validation", test_command_validation),
        ("Server Creation", test_server_creation),
        ("Client-Server Connection", test_client_server_connection),
        ("Ping/Pong Round Trip", test_ping_pong),
        ("Server Cleanup", test_server_cleanup),
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
    print(f"Phase 2 Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_phase2_tests()
    sys.exit(0 if success else 1)
