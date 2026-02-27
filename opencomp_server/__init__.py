"""OpenComp Server — Headless Blender backend for Electron frontend.

This package provides the IPC bridge between the Electron frontend
and Blender running in headless mode with GPU support.

Architecture:
    Electron App ←→ Unix Socket IPC ←→ opencomp_server ←→ opencomp_core
                ←→ Shared Memory (pixel data)
"""

__version__ = "0.1.0"
