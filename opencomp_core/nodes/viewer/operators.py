"""OpenComp Viewer operators — zoom, pan, ROI, route, reset, channel, fit.

All operators modify viewer state or the display pass only.
They never re-evaluate the node graph.
"""

import bpy


# ── Zoom ────────────────────────────────────────────────────────────────

class OC_OT_viewer_zoom_in(bpy.types.Operator):
    """Zoom the viewer in, centered on cursor position"""
    bl_idname = "oc.viewer_zoom_in"
    bl_label = "Viewer Zoom In"

    def invoke(self, context, event):
        from .viewer import _viewer_state
        old_zoom = _viewer_state["zoom"]
        new_zoom = min(old_zoom * 1.2, 20.0)
        _zoom_toward_cursor(context, event, _viewer_state, old_zoom, new_zoom)
        _viewer_state["zoom"] = new_zoom
        _tag_redraw(context)
        return {'FINISHED'}

    def execute(self, context):
        from .viewer import _viewer_state
        _viewer_state["zoom"] = min(_viewer_state["zoom"] * 1.2, 20.0)
        _tag_redraw(context)
        return {'FINISHED'}


class OC_OT_viewer_zoom_out(bpy.types.Operator):
    """Zoom the viewer out, centered on cursor position"""
    bl_idname = "oc.viewer_zoom_out"
    bl_label = "Viewer Zoom Out"

    def invoke(self, context, event):
        from .viewer import _viewer_state
        old_zoom = _viewer_state["zoom"]
        new_zoom = max(old_zoom / 1.2, 0.1)
        _zoom_toward_cursor(context, event, _viewer_state, old_zoom, new_zoom)
        _viewer_state["zoom"] = new_zoom
        _tag_redraw(context)
        return {'FINISHED'}

    def execute(self, context):
        from .viewer import _viewer_state
        _viewer_state["zoom"] = max(_viewer_state["zoom"] / 1.2, 0.1)
        _tag_redraw(context)
        return {'FINISHED'}


def _zoom_toward_cursor(context, event, state, old_zoom, new_zoom):
    """Adjust pan so the image point under the cursor stays fixed after zoom."""
    area = context.area
    tex = state.get("texture")
    if area is None or tex is None:
        return

    # Cursor position in viewport UV space (0..1)
    # Shader flips Y (1.0 - v_uv.y), so invert cursor Y to match
    cursor_vp_x = (event.mouse_x - area.x) / area.width
    cursor_vp_y = 1.0 - (event.mouse_y - area.y) / area.height

    # Aspect ratio scale (mirrors the shader math)
    img_aspect = tex.width / max(tex.height, 1)
    vp_aspect = area.width / max(area.height, 1)
    if vp_aspect > img_aspect:
        scale_x = img_aspect / vp_aspect
        scale_y = 1.0
    else:
        scale_x = 1.0
        scale_y = vp_aspect / img_aspect

    # Pan adjustment: keep image point under cursor fixed
    # From shader: uv = (vp_uv - 0.5) / (scale * zoom) + 0.5 - pan
    # Solving for pan change when zoom changes:
    dz = 1.0 / new_zoom - 1.0 / old_zoom
    state["pan"][0] += (cursor_vp_x - 0.5) / scale_x * dz
    state["pan"][1] += (cursor_vp_y - 0.5) / scale_y * dz


# ── Pan (MMB drag) ─────────────────────────────────────────────────────

class OC_OT_viewer_pan(bpy.types.Operator):
    """Pan the viewer with middle mouse drag"""
    bl_idname = "oc.viewer_pan"
    bl_label = "Viewer Pan"

    _prev_x: int = 0
    _prev_y: int = 0

    def invoke(self, context, event):
        self._prev_x = event.mouse_x
        self._prev_y = event.mouse_y
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        from .viewer import _viewer_state

        if event.type == 'MOUSEMOVE':
            area = context.area
            if area is None:
                return {'CANCELLED'}
            dx = (event.mouse_x - self._prev_x) / area.width
            dy = (event.mouse_y - self._prev_y) / area.height

            # To make the image stick 1:1 to the cursor we must
            # invert the full shader transform:
            #   uv = (vp_uv - 0.5) / (scale * zoom) + 0.5 - pan
            # delta_pan = d_vp / (scale * zoom)
            zoom = _viewer_state.get("zoom", 1.0)
            tex = _viewer_state.get("texture")
            if tex is not None and area.height > 0:
                img_aspect = tex.width / max(tex.height, 1)
                vp_aspect = area.width / max(area.height, 1)
                if vp_aspect > img_aspect:
                    sx, sy = img_aspect / vp_aspect, 1.0
                else:
                    sx, sy = 1.0, vp_aspect / img_aspect
            else:
                sx, sy = 1.0, 1.0

            _viewer_state["pan"][0] += dx / (sx * zoom)
            _viewer_state["pan"][1] -= dy / (sy * zoom)
            self._prev_x = event.mouse_x
            self._prev_y = event.mouse_y
            _tag_redraw(context)
            return {'RUNNING_MODAL'}

        if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            return {'CANCELLED'}

        return {'PASS_THROUGH'}


# ── ROI (Ctrl+LMB drag) ────────────────────────────────────────────────

class OC_OT_viewer_roi(bpy.types.Operator):
    """Drag to define a region of interest"""
    bl_idname = "oc.viewer_roi"
    bl_label = "Viewer ROI"

    _start_x: float = 0.0
    _start_y: float = 0.0

    def invoke(self, context, event):
        from .viewer import _viewer_state

        # Toggle off if already enabled
        if _viewer_state.get("roi_enabled", False):
            _viewer_state["roi_enabled"] = False
            _tag_redraw(context)
            return {'FINISHED'}

        area = context.area
        if area is None:
            return {'CANCELLED'}

        self._start_x = (event.mouse_x - area.x) / area.width
        self._start_y = (event.mouse_y - area.y) / area.height
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        from .viewer import _viewer_state
        area = context.area
        if area is None:
            return {'CANCELLED'}

        if event.type == 'MOUSEMOVE':
            x2 = (event.mouse_x - area.x) / area.width
            y2 = (event.mouse_y - area.y) / area.height
            _viewer_state["roi"] = [
                min(self._start_x, x2), min(self._start_y, y2),
                max(self._start_x, x2), max(self._start_y, y2),
            ]
            _viewer_state["roi_enabled"] = True
            _tag_redraw(context)
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            _viewer_state["roi_enabled"] = False
            _tag_redraw(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}


# ── Route to Viewer (Ctrl+1..5) ────────────────────────────────────────

class OC_OT_viewer_route(bpy.types.Operator):
    """Route the selected node to the viewer"""
    bl_idname = "oc.viewer_route"
    bl_label = "Route to Viewer"

    index: bpy.props.IntProperty(name="Viewer Index", default=1, min=1, max=5)

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            hasattr(space, 'node_tree')
            and space.node_tree is not None
            and space.node_tree.bl_idname == "OC_NT_compositor"
        )

    def execute(self, context):
        tree = context.space_data.node_tree

        # Get selected node
        selected = [n for n in tree.nodes if n.select]
        if not selected:
            self.report({'WARNING'}, "No node selected")
            return {'CANCELLED'}

        source_node = selected[0]
        if not source_node.outputs:
            self.report({'WARNING'}, "Selected node has no outputs")
            return {'CANCELLED'}

        # Collect all viewer nodes sorted by name for index mapping
        viewers = sorted(
            [n for n in tree.nodes if n.bl_idname == "OC_N_viewer"],
            key=lambda n: n.name,
        )

        # Pick the viewer matching the requested index (1-based)
        viewer_node = None
        idx = self.index - 1  # convert to 0-based
        if 0 <= idx < len(viewers):
            viewer_node = viewers[idx]
        elif viewers:
            viewer_node = viewers[0]

        if viewer_node is None:
            viewer_node = tree.nodes.new("OC_N_viewer")
            viewer_node.location = (source_node.location.x + 300,
                                    source_node.location.y)

        # Remove existing links to viewer input
        for link in list(tree.links):
            if link.to_socket == viewer_node.inputs[0]:
                tree.links.remove(link)

        # Connect source output → viewer input
        tree.links.new(source_node.outputs[0], viewer_node.inputs[0])

        # Set this viewer as the active viewer for viewport display
        from .viewer import _viewer_state
        _viewer_state["active_viewer"] = viewer_node.name

        return {'FINISHED'}


# ── Reset View ──────────────────────────────────────────────────────────

class OC_OT_viewer_reset(bpy.types.Operator):
    """Reset viewer zoom, pan, and ROI"""
    bl_idname = "oc.viewer_reset"
    bl_label = "Reset View"

    def execute(self, context):
        from .viewer import _viewer_state
        _viewer_state["zoom"] = 1.0
        _viewer_state["pan"] = [0.0, 0.0]
        _viewer_state["roi_enabled"] = False
        _tag_redraw(context)
        return {'FINISHED'}


# ── Channel Toggle ──────────────────────────────────────────────────────

class OC_OT_viewer_set_channel(bpy.types.Operator):
    """Toggle a channel isolation mode (press same key to return to All)"""
    bl_idname = "oc.viewer_set_channel"
    bl_label = "Set Viewer Channel"

    channel: bpy.props.EnumProperty(
        name="Channel",
        items=[
            ('ALL',  "All",  "Show all channels",     0),
            ('R',    "R",    "Red channel only",       1),
            ('G',    "G",    "Green channel only",     2),
            ('B',    "B",    "Blue channel only",      3),
            ('A',    "A",    "Alpha channel only",     4),
            ('LUMA', "Luma", "Rec.709 luminance only", 5),
        ],
        default='ALL',
    )

    def execute(self, context):
        try:
            settings = context.scene.oc_viewer
        except AttributeError:
            return {'CANCELLED'}

        # Toggle: if already on this channel, switch back to ALL
        if settings.channel_mode == self.channel:
            settings.channel_mode = 'ALL'
        else:
            settings.channel_mode = self.channel

        _tag_redraw(context)
        return {'FINISHED'}


# ── Fit to Window ────────────────────────────────────────────────────────

class OC_OT_viewer_fit(bpy.types.Operator):
    """Fit the image to the viewport (reset zoom and pan)"""
    bl_idname = "oc.viewer_fit"
    bl_label = "Fit to Window"

    def execute(self, context):
        from .viewer import _viewer_state
        _viewer_state["zoom"] = 1.0
        _viewer_state["pan"] = [0.0, 0.0]
        _tag_redraw(context)
        return {'FINISHED'}


# ── Helpers ─────────────────────────────────────────────────────────────

def _tag_redraw(context):
    """Request a viewport redraw for all 3D views."""
    try:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    except Exception:
        pass


# ── Registration ────────────────────────────────────────────────────────

_classes = [
    OC_OT_viewer_zoom_in,
    OC_OT_viewer_zoom_out,
    OC_OT_viewer_pan,
    OC_OT_viewer_roi,
    OC_OT_viewer_route,
    OC_OT_viewer_reset,
    OC_OT_viewer_set_channel,
    OC_OT_viewer_fit,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
