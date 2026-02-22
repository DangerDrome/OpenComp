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

# Set Qt API before importing qtpy
import os
os.environ.setdefault('QT_API', 'pyside6')

from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt

from ui.main_window import OpenCompMainWindow


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
    palette.setColor(QPalette.BrightText, QColor(255, 165, 0))
    palette.setColor(QPalette.Link, QColor(255, 165, 0))
    palette.setColor(QPalette.Highlight, QColor(255, 165, 0))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 30))
    app.setPalette(palette)

    # Create main window
    window = OpenCompMainWindow()
    window.show()

    if args.debug:
        print(f"[OpenComp Canvas] Started")
        print(f"[OpenComp Canvas] Socket path: {args.socket_path}")

    # Run event loop
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
