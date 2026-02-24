"""OpenComp Properties Panel — custom GPU-drawn properties for active node.

Replaces Blender's Properties editor content with OpenComp node properties.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import blf
from bpy.app.handlers import persistent


_props_draw_handler = None
_last_active_node_name = None


def _get_active_node():
    """Get the active node from the OpenComp tree.

    Checks both bpy.data.node_groups and the active node editor space.
    """
    # First try: check all node groups for an active node
    for tree in bpy.data.node_groups:
        if tree.bl_idname == "OC_NT_compositor":
            if tree.nodes.active:
                return tree.nodes.active

    # Second try: check the node editor space directly
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR' and space.tree_type == "OC_NT_compositor":
                            tree = space.edit_tree
                            if tree and tree.nodes.active:
                                return tree.nodes.active
    except Exception:
        pass

    return None


@persistent
def _on_depsgraph_update(scene):
    """Tag Properties area for redraw when active node changes."""
    global _last_active_node_name

    node = _get_active_node()
    current_name = node.name if node else None

    # Only redraw if the active node actually changed
    if current_name != _last_active_node_name:
        _last_active_node_name = current_name

        # Tag all Properties areas for redraw
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'PROPERTIES':
                        area.tag_redraw()
        except Exception:
            pass


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


def _draw_properties_ui():
    """Let native Blender Properties panels show through for interactive controls."""
    # Don't draw GPU overlay - let Blender's native panels with interactive
    # widgets (file browsers, color pickers, etc.) show instead
    return

    # Legacy GPU drawing code below (kept for reference)
    context = bpy.context
    if context.area is None or context.area.type != 'PROPERTIES':
        return

    region = context.region
    if region is None or region.type != 'WINDOW':
        return

    # Dark background
    bg_color = (0.18, 0.18, 0.18, 1.0)
    _draw_background(region, bg_color)

    # Get active node from Blender's node tree
    node = _get_active_node()

    # Content area
    y = region.height - 30
    x_margin = 15

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    if node:
        # Node name header
        blf.size(0, 16)
        blf.color(0, 0.3, 0.8, 0.45, 1.0)  # Green
        blf.position(0, x_margin, y, 0)
        blf.draw(0, node.bl_label)
        y -= 25

        # Node internal name (dimmed)
        blf.size(0, 11)
        blf.color(0, 0.5, 0.5, 0.5, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, node.name)
        y -= 30

        # Draw separator
        gpu.state.blend_set('ALPHA')
        sep_verts = [(x_margin, y + 10), (region.width - x_margin, y + 10)]
        batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
        shader.bind()
        shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
        batch.draw(shader)
        y -= 10

        # Properties section header
        blf.size(0, 12)
        blf.color(0, 0.6, 0.6, 0.6, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Properties")
        y -= 25

        # Draw node-specific properties
        blf.size(0, 11)
        blf.color(0, 0.8, 0.8, 0.8, 1.0)

        # Show common properties based on node type
        if hasattr(node, 'filepath'):
            blf.position(0, x_margin + 10, y, 0)
            filepath = node.filepath if node.filepath else "(no file)"
            # Truncate long paths
            if len(filepath) > 35:
                filepath = "..." + filepath[-32:]
            blf.draw(0, f"File: {filepath}")
            y -= 20

        if hasattr(node, 'color') and node.bl_idname == 'OC_N_constant':
            blf.position(0, x_margin + 10, y, 0)
            c = node.color
            blf.draw(0, f"Color: ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
            y -= 20

        # Show inputs/outputs
        y -= 10
        blf.color(0, 0.6, 0.6, 0.6, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Connections")
        y -= 20

        blf.color(0, 0.7, 0.7, 0.7, 1.0)
        for inp in node.inputs:
            status = "connected" if inp.is_linked else "empty"
            blf.position(0, x_margin + 10, y, 0)
            blf.draw(0, f"← {inp.name}: {status}")
            y -= 18

        for out in node.outputs:
            status = "connected" if out.is_linked else "empty"
            blf.position(0, x_margin + 10, y, 0)
            blf.draw(0, f"→ {out.name}: {status}")
            y -= 18

        # Hint
        y -= 20
        blf.size(0, 10)
        blf.color(0, 0.4, 0.4, 0.4, 1.0)
        blf.position(0, x_margin, y, 0)
        blf.draw(0, "Press N in Node Editor for full controls")

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
    y = 80
    blf.size(0, 12)
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    blf.position(0, x_margin, y, 0)
    blf.draw(0, "Project")
    y -= 20

    blf.size(0, 10)
    blf.color(0, 0.6, 0.6, 0.6, 1.0)
    blf.position(0, x_margin + 10, y, 0)
    blf.draw(0, f"{scene.render.resolution_x}x{scene.render.resolution_y}")
    y -= 15
    blf.position(0, x_margin + 10, y, 0)
    blf.draw(0, f"{scene.frame_start}-{scene.frame_end} @ {scene.render.fps}fps")

    gpu.state.blend_set('NONE')


def register():
    global _props_draw_handler

    # Register GPU draw handler for Properties window
    _props_draw_handler = bpy.types.SpaceProperties.draw_handler_add(
        _draw_properties_ui, (), 'WINDOW', 'POST_PIXEL'
    )

    # Register handler to track active node changes
    if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)


def unregister():
    global _props_draw_handler

    # Remove depsgraph handler
    if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)

    if _props_draw_handler:
        bpy.types.SpaceProperties.draw_handler_remove(_props_draw_handler, 'WINDOW')
        _props_draw_handler = None
