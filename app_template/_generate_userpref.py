"""Generate userpref.blend for the OpenComp app template.

Run in GUI mode (NOT --background):

    ./blender/blender --factory-startup --python app_template/_generate_userpref.py

Creates a userpref.blend that:
- Skips the Quick Setup dialog on first launch
- Sets OpenComp-appropriate preferences (dark theme, zoom to mouse, etc.)
"""

import bpy
import pathlib
import shutil

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "app_template" / "userpref.blend"


def _configure_preferences():
    """Set preferences suitable for OpenComp."""
    prefs = bpy.context.preferences

    # Input
    prefs.inputs.use_zoom_to_mouse = True

    # View
    prefs.view.show_splash = True  # We override the splash content anyway
    prefs.view.show_developer_ui = False

    # Theme - dark
    try:
        theme = prefs.themes[0]
        theme.user_interface.wcol_regular.inner = (0.22, 0.22, 0.22, 1.0)
        theme.node_editor.space.back = (0.16, 0.16, 0.16)
        theme.node_editor.wire = (0.5, 0.5, 0.5, 1.0)
        theme.node_editor.wire_select = (1.0, 1.0, 1.0, 1.0)
    except Exception as e:
        print(f"[Gen] Theme warning: {e}")

    # Auto-save preferences
    prefs.use_preferences_save = True

    print("[Gen] Preferences configured")


def _save_and_quit():
    """Save userpref.blend and quit."""
    # First save to Blender's user location
    bpy.ops.wm.save_userpref()

    # Find where Blender saved it
    possible_paths = [
        pathlib.Path(bpy.utils.resource_path('USER')) / "config" / "userpref.blend",
        pathlib.Path.home() / ".config" / "blender" / "5.0" / "config" / "userpref.blend",
        pathlib.Path.home() / ".config" / "blender" / "5.1" / "config" / "userpref.blend",
    ]

    copied = False
    for user_prefs_path in possible_paths:
        if user_prefs_path.exists():
            shutil.copy(user_prefs_path, OUTPUT)
            print(f"[Gen] userpref.blend saved → {OUTPUT}")
            print(f"[Gen] (copied from {user_prefs_path})")
            copied = True
            break

    if not copied:
        print(f"[Gen] ERROR: Could not find userpref.blend to copy")
        print(f"[Gen] Checked: {possible_paths}")

    bpy.ops.wm.quit_blender()
    return None


def main():
    print("[Gen] Generating OpenComp userpref.blend")
    _configure_preferences()
    # Defer save to ensure prefs are fully applied
    bpy.app.timers.register(_save_and_quit, first_interval=0.3)


if __name__ == "__main__":
    main()
