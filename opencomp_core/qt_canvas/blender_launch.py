"""OpenComp Qt Canvas — Blender launch operator.

Provides a Blender operator to launch the Qt canvas process
and integrate it with the OpenComp workflow.
"""

import subprocess
import sys
import pathlib
import time


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
    from .ipc.protocol import cmd_ping

    client = IpcClientSync(socket_path)
    if not client.connect(timeout=0.5):
        return False

    result = client.ping()
    client.close()
    return result


def launch_canvas(socket_path: str = "/tmp/opencomp_ipc.sock",
                  wait_for_socket: float = 5.0) -> bool:
    """Launch the Qt canvas process.

    Args:
        socket_path: Path to the IPC socket.
        wait_for_socket: Seconds to wait for socket to appear.

    Returns:
        True if launch successful, False otherwise.
    """
    # Check if already running
    if is_canvas_running(socket_path):
        print("[OpenComp] Canvas already running")
        return True

    # Get launch script and Python
    launch_script = get_launch_script_path()
    python = get_python_executable()

    if not launch_script.exists():
        print(f"[OpenComp] Launch script not found: {launch_script}")
        return False

    # Start process
    try:
        process = subprocess.Popen(
            [python, str(launch_script), "--socket-path", socket_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from Blender
        )
    except Exception as e:
        print(f"[OpenComp] Failed to launch canvas: {e}")
        return False

    # Wait for socket to appear
    socket_file = pathlib.Path(socket_path)
    start = time.time()
    while time.time() - start < wait_for_socket:
        if socket_file.exists():
            # Try to ping
            time.sleep(0.2)
            if is_canvas_running(socket_path):
                print("[OpenComp] Canvas launched successfully")
                return True
        time.sleep(0.1)

    print(f"[OpenComp] Canvas did not respond within {wait_for_socket}s")
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
    print("[OpenComp] Launch canvas operator registered")


def unregister_operator():
    """Unregister the launch canvas operator."""
    import bpy

    try:
        bpy.utils.unregister_class(bpy.types.OC_OT_launch_canvas)
    except:
        pass

    # Stop IPC server
    from .ipc.server import stop_server
    stop_server()
