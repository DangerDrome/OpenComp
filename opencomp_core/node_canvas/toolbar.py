"""GPU-rendered left toolbar for OpenComp.

Draws a Nuke-style vertical toolbar with tool icons.
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from .. import console

# Toolbar configuration
TOOLBAR_BG_COLOR = (0.16, 0.16, 0.16, 1.0)  # Dark gray
BUTTON_SIZE = 32
BUTTON_PADDING = 8
BUTTON_HOVER_COLOR = (0.25, 0.25, 0.25, 1.0)
BUTTON_ACTIVE_COLOR = (0.35, 0.35, 0.35, 1.0)
ICON_COLOR = (0.7, 0.7, 0.7, 1.0)
ICON_HOVER_COLOR = (1.0, 1.0, 1.0, 1.0)

# Toolbar buttons definition
TOOLBAR_BUTTONS = [
    {"id": "select", "icon": "cursor", "tooltip": "Select Tool", "operator": None},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "read", "icon": "image", "tooltip": "Read Node", "operator": "node.add_node", "props": {"type": "OC_N_read"}},
    {"id": "constant", "icon": "constant", "tooltip": "Constant", "operator": "node.add_node", "props": {"type": "OC_N_constant"}},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "grade", "icon": "color", "tooltip": "Grade", "operator": "node.add_node", "props": {"type": "OC_N_grade"}},
    {"id": "cdl", "icon": "color", "tooltip": "CDL", "operator": "node.add_node", "props": {"type": "OC_N_cdl"}},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "merge", "icon": "layers", "tooltip": "Merge", "operator": "node.add_node", "props": {"type": "OC_N_merge"}},
    {"id": "over", "icon": "layers", "tooltip": "Over", "operator": "node.add_node", "props": {"type": "OC_N_over"}},
    {"id": "shuffle", "icon": "shuffle", "tooltip": "Shuffle", "operator": "node.add_node", "props": {"type": "OC_N_shuffle"}},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "blur", "icon": "blur", "tooltip": "Blur", "operator": "node.add_node", "props": {"type": "OC_N_blur"}},
    {"id": "sharpen", "icon": "sharpen", "tooltip": "Sharpen", "operator": "node.add_node", "props": {"type": "OC_N_sharpen"}},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "transform", "icon": "transform", "tooltip": "Transform", "operator": "node.add_node", "props": {"type": "OC_N_transform"}},
    {"id": "crop", "icon": "crop", "tooltip": "Crop", "operator": "node.add_node", "props": {"type": "OC_N_crop"}},
    {"id": "separator", "icon": None, "tooltip": None, "operator": None},
    {"id": "viewer", "icon": "view", "tooltip": "Viewer", "operator": "node.add_node", "props": {"type": "OC_N_viewer"}},
    {"id": "write", "icon": "export", "tooltip": "Write", "operator": "node.add_node", "props": {"type": "OC_N_write"}},
]

_shader_cache = {}
_draw_handler = None
_button_regions = []  # List of (x, y, w, h, button_def) for hit testing


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


def _draw_toolbar_icon(icon_name, cx, cy, size, color):
    """Draw an icon centered at (cx, cy)."""
    from . import icons

    half = size / 2
    x = cx - half
    y = cy - half

    # Use the icon drawing system
    icons.draw_icon(icon_name, x, y, size, color)


def _draw_toolbar(context, region_width, region_height):
    """Draw the toolbar background and buttons."""
    global _button_regions
    _button_regions = []

    # Draw background
    _draw_rect(0, 0, region_width, region_height, TOOLBAR_BG_COLOR)

    # Calculate button positions (top to bottom)
    x_center = region_width / 2
    y = region_height - BUTTON_PADDING - BUTTON_SIZE / 2

    # Mouse position is handled in modal operator, not draw callback

    for button in TOOLBAR_BUTTONS:
        if button["id"] == "separator":
            # Draw separator line
            sep_y = y + BUTTON_SIZE / 2
            _draw_rect(BUTTON_PADDING, sep_y, region_width - 2 * BUTTON_PADDING, 1,
                      (0.3, 0.3, 0.3, 1.0))
            y -= BUTTON_PADDING * 2
            continue

        # Button bounds
        bx = x_center - BUTTON_SIZE / 2
        by = y - BUTTON_SIZE / 2

        # Store for hit testing
        _button_regions.append((bx, by, BUTTON_SIZE, BUTTON_SIZE, button))

        # Draw button background (hover state would be handled by modal)
        # For now, just draw a subtle background
        _draw_rect(bx, by, BUTTON_SIZE, BUTTON_SIZE, (0.2, 0.2, 0.2, 0.5))

        # Draw icon
        if button["icon"]:
            _draw_toolbar_icon(button["icon"], x_center, y, BUTTON_SIZE * 0.7, ICON_COLOR)

        y -= BUTTON_SIZE + BUTTON_PADDING


def _draw_callback():
    """Draw callback for the toolbar area."""
    context = bpy.context

    # Only draw in IMAGE_EDITOR areas that are narrow (our toolbar)
    if context.area.type != 'IMAGE_EDITOR':
        return
    if context.area.width > 100:
        return

    region = context.region
    if region.type != 'WINDOW':
        return

    # Enable blending
    gpu.state.blend_set('ALPHA')

    _draw_toolbar(context, region.width, region.height)

    gpu.state.blend_set('NONE')


def get_button_at(x, y):
    """Get the button at the given coordinates, or None."""
    for bx, by, bw, bh, button in _button_regions:
        if bx <= x <= bx + bw and by <= y <= by + bh:
            return button
    return None


class OC_OT_toolbar_modal(bpy.types.Operator):
    """Modal operator for handling toolbar interactions."""
    bl_idname = "oc.toolbar_modal"
    bl_label = "OpenComp Toolbar"

    _is_running = False

    def modal(self, context, event):
        # Only handle events in our toolbar area
        if context.area is None or context.area.type != 'IMAGE_EDITOR':
            return {'PASS_THROUGH'}
        if context.area.width > 100:
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Get mouse position relative to region
            mx = event.mouse_region_x
            my = event.mouse_region_y

            button = get_button_at(mx, my)
            if button and button["operator"]:
                # Find the NODE_EDITOR area to execute node operations
                node_area = None
                for area in context.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        node_area = area
                        break

                if node_area:
                    # Execute the operator in NODE_EDITOR context
                    try:
                        with context.temp_override(area=node_area):
                            op_path = button["operator"].split(".")
                            op = getattr(getattr(bpy.ops, op_path[0]), op_path[1])
                            props = button.get("props", {})
                            op('INVOKE_DEFAULT', **props)
                            console.debug(f"Toolbar: executed {button['operator']}", "Canvas")
                    except Exception as e:
                        console.warning(f"Toolbar operator failed: {e}", "Canvas")

                return {'RUNNING_MODAL'}

        elif event.type == 'MOUSEMOVE':
            # Could update hover state here
            context.area.tag_redraw()
            return {'PASS_THROUGH'}

        elif event.type == 'ESC':
            OC_OT_toolbar_modal._is_running = False
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if OC_OT_toolbar_modal._is_running:
            return {'CANCELLED'}

        OC_OT_toolbar_modal._is_running = True
        context.window_manager.modal_handler_add(self)
        console.debug("Toolbar modal started", "Canvas")
        return {'RUNNING_MODAL'}


def register():
    """Register the toolbar draw handler and operator."""
    global _draw_handler

    bpy.utils.register_class(OC_OT_toolbar_modal)

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(
            _draw_callback, (), 'WINDOW', 'POST_PIXEL'
        )
        console.registered("Toolbar draw handler")

    # Start the toolbar modal
    def _start_toolbar():
        try:
            bpy.ops.oc.toolbar_modal('INVOKE_DEFAULT')
        except Exception as e:
            console.warning(f"Toolbar modal start failed: {e}", "Canvas")
        return None

    bpy.app.timers.register(_start_toolbar, first_interval=0.6)


def unregister():
    """Unregister the toolbar draw handler and operator."""
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
        console.unregistered("Toolbar draw handler")

    try:
        bpy.utils.unregister_class(OC_OT_toolbar_modal)
    except RuntimeError:
        pass
