"""Generate startup.blend for OpenComp v0.2.

Run in GUI mode:
    ./blender/blender --factory-startup --python app_template/_generate_startup_v2.py

Creates a compositor layout:
- VIEW_3D (viewer, top) with black background
- DOPESHEET (timeline, thin strip below viewer)
- NODE_EDITOR (node graph, large, bottom)
- PROPERTIES (right side)
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
    scene.frame_current = 1001


def _configure_viewer_area(area):
    """Configure VIEW_3D as a clean, black-background viewer - hide toolbar until node-specific tools exist."""
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            # Hide toolbar until we have context-sensitive node tools
            space.show_region_toolbar = False
            space.show_region_ui = False
            space.show_region_tool_header = False
            space.show_gizmo = False
            space.overlay.show_overlays = False
            # Black background
            space.shading.type = 'SOLID'
            space.shading.background_type = 'VIEWPORT'
            space.shading.background_color = (0.0, 0.0, 0.0)


def _build_layout():
    """Build the compositor layout."""
    global _phase

    window = bpy.context.window
    if window is None:
        return 0.1
    screen = window.screen

    if _phase == 0:
        # Phase 0: Initial area type conversion
        print("[Gen] Phase 0: Setting up area types")
        for area in screen.areas:
            print(f"  {area.type}: {area.width}x{area.height} at y={area.y}")

        # Join OUTLINER into PROPERTIES (don't create a second PROPERTIES panel)
        outliner = None
        properties = None
        for area in screen.areas:
            if area.type == 'OUTLINER':
                outliner = area
            elif area.type == 'PROPERTIES':
                properties = area

        if outliner and properties:
            # Join outliner into properties
            try:
                with bpy.context.temp_override(window=window, screen=screen):
                    result = bpy.ops.screen.area_join(
                        source_xy=(properties.x + properties.width // 2,
                                   properties.y + properties.height // 2),
                        target_xy=(outliner.x + outliner.width // 2,
                                   outliner.y + outliner.height // 2)
                    )
                    print(f"  Joined OUTLINER into PROPERTIES: {result}")
            except Exception as e:
                print(f"  Join failed, converting OUTLINER to PROPERTIES: {e}")
                outliner.type = 'PROPERTIES'

        _phase = 1
        return 0.1

    if _phase == 1:
        # Phase 1: Split VIEW_3D into viewer (top 35%) and node editor (bottom 65%)
        print("[Gen] Phase 1: Splitting VIEW_3D for viewer + nodes")

        view3d = None
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                view3d = area
                break

        if view3d:
            with bpy.context.temp_override(window=window, area=view3d, screen=screen):
                result = bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.35)
                print(f"  Split VIEW_3D result: {result}")

        _phase = 2
        return 0.1

    if _phase == 2:
        # Phase 2: Configure split areas - top stays VIEW_3D, bottom becomes NODE_EDITOR
        print("[Gen] Phase 2: Configuring viewer and node editor")

        view3d_areas = [a for a in screen.areas if a.type == 'VIEW_3D']
        view3d_areas.sort(key=lambda a: a.y, reverse=True)  # Top first

        if len(view3d_areas) >= 2:
            # Top area stays VIEW_3D (viewer)
            _configure_viewer_area(view3d_areas[0])
            print(f"  Top -> VIEW_3D (viewer): {view3d_areas[0].width}x{view3d_areas[0].height}")

            # Bottom area -> NODE_EDITOR
            view3d_areas[1].type = 'NODE_EDITOR'
            print(f"  Bottom -> NODE_EDITOR: {view3d_areas[1].width}x{view3d_areas[1].height}")
        elif len(view3d_areas) == 1:
            view3d_areas[0].type = 'NODE_EDITOR'
            print(f"  Single -> NODE_EDITOR")

        _phase = 3
        return 0.1

    if _phase == 3:
        # Phase 3: Move DOPESHEET to be between viewer and node editor
        # by joining it with the existing timeline and re-splitting viewer
        print("[Gen] Phase 3: Repositioning timeline under viewer")

        # Find the viewer (VIEW_3D) and split it to create timeline strip
        view3d = None
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                view3d = area
                break

        if view3d:
            # Split viewer horizontally: 80% viewer (top), 20% for timeline (bottom with 2x controls)
            with bpy.context.temp_override(window=window, area=view3d, screen=screen):
                result = bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.20)
                print(f"  Split viewer for timeline: {result}")

        _phase = 4
        return 0.1

    if _phase == 4:
        # Phase 4: Convert the bottom split of viewer to DOPESHEET and configure existing one
        print("[Gen] Phase 4: Setting up timeline areas")

        view3d_areas = [a for a in screen.areas if a.type == 'VIEW_3D']
        view3d_areas.sort(key=lambda a: a.y, reverse=True)  # Top first

        if len(view3d_areas) >= 2:
            # Top stays VIEW_3D (viewer)
            _configure_viewer_area(view3d_areas[0])
            print(f"  Viewer: {view3d_areas[0].width}x{view3d_areas[0].height}")

            # Bottom VIEW_3D becomes DOPESHEET (timeline under viewer)
            timeline_area = view3d_areas[1]
            timeline_area.type = 'DOPESHEET_EDITOR'
            for space in timeline_area.spaces:
                if space.type == 'DOPESHEET_EDITOR':
                    space.mode = 'TIMELINE'
                    space.show_region_ui = False  # Hide right sidebar
                    # Hide the channels/search region on the left
                    try:
                        space.show_region_channels = False
                    except AttributeError:
                        pass
            # Move header to bottom of timeline using operator
            try:
                with bpy.context.temp_override(window=window, area=timeline_area, screen=screen):
                    bpy.ops.screen.region_flip()
            except Exception as e:
                print(f"  Header flip failed: {e}")
            print(f"  Timeline (new): {timeline_area.width}x{timeline_area.height}")

        # Remove the old bottom DOPESHEET by joining it with NODE_EDITOR
        dopesheet_areas = [a for a in screen.areas if a.type == 'DOPESHEET_EDITOR']
        node_areas = [a for a in screen.areas if a.type == 'NODE_EDITOR']

        if len(dopesheet_areas) >= 2 and len(node_areas) >= 1:
            # Find the bottom-most dopesheet (the old one at y=very low)
            dopesheet_areas.sort(key=lambda a: a.y)
            old_dopesheet = dopesheet_areas[0]  # Lowest y
            node_editor = node_areas[0]

            # Try to join old dopesheet into node editor
            try:
                with bpy.context.temp_override(window=window, screen=screen):
                    # source = area to keep, target = area to absorb
                    result = bpy.ops.screen.area_join(
                        source_xy=(node_editor.x + node_editor.width // 2,
                                   node_editor.y + node_editor.height // 2),
                        target_xy=(old_dopesheet.x + old_dopesheet.width // 2,
                                   old_dopesheet.y + old_dopesheet.height // 2)
                    )
                    print(f"  Join old timeline into node editor: {result}")
            except Exception as e:
                print(f"  Join failed: {e}")

        _phase = 5
        return 0.1

    if _phase == 5:
        # Phase 5: Configure preferences and VIEW_3D theme
        print("[Gen] Phase 5: Configuring preferences")

        prefs = bpy.context.preferences
        prefs.view.show_splash = False

        # Keep icons visible
        theme = prefs.themes[0]
        theme.user_interface.icon_alpha = 1.0

        # Set VIEW_3D background to very dark
        try:
            theme.view_3d.space.back = (0.05, 0.05, 0.05)
        except Exception:
            pass

        _phase = 6
        return 0.1

    if _phase == 6:
        # Phase 6: Save and quit
        print("[Gen] Phase 6: Saving startup.blend")

        # Log final layout
        for area in screen.areas:
            print(f"  {area.type}: {area.width}x{area.height} at y={area.y}")

        bpy.ops.wm.save_mainfile(filepath=str(OUTPUT))
        print(f"[Gen] Saved: {OUTPUT}")

        bpy.ops.wm.quit_blender()
        return None


def main():
    print("[Gen] Generating OpenComp v0.2 startup.blend")

    _clear_default_objects()
    _setup_scene()

    # Defer layout building
    bpy.app.timers.register(_build_layout, first_interval=0.3)


# Run immediately when loaded by Blender
main()
