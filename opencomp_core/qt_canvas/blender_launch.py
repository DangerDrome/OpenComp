"""OpenComp Qt Canvas — Blender launch operator.

Provides a Blender operator to launch the Qt canvas process
and integrate it with the OpenComp workflow.
"""

import subprocess
import sys
import pathlib
from .. import console


def get_launch_script_path() -> pathlib.Path:
    """Get the path to the Qt canvas launch script."""
    return pathlib.Path(__file__).parent / "launch.py"


def get_python_executable() -> str:
    """Get the Python executable to use for the Qt process.

    Returns system Python, not Blender's Python, to avoid conflicts.
    """
    # Try system Python
    import shutil
    python = shutil.which("python3") or shutil.which("python")
    if python:
        return python

    # Fall back to Blender's Python (may have Qt conflicts)
    return sys.executable


def is_canvas_running(socket_path: str = "/tmp/opencomp_ipc.sock") -> bool:
    """Check if the Qt canvas process is already running.

    Args:
        socket_path: Path to the IPC socket.

    Returns:
        True if canvas is responding to pings.
    """
    from .ipc.client import IpcClientSync

    client = IpcClientSync(socket_path)
    if not client.connect(timeout=0.5):
        return False

    result = client.ping()
    client.close()
    return result


def launch_canvas(socket_path: str = "/tmp/opencomp_ipc.sock",
                  blocking: bool = False) -> bool:
    """Launch the Qt canvas process.

    Args:
        socket_path: Path to the IPC socket.
        blocking: If True, wait for canvas to be ready. If False, fire and forget.

    Returns:
        True if launch started successfully, False otherwise.
    """
    # Get launch script and Python
    launch_script = get_launch_script_path()
    python = get_python_executable()

    if not launch_script.exists():
        console.error(f"Launch script not found: {launch_script}", "Qt")
        return False

    console.info("Launching Qt canvas...", "Qt")
    console.debug(f"Python: {python}", "Qt")
    console.debug(f"Script: {launch_script}", "Qt")

    # Start process (fire and forget - don't block Blender)
    try:
        process = subprocess.Popen(
            [python, str(launch_script), "--socket-path", socket_path, "--no-connect"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # Detach from Blender
        )
        console.launched(f"Canvas process (PID: {process.pid})")
        return True
    except Exception as e:
        console.error(f"Failed to launch canvas: {e}", "Qt")
        return False


# ── Blender Operator ────────────────────────────────────────────────────────

def register_operator():
    """Register the launch canvas operator with Blender."""
    import bpy

    class OC_OT_launch_canvas(bpy.types.Operator):
        """Launch the OpenComp Qt Node Canvas"""

        bl_idname = "oc.launch_canvas"
        bl_label = "Open Node Canvas"
        bl_description = "Launch the Qt-based node editor canvas"

        def execute(self, context):
            # Start IPC server first
            from .ipc.server import start_server, is_running
            if not is_running():
                start_server()

            # Launch Qt canvas
            if launch_canvas():
                self.report({'INFO'}, "OpenComp Canvas opened")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Failed to launch canvas")
                return {'CANCELLED'}

    bpy.utils.register_class(OC_OT_launch_canvas)
    console.registered("Launch canvas operator")


def unregister_operator():
    """Unregister the launch canvas operator."""
    import bpy

    try:
        bpy.utils.unregister_class(bpy.types.OC_OT_launch_canvas)
    except Exception:
        pass

    # Stop IPC server
    from .ipc.server import stop_server
    stop_server()
