"""OpenComp Node Canvas — Operators.

Complete UI takeover for the Node Editor area.
Uses a modal operator that captures all input when mouse is in the area.
"""

import bpy
from bpy.types import Operator

from .state import get_canvas_state, NodeVisual, LinkVisual
from .renderer import NodeCanvasRenderer


# Global state
_renderer = None
_draw_handler = None
_header_handler = None
_modal_handler = None
_links = []


def get_renderer() -> NodeCanvasRenderer:
    """Get or create the global renderer."""
    global _renderer
    if _renderer is None:
        _renderer = NodeCanvasRenderer()
    return _renderer


def _draw_callback():
    """Persistent draw callback for the node canvas."""
    context = bpy.context
    if context.area is None or context.area.type != 'NODE_EDITOR':
        return

    # Only draw in OpenComp node trees
    space = context.space_data
    if space.tree_type != 'OC_NT_compositor':
        return

    region = context.region
    state = get_canvas_state()
    renderer = get_renderer()

    renderer.draw(state, region.width, region.height, _links)


def _draw_header_callback():
    """Draw custom header for the Node Editor."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    import blf

    context = bpy.context
    if context.area is None or context.area.type != 'NODE_EDITOR':
        return

    # Only draw in OpenComp node trees
    space = context.space_data
    if space.tree_type != 'OC_NT_compositor':
        return

    # Find the header region
    region = None
    for r in context.area.regions:
        if r.type == 'HEADER':
            region = r
            break

    if region is None or region.height < 5:
        return

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    # Draw dark background
    verts = [(0, 0), (region.width, 0), (region.width, region.height), (0, region.height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", (0.20, 0.20, 0.20, 1.0))
    batch.draw(shader)

    x = 10
    y = (region.height - 12) // 2 + 2

    # Node Graph label
    blf.size(0, 13)
    blf.color(0, 0.9, 0.55, 0.2, 1.0)  # Orange
    blf.position(0, x, y, 0)
    blf.draw(0, "Node Graph")
    x += 95

    # Separator
    sep_verts = [(x, 5), (x, region.height - 5)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 15

    # Tree name
    blf.size(0, 11)
    blf.color(0, 0.7, 0.7, 0.7, 1.0)
    tree_name = "OpenComp"
    if space.node_tree:
        tree_name = space.node_tree.name
    blf.position(0, x, y, 0)
    blf.draw(0, tree_name)
    x += 100

    # Node count
    state = get_canvas_state()
    node_count = len(state.node_visuals)
    count_text = f"Nodes: {node_count}"
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, count_text)

    # Right side - shortcuts hint
    hint_text = "` Add Node | F Frame | A Select All"
    text_width, _ = blf.dimensions(0, hint_text)
    blf.color(0, 0.4, 0.4, 0.4, 1.0)
    blf.position(0, region.width - text_width - 15, y, 0)
    blf.draw(0, hint_text)

    gpu.state.blend_set('NONE')


def ensure_draw_handler():
    """Ensure the persistent draw handlers are registered."""
    global _draw_handler, _header_handler

    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceNodeEditor.draw_handler_add(
            _draw_callback, (), 'WINDOW', 'POST_PIXEL'
        )
        print("[OpenComp] Canvas draw handler registered")

    if _header_handler is None:
        _header_handler = bpy.types.SpaceNodeEditor.draw_handler_add(
            _draw_header_callback, (), 'HEADER', 'POST_PIXEL'
        )
        print("[OpenComp] Canvas header handler registered")


def remove_draw_handler():
    """Remove the persistent draw handlers."""
    global _draw_handler, _header_handler

    if _draw_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None

    if _header_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_header_handler, 'HEADER')
        _header_handler = None


def _add_demo_nodes(state):
    """Add demo nodes to test the canvas."""
    global _links

    state.node_visuals["Read1"] = NodeVisual(
        node_name="Read1",
        x=-70, y=100,
        width=140, height=80,
        color=(0.2, 0.4, 0.2)
    )
    state.node_visuals["Read1"].input_ports = []
    state.node_visuals["Read1"].output_ports = [(0, 0)]

    state.node_visuals["Grade1"] = NodeVisual(
        node_name="Grade1",
        x=-70, y=-50,
        width=140, height=80,
        color=(0.4, 0.3, 0.2)
    )
    state.node_visuals["Grade1"].input_ports = [(0, 0)]
    state.node_visuals["Grade1"].output_ports = [(0, 0)]

    state.node_visuals["Viewer"] = NodeVisual(
        node_name="Viewer",
        x=-70, y=-200,
        width=140, height=80,
        color=(0.3, 0.2, 0.4)
    )
    state.node_visuals["Viewer"].input_ports = [(0, 0)]
    state.node_visuals["Viewer"].output_ports = []

    _links = [
        LinkVisual("Read1", 0, "Grade1", 0),
        LinkVisual("Grade1", 0, "Viewer", 0),
    ]


class OC_OT_canvas_modal(Operator):
    """OpenComp Canvas - handles all input in Node Editor"""
    bl_idname = "oc.canvas_modal"
    bl_label = "OpenComp Canvas"
    bl_options = {'REGISTER'}

    _timer = None
    _is_panning = False
    _is_moving = False
    _is_box_selecting = False
    _last_x = 0
    _last_y = 0
    _start_x = 0
    _start_y = 0

    def _find_node_editor_area(self, context, mx, my):
        """Check if mouse is over a NODE_EDITOR area and return it."""
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                if (area.x <= mx <= area.x + area.width and
                    area.y <= my <= area.y + area.height):
                    return area
        return None

    def modal(self, context, event):
        # Always redraw on timer
        if event.type == 'TIMER':
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    area.tag_redraw()
            return {'PASS_THROUGH'}

        # Get absolute mouse position
        abs_x = event.mouse_x
        abs_y = event.mouse_y

        # Check if mouse is over a Node Editor
        node_area = self._find_node_editor_area(context, abs_x, abs_y)

        # If mouse is not over Node Editor, pass through all events
        # UNLESS we're in the middle of an operation (panning, moving, box selecting)
        if node_area is None and not (self._is_panning or self._is_moving or self._is_box_selecting):
            return {'PASS_THROUGH'}

        # Get the region for coordinate conversion
        region = None
        if node_area:
            for r in node_area.regions:
                if r.type == 'WINDOW':
                    region = r
                    break

        if region is None:
            return {'PASS_THROUGH'}

        state = get_canvas_state()
        mx = event.mouse_x - region.x
        my = event.mouse_y - region.y

        # ESC to exit canvas mode entirely
        if event.type == 'ESC' and event.value == 'PRESS':
            if self._is_panning or self._is_moving or self._is_box_selecting:
                # Cancel current operation
                self._is_panning = False
                self._is_moving = False
                self._is_box_selecting = False
                state.is_box_selecting = False
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}
            # Don't exit modal - we want to keep running
            return {'RUNNING_MODAL'}

        # ===== PANNING (Middle Mouse) =====
        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self._is_panning = True
                self._last_x = mx
                self._last_y = my
                return {'RUNNING_MODAL'}
            elif event.value == 'RELEASE':
                self._is_panning = False
                return {'RUNNING_MODAL'}

        if self._is_panning and event.type == 'MOUSEMOVE':
            dx = mx - self._last_x
            dy = my - self._last_y
            state.pan_x += dx / state.zoom
            state.pan_y += dy / state.zoom
            self._last_x = mx
            self._last_y = my
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # ===== ZOOMING (Scroll Wheel) =====
        if event.type == 'WHEELUPMOUSE':
            state.zoom_at(1.1, mx, my, region.width, region.height)
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            state.zoom_at(0.9, mx, my, region.width, region.height)
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # ===== SELECTION & MOVEMENT (Left Mouse) =====
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
                node_name = state.hit_test_node(cx, cy)

                if node_name:
                    # Clicked on a node - select and prepare to move
                    if not event.shift and node_name not in state.selected_nodes:
                        state.deselect_all()
                    state.select_node(node_name, extend=True)
                    self._is_moving = True
                    self._last_x = cx
                    self._last_y = cy
                else:
                    # Clicked on empty - start box selection
                    if not event.shift:
                        state.deselect_all()
                    self._is_box_selecting = True
                    self._start_x = mx
                    self._start_y = my
                    state.is_box_selecting = True
                    state.drag_start_x = mx
                    state.drag_start_y = my
                    state.drag_current_x = mx
                    state.drag_current_y = my

                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                if self._is_moving:
                    self._is_moving = False
                elif self._is_box_selecting:
                    # Complete box selection
                    cx1, cy1 = state.screen_to_canvas(
                        self._start_x, self._start_y,
                        region.width, region.height
                    )
                    cx2, cy2 = state.screen_to_canvas(
                        mx, my,
                        region.width, region.height
                    )
                    state.box_select(cx1, cy1, cx2, cy2, extend=event.shift)
                    self._is_box_selecting = False
                    state.is_box_selecting = False

                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

        # Mouse move during operations
        if event.type == 'MOUSEMOVE':
            if self._is_moving:
                cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
                dx = cx - self._last_x
                dy = cy - self._last_y

                for name in state.selected_nodes:
                    if name in state.node_visuals:
                        nv = state.node_visuals[name]
                        nv.x += dx
                        nv.y += dy

                self._last_x = cx
                self._last_y = cy
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif self._is_box_selecting:
                state.drag_current_x = mx
                state.drag_current_y = my
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

        # ===== KEYBOARD SHORTCUTS =====
        if event.type == 'A' and event.value == 'PRESS':
            if event.alt:
                state.deselect_all()
            else:
                # Toggle select all
                if state.selected_nodes:
                    state.deselect_all()
                else:
                    for name in state.node_visuals:
                        state.selected_nodes.add(name)
                    for nv in state.node_visuals.values():
                        nv.selected = True
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'X', 'DEL'} and event.value == 'PRESS':
            for name in list(state.selected_nodes):
                if name in state.node_visuals:
                    del state.node_visuals[name]
            state.selected_nodes.clear()
            state.active_node = None
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'F', 'HOME'} and event.value == 'PRESS':
            state.frame_all(region.width, region.height)
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'ACCENT_GRAVE' and event.value == 'PRESS':
            # Add node at cursor
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
            node_count = len(state.node_visuals) + 1
            name = f"Node{node_count}"
            state.node_visuals[name] = NodeVisual(
                node_name=name,
                x=cx - 70,
                y=cy + 40,
                width=140,
                height=80
            )
            state.node_visuals[name].input_ports = [(0, 0)]
            state.node_visuals[name].output_ports = [(0, 0)]
            state.select_node(name)
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Pass through other events
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        # Add demo nodes if empty
        state = get_canvas_state()
        if not state.node_visuals:
            _add_demo_nodes(state)

        # Ensure draw handler is active
        ensure_draw_handler()

        # Add timer for continuous updates
        wm = context.window_manager
        self._timer = wm.event_timer_add(1/60, window=context.window)

        wm.modal_handler_add(self)

        # Redraw all node editors
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()

        print("[OpenComp] Canvas modal started")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        print("[OpenComp] Canvas modal cancelled")


class OC_OT_canvas_start(Operator):
    """Start the OpenComp canvas mode"""
    bl_idname = "oc.canvas_start"
    bl_label = "Start OpenComp Canvas"

    def execute(self, context):
        bpy.ops.oc.canvas_modal('INVOKE_DEFAULT')
        return {'FINISHED'}


# Registration
classes = [
    OC_OT_canvas_modal,
    OC_OT_canvas_start,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Ensure draw handler is registered
    ensure_draw_handler()

    # Auto-start the canvas modal after a short delay
    def _start_canvas():
        try:
            bpy.ops.oc.canvas_modal('INVOKE_DEFAULT')
        except Exception as e:
            print(f"[OpenComp] Canvas auto-start failed: {e}")
        return None  # Don't repeat

    bpy.app.timers.register(_start_canvas, first_interval=0.5)


def unregister():
    remove_draw_handler()

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
