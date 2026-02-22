"""Generate startup.blend for the OpenComp app template.

Run in GUI mode (NOT --background) so area operators work:

    ./blender/blender --factory-startup --python app_template/_generate_startup.py

A Blender window appears briefly while the layout is built, then quits.

Creates a startup.blend with:
- Default objects removed (cube, camera, light)
- Scene defaults set for compositing (1920x1080, 24fps, 1001-1100)
- Dark theme applied
- Status bar hidden
- Nuke-style layout: VIEW_3D (38%) + NODE_EDITOR (62%) + PROPERTIES (right)
"""

import bpy
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "app_template" / "startup.blend"

_phase = 0


def _clear_default_objects():
    """Remove default cube, camera, light."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for cam in list(bpy.data.cameras):
        bpy.data.cameras.remove(cam, do_unlink=True)
    for light in list(bpy.data.lights):
        bpy.data.lights.remove(light, do_unlink=True)


def _setup_scene():
    """Configure scene defaults for compositing."""
    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.fps = 24
    scene.frame_start = 1001
    scene.frame_end = 1100


def _apply_theme():
    """Apply dark theme suitable for compositing."""
    try:
        prefs = bpy.context.preferences
        theme = prefs.themes[0]

        # General UI
        theme.user_interface.wcol_regular.inner = (0.22, 0.22, 0.22, 1.0)

        # Node editor - dark background (back is RGB, wire is RGBA)
        theme.node_editor.space.back = (0.16, 0.16, 0.16)
        theme.node_editor.wire = (0.5, 0.5, 0.5, 1.0)
        theme.node_editor.wire_select = (1.0, 1.0, 1.0, 1.0)

        # Hide status bar for cleaner look
        for screen in bpy.data.screens:
            screen.show_statusbar = False
    except Exception as e:
        print(f"[Gen] Theme warning: {e}")


def _area_center(area):
    """Return (x, y) center of a screen area."""
    return (area.x + area.width // 2, area.y + area.height // 2)


def _join_areas(window, screen, keep_area, remove_area):
    """Join two adjacent areas. keep_area stays, remove_area is absorbed.

    Blender 5.0 uses source_xy / target_xy (not cursor).
    """
    sx, sy = _area_center(keep_area)
    tx, ty = _area_center(remove_area)
    with bpy.context.temp_override(window=window, screen=screen):
        return bpy.ops.screen.area_join(source_xy=(sx, sy), target_xy=(tx, ty))


def _build_layout():
    """Multi-phase timer to build the Nuke-style layout.

    Default Blender "Layout" workspace areas:
    ┌─────────────────┬──────────┐
    │   VIEW_3D       │ OUTLINER │
    │   (large ~70%)  │          │
    ├─────────────────┼──────────┤
    │ DOPESHEET_EDITOR│PROPERTIES│
    │   (small ~30%)  │          │
    └─────────────────┴──────────┘

    Target:
    ┌─────────────────┬──────────┐
    │   VIEW_3D       │          │
    │   (~38%)        │PROPERTIES│
    ├─────────────────┤          │
    │   NODE_EDITOR   │          │
    │   (~62%)        │          │
    └─────────────────┴──────────┘
    """
    global _phase

    window = bpy.context.window
    if window is None:
        return 0.1
    screen = window.screen

    if _phase == 0:
        # ── Phase 0: Convert area types ──────────────────────────────
        print("[Gen] Phase 0: Converting area types")
        for area in screen.areas:
            print(f"  {area.type:20s} ({area.x}, {area.y}) {area.width}x{area.height}")
            if area.type == 'DOPESHEET_EDITOR':
                area.type = 'NODE_EDITOR'
            elif area.type == 'OUTLINER':
                area.type = 'PROPERTIES'
        _phase = 1
        return 0.1

    if _phase == 1:
        # ── Phase 1: Join two PROPERTIES areas into one ──────────────
        print("[Gen] Phase 1: Joining PROPERTIES areas")
        props = [a for a in screen.areas if a.type == 'PROPERTIES']
        if len(props) >= 2:
            props.sort(key=lambda a: a.y)
            bot, top = props[0], props[1]
            try:
                result = _join_areas(window, screen, keep_area=bot, remove_area=top)
                print(f"  Join result: {result}")
            except Exception as e:
                print(f"  Join failed: {e}")
        else:
            print("  Only one PROPERTIES area — skip")
        _phase = 2
        return 0.1

    if _phase == 2:
        # ── Phase 2: Join VIEW_3D + NODE_EDITOR into one left area ───
        print("[Gen] Phase 2: Joining left column areas")
        view3d = None
        node_ed = None
        for area in screen.areas:
            if area.type == 'VIEW_3D' and view3d is None:
                view3d = area
            elif area.type == 'NODE_EDITOR' and node_ed is None:
                node_ed = area

        if view3d and node_ed:
            try:
                result = _join_areas(window, screen, keep_area=view3d, remove_area=node_ed)
                print(f"  Join result: {result}")
            except Exception as e:
                print(f"  Join failed: {e}")
                # Fallback: skip the re-split, keep default proportions
                _phase = 4
                return 0.1
        _phase = 3
        return 0.1

    if _phase == 3:
        # ── Phase 3: Re-split left area at 38/62 proportions ─────────
        # After join, the left side is one big VIEW_3D area.
        # Split HORIZONTAL with factor=0.62:
        #   bottom 62% → NODE_EDITOR (large, for the node graph)
        #   top    38% → VIEW_3D    (smaller, for the viewer)
        print("[Gen] Phase 3: Splitting left column at 38/62")
        left_area = None
        for area in screen.areas:
            if area.type in ('VIEW_3D', 'NODE_EDITOR'):
                left_area = area
                break

        if left_area:
            areas_before = set(id(a) for a in screen.areas)
            try:
                with bpy.context.temp_override(window=window, area=left_area, screen=screen):
                    result = bpy.ops.screen.area_split(
                        direction='HORIZONTAL', factor=0.62
                    )
                    print(f"  Split result: {result}")
            except Exception as e:
                print(f"  Split failed: {e}")
                _phase = 4
                return 0.1

            # Identify the new (top) area and set types
            for area in screen.areas:
                if id(area) not in areas_before:
                    # New area is the top portion → VIEW_3D (viewer)
                    area.type = 'VIEW_3D'
                    print(f"  Top area → VIEW_3D ({area.width}x{area.height})")

            # Original area is the bottom portion → NODE_EDITOR
            if left_area.type != 'NODE_EDITOR':
                left_area.type = 'NODE_EDITOR'
            print(f"  Bottom area → NODE_EDITOR ({left_area.width}x{left_area.height})")

        _phase = 4
        return 0.1

    if _phase == 4:
        # ── Phase 4: Log final layout, save, quit ────────────────────
        print("[Gen] Final layout:")
        for area in screen.areas:
            print(f"  {area.type:20s} ({area.x}, {area.y}) {area.width}x{area.height}")

        bpy.ops.wm.save_mainfile(filepath=str(OUTPUT))
        print(f"[Gen] startup.blend saved → {OUTPUT}")

        bpy.ops.wm.quit_blender()
        return None


def main():
    print("[Gen] Generating OpenComp startup.blend (GUI mode)")

    _clear_default_objects()
    _setup_scene()
    _apply_theme()

    # Defer layout building — window must be fully ready
    bpy.app.timers.register(_build_layout, first_interval=0.3)


if __name__ == "__main__":
    main()
