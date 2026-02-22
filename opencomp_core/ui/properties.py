"""OpenComp Properties Panel — Nuke-style properties.

Completely replaces Blender's Properties editor with custom GPU-drawn UI.
"""

import bpy
from bpy.types import Header
import gpu
from gpu_extras.batch import batch_for_shader
import blf


_props_draw_handler = None
_props_nav_handler = None
_props_header_handler = None


def _draw_background(region, color):
    """Draw solid background covering entire region."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    verts = [(0, 0), (region.width, 0), (region.width, region.height), (0, region.height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_properties_nav():
    """Draw custom navigation bar (replaces context tabs)."""
    context = bpy.context
    if context.area is None or context.area.type != 'PROPERTIES':
        return

    # Find the NAVIGATION_BAR region
    region = None
    for r in context.area.regions:
        if r.type == 'NAVIGATION_BAR':
            region = r
            break

    if region is None:
        return

    # Draw dark background
    _draw_background(region, (0.15, 0.15, 0.15, 1.0))

    # Draw navigation items
    y = region.height - 30
    x = 5

    blf.size(0, 11)

    nav_items = [
        ("Scene", True),
        ("Node", False),
        ("Output", False),
    ]

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    for label, active in nav_items:
        # Draw highlight for active item
        if active:
            highlight_verts = [
                (0, y - 5), (region.width, y - 5),
                (region.width, y + 15), (0, y + 15)
            ]
            indices = [(0, 1, 2), (0, 2, 3)]
            batch = batch_for_shader(shader, 'TRIS', {"pos": highlight_verts}, indices=indices)
            shader.bind()
            shader.uniform_float("color", (0.9, 0.55, 0.2, 0.3))
            batch.draw(shader)
            blf.color(0, 0.9, 0.55, 0.2, 1.0)
        else:
            blf.color(0, 0.6, 0.6, 0.6, 1.0)

        blf.position(0, x, y, 0)
        blf.draw(0, label)
        y -= 25

    gpu.state.blend_set('NONE')


def _draw_properties_header():
    """Draw custom header for properties editor."""
    context = bpy.context
    if context.area is None or context.area.type != 'PROPERTIES':
        return

    # Find the HEADER region
    region = None
    for r in context.area.regions:
        if r.type == 'HEADER':
            region = r
            break

    if region is None:
        return

    # Draw dark header background
    _draw_background(region, (0.22, 0.22, 0.22, 1.0))

    # Draw header text
    blf.size(0, 13)
    blf.color(0, 0.8, 0.8, 0.8, 1.0)
    blf.position(0, 10, (region.height - 13) // 2 + 2, 0)
    blf.draw(0, "Properties")

    gpu.state.blend_set('NONE')


def _draw_properties_ui():
    """Draw complete custom properties UI."""
    context = bpy.context
    if context.area is None or context.area.type != 'PROPERTIES':
        return

    region = context.region
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')

    # Draw dark background to cover everything
    bg_verts = [(0, 0), (region.width, 0), (region.width, region.height), (0, region.height)]
    bg_indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": bg_verts}, indices=bg_indices)
    shader.bind()
    shader.uniform_float("color", (0.18, 0.18, 0.18, 1.0))
    batch.draw(shader)

    # Get active node info from canvas state
    active_node = None
    node_info = None
    try:
        from ..node_canvas.state import get_canvas_state
        state = get_canvas_state()
        if state.active_node and state.active_node in state.node_visuals:
            active_node = state.active_node
            node_info = state.node_visuals[active_node]
    except:
        pass

    # Content area
    y = region.height - 20
    x_margin = 10

    if node_info:
        # Node name header
        blf.size(0, 16)
        blf.color(0, 0.9, 0.55, 0.2, 1.0)  # Orange
        blf.position(0, x_margin, y, 0)
        blf.draw(0, node_info.node_name)
        y -= 30

        # Draw separator
        sep_verts = [(x_margin, y + 10), (region.width - x_margin, y + 10)]
        batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
        shader.bind()
        shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
        batch.draw(shader)

        # Position section
        blf.size(0, 12)
        blf.color(0, 0.6, 0.6, 0.6, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Transform")
        y -= 25

        # X position
        blf.color(0, 0.8, 0.8, 0.8, 1.0)
        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"x:  {node_info.x:.1f}")
        y -= 20

        # Y position
        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"y:  {node_info.y:.1f}")
        y -= 30

        # Size section
        blf.color(0, 0.6, 0.6, 0.6, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Size")
        y -= 25

        blf.color(0, 0.8, 0.8, 0.8, 1.0)
        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"width:  {node_info.width:.1f}")
        y -= 20

        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"height: {node_info.height:.1f}")
        y -= 30

        # Ports section
        blf.color(0, 0.6, 0.6, 0.6, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Connections")
        y -= 25

        blf.color(0, 0.8, 0.8, 0.8, 1.0)
        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"inputs:  {len(node_info.input_ports)}")
        y -= 20

        blf.position(0, x_margin + 10, y, 0)
        blf.draw(0, f"outputs: {len(node_info.output_ports)}")

    else:
        # No node selected
        blf.size(0, 14)
        blf.color(0, 0.5, 0.5, 0.5, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "No node selected")
        y -= 30

        blf.size(0, 11)
        blf.color(0, 0.4, 0.4, 0.4, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Select a node in the Node Graph")
        blf.position(0, x_margin, y - 15, 0)
        blf.draw(0, "to see its properties here.")

    # Draw project info at bottom
    scene = context.scene
    y = 100
    blf.size(0, 12)
    blf.color(0, 0.6, 0.6, 0.6, 1.0)
    blf.position(0, x_margin, y, 0)
    blf.draw(0, "Project")
    y -= 25

    blf.size(0, 11)
    blf.color(0, 0.7, 0.7, 0.7, 1.0)
    blf.position(0, x_margin + 10, y, 0)
    blf.draw(0, f"Resolution: {scene.render.resolution_x} x {scene.render.resolution_y}")
    y -= 18
    blf.position(0, x_margin + 10, y, 0)
    blf.draw(0, f"Frames: {scene.frame_start} - {scene.frame_end}")
    y -= 18
    blf.position(0, x_margin + 10, y, 0)
    blf.draw(0, f"FPS: {scene.render.fps}")

    gpu.state.blend_set('NONE')


class OC_HT_properties_header(Header):
    """Empty header - we draw our own."""
    bl_space_type = 'PROPERTIES'

    def draw(self, context):
        # Empty - we draw custom header via GPU
        pass


def register():
    global _props_draw_handler, _props_nav_handler, _props_header_handler

    bpy.utils.register_class(OC_HT_properties_header)

    # Register draw handlers for all regions
    _props_draw_handler = bpy.types.SpaceProperties.draw_handler_add(
        _draw_properties_ui, (), 'WINDOW', 'POST_PIXEL'
    )

    _props_nav_handler = bpy.types.SpaceProperties.draw_handler_add(
        _draw_properties_nav, (), 'NAVIGATION_BAR', 'POST_PIXEL'
    )

    _props_header_handler = bpy.types.SpaceProperties.draw_handler_add(
        _draw_properties_header, (), 'HEADER', 'POST_PIXEL'
    )


def unregister():
    global _props_draw_handler, _props_nav_handler, _props_header_handler

    if _props_draw_handler:
        bpy.types.SpaceProperties.draw_handler_remove(_props_draw_handler, 'WINDOW')
        _props_draw_handler = None

    if _props_nav_handler:
        bpy.types.SpaceProperties.draw_handler_remove(_props_nav_handler, 'NAVIGATION_BAR')
        _props_nav_handler = None

    if _props_header_handler:
        bpy.types.SpaceProperties.draw_handler_remove(_props_header_handler, 'HEADER')
        _props_header_handler = None

    try:
        bpy.utils.unregister_class(OC_HT_properties_header)
    except:
        pass
