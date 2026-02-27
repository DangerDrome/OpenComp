"""GPU-drawn custom headers for OpenComp areas.

Provides Nuke-style headers for Node Editor and Properties panels.
All headers are GPU-drawn to avoid Blender's native look.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from .. import console

# Header styling
HEADER_BG_COLOR = (0.16, 0.16, 0.16, 1.0)
HEADER_TEXT_COLOR = (0.75, 0.75, 0.75, 1.0)
HEADER_ACCENT_COLOR = (0.5, 0.5, 0.5, 1.0)

_node_header_handler = None
_properties_header_handler = None
_shader_cache = {}


def _get_shader():
    """Get or create the 2D uniform color shader."""
    global _shader_cache
    if "2D_UNIFORM_COLOR" not in _shader_cache:
        _shader_cache["2D_UNIFORM_COLOR"] = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader_cache["2D_UNIFORM_COLOR"]


def _draw_rect(x, y, w, h, color):
    """Draw a filled rectangle."""
    shader = _get_shader()
    vertices = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_text(text, x, y, size=11, color=(0.75, 0.75, 0.75, 1.0)):
    """Draw text using Blender's built-in font."""
    import blf
    font_id = 0
    blf.size(font_id, size)
    blf.color(font_id, *color)
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def _draw_node_header():
    """Draw custom header for Node Editor."""
    context = bpy.context

    if context.area is None or context.area.type != 'NODE_EDITOR':
        return

    region = context.region
    if region.type != 'HEADER':
        return

    # Check if this is an OpenComp tree
    snode = context.space_data
    if snode.tree_type != "OC_NT_compositor":
        return

    rw = region.width
    rh = region.height

    gpu.state.blend_set('ALPHA')

    # Draw header background - cover everything
    _draw_rect(0, 0, rw, rh, HEADER_BG_COLOR)

    # Draw "Node Graph" label
    _draw_text("Node Graph", 12, rh // 2 - 4, size=12, color=HEADER_TEXT_COLOR)

    # Draw tree name if available
    if snode.node_tree:
        tree_name = snode.node_tree.name
        _draw_text(f"[ {tree_name} ]", 110, rh // 2 - 4, size=11, color=HEADER_ACCENT_COLOR)

    # Draw frame number on right
    frame_text = f"Frame {context.scene.frame_current}"
    _draw_text(frame_text, rw - 90, rh // 2 - 4, size=11, color=HEADER_ACCENT_COLOR)

    gpu.state.blend_set('NONE')


def _draw_properties_header():
    """Draw custom header for Properties panel."""
    context = bpy.context

    if context.area is None or context.area.type != 'PROPERTIES':
        return

    region = context.region
    if region.type != 'HEADER':
        return

    rw = region.width
    rh = region.height

    gpu.state.blend_set('ALPHA')

    # Draw header background - cover everything
    _draw_rect(0, 0, rw, rh, HEADER_BG_COLOR)

    # Draw "Properties" label
    _draw_text("Properties", 12, rh // 2 - 4, size=12, color=HEADER_TEXT_COLOR)

    # Show active node name if available
    node = None
    for tree in bpy.data.node_groups:
        if tree.bl_idname == "OC_NT_compositor" and tree.nodes.active:
            node = tree.nodes.active
            break

    if node:
        _draw_text(f"[ {node.name} ]", 110, rh // 2 - 4, size=11, color=HEADER_ACCENT_COLOR)

    gpu.state.blend_set('NONE')


def register():
    global _node_header_handler, _properties_header_handler

    # Hide default headers first
    try:
        bpy.utils.unregister_class(bpy.types.NODE_HT_header)
        console.debug("Hid NODE_HT_header", "UI")
    except Exception:
        pass

    # Register GPU draw handlers for headers
    _node_header_handler = bpy.types.SpaceNodeEditor.draw_handler_add(
        _draw_node_header, (), 'HEADER', 'POST_PIXEL'
    )
    console.registered("Node Editor GPU header")

    _properties_header_handler = bpy.types.SpaceProperties.draw_handler_add(
        _draw_properties_header, (), 'HEADER', 'POST_PIXEL'
    )
    console.registered("Properties GPU header")


def unregister():
    global _node_header_handler, _properties_header_handler

    if _node_header_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_node_header_handler, 'HEADER')
        _node_header_handler = None

    if _properties_header_handler is not None:
        bpy.types.SpaceProperties.draw_handler_remove(_properties_header_handler, 'HEADER')
        _properties_header_handler = None

    # Restore default headers
    try:
        bpy.utils.register_class(bpy.types.NODE_HT_header)
    except Exception:
        pass
