#!/usr/bin/env python3
"""OpenComp Qt Canvas — Entry point.

Launches the NodeGraphQt-based node editor as a standalone application.
Communicates with Blender via Unix domain sockets.

Usage:
    python opencomp_core/qt_canvas/launch.py
    python opencomp_core/qt_canvas/launch.py --socket-path /tmp/custom.sock
"""

import sys
import argparse
from os import environ as os_environ  # Only import environ, not full os module
from pathlib import Path

# Set Qt API before importing qtpy
os_environ.setdefault('QT_API', 'pyside6')

# Add parent directory to path for imports
_this_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_this_dir.parent))

from qtpy.QtWidgets import QApplication  # noqa: E402
from qtpy.QtCore import Qt  # noqa: E402

from ui.main_window import OpenCompMainWindow  # noqa: E402
from ipc.client import IpcClient  # noqa: E402
from ipc.protocol import cmd_get_graph_state  # noqa: E402


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='OpenComp Qt Node Canvas'
    )
    parser.add_argument(
        '--socket-path',
        default='/tmp/opencomp_ipc.sock',
        help='Unix socket path for IPC with Blender'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--no-connect',
        action='store_true',
        help='Do not connect to Blender (standalone mode)'
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("OpenComp")
    app.setOrganizationName("OpenComp")

    # Apply dark palette
    from qtpy.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(200, 200, 200))
    palette.setColor(QPalette.Base, QColor(40, 40, 40))
    palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
    palette.setColor(QPalette.ToolTipText, QColor(200, 200, 200))
    palette.setColor(QPalette.Text, QColor(200, 200, 200))
    palette.setColor(QPalette.Button, QColor(50, 50, 50))
    palette.setColor(QPalette.ButtonText, QColor(200, 200, 200))
    palette.setColor(QPalette.BrightText, QColor(76, 204, 115))
    palette.setColor(QPalette.Link, QColor(76, 204, 115))
    palette.setColor(QPalette.Highlight, QColor(76, 204, 115))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 30))
    app.setPalette(palette)

    # Create main window
    window = OpenCompMainWindow()
    window.show()

    # IPC client (optional)
    ipc_client = None

    if not args.no_connect:
        ipc_client = IpcClient(args.socket_path)

        def on_connected():
            window.set_status("Connected to Blender")
            # Request current graph state
            response = ipc_client.send_command(cmd_get_graph_state(), timeout_ms=2000)
            if response and response.get('status') == 'graph_state':
                from canvas.session import deserialize_graph_state
                deserialize_graph_state(window.graph, response)

        def on_disconnected():
            window.set_status("Disconnected from Blender")

        def on_message(msg):
            # Handle async messages from Blender
            if args.debug:
                print(f"[OpenComp Canvas] Received: {msg}")

        ipc_client.connected.connect(on_connected)
        ipc_client.disconnected.connect(on_disconnected)
        ipc_client.message_received.connect(on_message)

        # Start IPC client thread
        ipc_client.start()

    if args.debug:
        print("[OpenComp Canvas] Started")
        print(f"[OpenComp Canvas] Socket path: {args.socket_path}")

    # Run event loop
    result = app.exec()

    # Cleanup
    if ipc_client:
        ipc_client.stop()

    return result


if __name__ == '__main__':
    sys.exit(main())
