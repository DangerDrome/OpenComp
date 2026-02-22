"""OpenComp Viewer — Nuke-style image viewer.

Replaces Blender's 3D View with a clean image viewer.
All UI is GPU-drawn to completely replace Blender's look.
"""

import bpy
from bpy.types import Header, Operator
import gpu
from gpu_extras.batch import batch_for_shader
import blf


_viewer_draw_handler = None
_viewer_header_handler = None
_viewer_tool_header_handler = None


def _draw_background(width, height, color):
    """Draw solid background."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    verts = [(0, 0), (width, 0), (width, height), (0, height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_viewer_header():
    """Draw custom GPU header for viewer."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Find header region
    region = None
    for r in context.area.regions:
        if r.type == 'HEADER':
            region = r
            break

    if region is None or region.height < 5:
        return

    gpu.state.blend_set('ALPHA')

    # Draw dark header background
    _draw_background(region.width, region.height, (0.20, 0.20, 0.20, 1.0))

    # Draw header content
    x = 10
    y = (region.height - 12) // 2 + 2

    # Viewer label
    blf.size(0, 13)
    blf.color(0, 0.9, 0.55, 0.2, 1.0)  # Orange
    blf.position(0, x, y, 0)
    blf.draw(0, "Viewer")
    x += 70

    # Separator
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    sep_verts = [(x, 5), (x, region.height - 5)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 15

    # Channel buttons
    blf.size(0, 11)
    channels = ["RGB", "R", "G", "B", "A"]
    for i, ch in enumerate(channels):
        # Active channel highlight
        if ch == "RGB":
            box_x = x - 5
            box_verts = [
                (box_x, 4), (box_x + 30, 4),
                (box_x + 30, region.height - 4), (box_x, region.height - 4)
            ]
            batch = batch_for_shader(shader, 'TRIS', {"pos": box_verts}, indices=[(0, 1, 2), (0, 2, 3)])
            shader.bind()
            shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
            batch.draw(shader)
            blf.color(0, 0.9, 0.9, 0.9, 1.0)
        else:
            blf.color(0, 0.6, 0.6, 0.6, 1.0)

        blf.position(0, x, y, 0)
        blf.draw(0, ch)
        x += 35

    # Separator
    x += 5
    sep_verts = [(x, 5), (x, region.height - 5)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 15

    # Zoom level
    blf.color(0, 0.7, 0.7, 0.7, 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, "100%")
    x += 50

    # Frame info on the right
    scene = context.scene
    frame_text = f"Frame {scene.frame_current}"
    text_width, _ = blf.dimensions(0, frame_text)
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    blf.position(0, region.width - text_width - 15, y, 0)
    blf.draw(0, frame_text)

    gpu.state.blend_set('NONE')


def _draw_viewer_tool_header():
    """Draw custom tool header (hide it)."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Find tool header region
    region = None
    for r in context.area.regions:
        if r.type == 'TOOL_HEADER':
            region = r
            break

    if region is None or region.height < 5:
        return

    gpu.state.blend_set('ALPHA')
    # Just draw background to hide any Blender content
    _draw_background(region.width, region.height, (0.18, 0.18, 0.18, 1.0))
    gpu.state.blend_set('NONE')


def _draw_viewer_overlay():
    """Draw Nuke-style viewer overlay."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    region = context.region
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')

    # Draw dark background
    _draw_background(region.width, region.height, (0.12, 0.12, 0.12, 1.0))

    # Draw center crosshair
    cx, cy = region.width / 2, region.height / 2
    cross_size = 20
    cross_vertices = [
        (cx - cross_size, cy), (cx + cross_size, cy),
        (cx, cy - cross_size), (cx, cy + cross_size),
    ]
    batch = batch_for_shader(shader, 'LINES', {"pos": cross_vertices})
    shader.bind()
    shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
    batch.draw(shader)

    # Draw frame border indicator
    border_color = (0.5, 0.3, 0.1, 1.0)  # Orange tint
    margin = 50
    border_verts = [
        (margin, margin), (region.width - margin, margin),
        (region.width - margin, region.height - margin),
        (margin, region.height - margin),
        (margin, margin)
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
    shader.bind()
    shader.uniform_float("color", border_color)
    batch.draw(shader)

    # Draw "No Image" text if nothing connected
    blf.size(0, 24)
    blf.color(0, 0.4, 0.4, 0.4, 1.0)
    text = "Connect Viewer Node"
    text_width, text_height = blf.dimensions(0, text)
    blf.position(0, cx - text_width / 2, cy - text_height / 2, 0)
    blf.draw(0, text)

    gpu.state.blend_set('NONE')


def _hide_default_view3d_ui():
    """Hide default Blender 3D View overlays and gizmos."""
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            # Hide overlays
            space.overlay.show_overlays = False
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_axis_z = False
            space.overlay.show_cursor = False
            space.overlay.show_object_origins = False
            # Hide gizmos
            space.show_gizmo = False
            # Set shading
            space.shading.type = 'SOLID'
            space.shading.background_type = 'VIEWPORT'
            space.shading.background_color = (0.12, 0.12, 0.12)
    return None  # Don't repeat timer


class OC_HT_viewer_header(Header):
    """Empty header - we draw our own via GPU."""
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        # Empty - GPU handler draws our header
        pass


class OC_OT_viewer_channel(Operator):
    """Set viewer channel display"""
    bl_idname = "oc.viewer_channel"
    bl_label = "Set Channel"

    channel: bpy.props.StringProperty(default='RGB')

    def execute(self, context):
        self.report({'INFO'}, f"Channel: {self.channel}")
        return {'FINISHED'}


class OC_OT_viewer_zoom(Operator):
    """Zoom viewer in/out"""
    bl_idname = "oc.viewer_zoom"
    bl_label = "Zoom"

    zoom_in: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        return {'FINISHED'}


class OC_OT_viewer_fit(Operator):
    """Fit image in viewer"""
    bl_idname = "oc.viewer_fit"
    bl_label = "Fit"

    def execute(self, context):
        return {'FINISHED'}


classes = [
    OC_HT_viewer_header,
    OC_OT_viewer_channel,
    OC_OT_viewer_zoom,
    OC_OT_viewer_fit,
]


def register():
    global _viewer_draw_handler, _viewer_header_handler, _viewer_tool_header_handler

    for cls in classes:
        bpy.utils.register_class(cls)

    # Register draw handlers for all regions
    _viewer_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_overlay, (), 'WINDOW', 'POST_PIXEL'
    )

    _viewer_header_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_header, (), 'HEADER', 'POST_PIXEL'
    )

    _viewer_tool_header_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_tool_header, (), 'TOOL_HEADER', 'POST_PIXEL'
    )

    # Hide default UI after a delay
    bpy.app.timers.register(_hide_default_view3d_ui, first_interval=0.2)

    # Unregister default headers
    try:
        bpy.utils.unregister_class(bpy.types.VIEW3D_HT_header)
    except:
        pass
    try:
        bpy.utils.unregister_class(bpy.types.VIEW3D_HT_tool_header)
    except:
        pass


def unregister():
    global _viewer_draw_handler, _viewer_header_handler, _viewer_tool_header_handler

    if _viewer_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_draw_handler, 'WINDOW')
        _viewer_draw_handler = None

    if _viewer_header_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_header_handler, 'HEADER')
        _viewer_header_handler = None

    if _viewer_tool_header_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_tool_header_handler, 'TOOL_HEADER')
        _viewer_tool_header_handler = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
