"""OpenComp Node Canvas — Operators.

Complete UI takeover for the Node Editor area.
Uses a modal operator that captures all input when mouse is in the area.
"""

import bpy
from bpy.types import Operator

from .state import (
    get_canvas_state, NodeVisual, LinkVisual,
    sync_from_tree, write_node_positions_to_tree, write_selection_to_tree
)
from .renderer import NodeCanvasRenderer


# Global state
_renderer = None
_draw_handler = None
_header_handler = None
_sidebar_handler = None
_modal_handler = None
_links = []


# Pending link cleanup state
_pending_link_check = {
    'active': False,
    'node_count': 0,
    'tree_name': None,
    'checks': 0,
}


class OC_MT_connection_style(bpy.types.Menu):
    """Connection line style menu."""
    bl_idname = "OC_MT_connection_style"
    bl_label = "Connection Style"

    def draw(self, context):
        layout = self.layout

        # Find the node tree from any available context
        tree = None
        if context.space_data and hasattr(context.space_data, 'node_tree'):
            tree = context.space_data.node_tree
        else:
            # Try to find from node editor area
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR' and space.tree_type == 'OC_NT_compositor':
                            tree = space.node_tree
                            break
                    break

        current = 'BEZIER'
        if tree and hasattr(tree, 'connection_style'):
            current = tree.connection_style

        styles = [
            ('BEZIER', "Bezier", "Classic smooth curves"),
            ('STRAIGHT', "Straight", "Direct lines"),
            ('DIRECTIONAL', "Directional", "Curves follow direction"),
            ('STEP', "Step", "Right-angle lines"),
            ('SMOOTH_STEP', "Smooth Step", "Rounded corners"),
        ]

        for style_id, name, desc in styles:
            op = layout.operator("oc.set_connection_style", text=name,
                                icon='CHECKMARK' if current == style_id else 'BLANK1')
            op.style = style_id


class OC_OT_set_connection_style(Operator):
    """Set the connection line style."""
    bl_idname = "oc.set_connection_style"
    bl_label = "Set Connection Style"
    bl_options = {'REGISTER', 'UNDO'}

    style: bpy.props.StringProperty(default='BEZIER')

    def execute(self, context):
        # Find the node tree from any available context
        tree = None
        if context.space_data and hasattr(context.space_data, 'node_tree'):
            tree = context.space_data.node_tree
        else:
            # Try to find from node editor area
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR' and space.tree_type == 'OC_NT_compositor':
                            tree = space.node_tree
                            break
                    break

        if tree and hasattr(tree, 'connection_style'):
            tree.connection_style = self.style
            # Redraw all node editors
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    area.tag_redraw()
        return {'FINISHED'}


def _check_pending_link_cleanup():
    """Timer callback to check if pending link should be cleared.

    Called repeatedly after menu is opened. Checks if a node was added
    or if menu was dismissed (no active popup/menu regions).
    """
    global _pending_link_check

    if not _pending_link_check['active']:
        return None  # Stop timer

    state = get_canvas_state()

    # If pending link already cleared by other means (ESC, click, etc.), stop
    if state.pending_link_node is None:
        _pending_link_check['active'] = False
        return None

    # Find the tree
    tree = None
    for ng in bpy.data.node_groups:
        if ng.name == _pending_link_check['tree_name']:
            tree = ng
            break

    if tree is None:
        # Tree gone, clear state
        state.pending_link_node = None
        state.pending_link_port = -1
        state.add_node_location = None
        _pending_link_check['active'] = False
        return None

    current_count = len(tree.nodes)

    if current_count > _pending_link_check['node_count']:
        # A node was added, clear pending state (connection already handled by OC_OT_add_node)
        state.pending_link_node = None
        state.pending_link_port = -1
        state.add_node_location = None
        _pending_link_check['active'] = False
        return None

    # Check if there's an active menu/popup by looking for temporary windows or popup regions
    # If no popup is active and no node was added, the menu was dismissed
    has_popup = False
    try:
        # Check for popup menus - they have a specific window type or region
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                for region in area.regions:
                    if region.type == 'HEADER' and region.height == 0:
                        continue
                    # Popup menus typically have specific characteristics
        # Use a simple heuristic: check if we're past the initial delay
        _pending_link_check['checks'] += 1

        # Only clear after menu has had time to respond (5 seconds = 50 checks)
        # This gives user plenty of time to browse the menu
        if _pending_link_check['checks'] >= 50:
            state.pending_link_node = None
            state.pending_link_port = -1
            state.add_node_location = None
            _pending_link_check['active'] = False

            # Trigger redraw
            for area in bpy.context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    area.tag_redraw()

            return None  # Stop timer
    except:
        pass

    # Keep checking every 100ms
    return 0.1


def get_renderer() -> NodeCanvasRenderer:
    """Get or create the global renderer."""
    global _renderer
    if _renderer is None:
        _renderer = NodeCanvasRenderer()
    return _renderer


def _is_popup_active():
    """Check if a popup menu or dialog is currently active."""
    try:
        # Check if there are multiple windows (popups create temporary windows)
        if len(bpy.context.window_manager.windows) > 1:
            return True
    except:
        pass
    return False


def _draw_callback():
    """Persistent draw callback for the node canvas."""
    global _links

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

    # Get the actual node tree
    tree = space.node_tree

    # Only sync from tree when no popup is active (file browser, menus, etc.)
    # When popup is active, we "freeze" the display using cached state
    if not _is_popup_active():
        _links = sync_from_tree(state, tree)

    # Get connection style from tree
    connection_style = 'BEZIER'
    if tree and hasattr(tree, 'connection_style'):
        connection_style = tree.connection_style

    # Always draw everything - nodes stay visible during file browser
    renderer.draw(state, region.width, region.height, _links, connection_style)


def _draw_header_callback():
    """Draw custom header elements for OpenComp.

    We keep the native Blender header visible (with our prepended File menu)
    and just add some styling or info on top if needed.
    """
    # Don't draw anything over the header - let Blender's native header
    # (with our prepended File menu) show through
    pass


def _draw_sidebar_callback():
    """Let the native Blender sidebar show for node properties."""
    # Don't draw over sidebar - let Blender's node panels show through
    pass


def ensure_draw_handler():
    """Ensure the persistent draw handlers are registered."""
    global _draw_handler, _header_handler, _sidebar_handler

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

    if _sidebar_handler is None:
        _sidebar_handler = bpy.types.SpaceNodeEditor.draw_handler_add(
            _draw_sidebar_callback, (), 'UI', 'POST_PIXEL'
        )
        print("[OpenComp] Canvas sidebar handler registered")


def remove_draw_handler():
    """Remove the persistent draw handlers."""
    global _draw_handler, _header_handler, _sidebar_handler

    if _draw_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None

    if _header_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_header_handler, 'HEADER')
        _header_handler = None

    if _sidebar_handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_sidebar_handler, 'UI')
        _sidebar_handler = None


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
    _is_linking = False
    _cut_mode_active = False  # True when X/Y/R is held (ready to cut)
    _cut_mode_reroute = False  # True if R key (insert reroute), False if X/Y (cut)
    _is_drag_cutting = False  # True when actively dragging the cut line
    _cut_was_performed = False  # True if a cut/reroute was done this session
    _last_x = 0
    _last_y = 0

    # Shake detection for disconnecting nodes
    _shake_history = []  # List of (x, timestamp) for detecting shake
    _shake_direction_changes = 0
    _shake_last_direction = 0  # -1 = left, 1 = right, 0 = none
    _shake_disconnected = False  # Prevent multiple disconnects per drag
    _start_x = 0
    _start_y = 0

    def _find_node_editor_area(self, context, mx, my):
        """Check if mouse is over a NODE_EDITOR area and return it.

        Uses a margin at the edges so Blender's area divider resize still works.
        Only returns the area if it's using an OpenComp tree.
        """
        EDGE_MARGIN = 4  # Small margin for area dividers
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                # Check if mouse is inside the area with margin for edge dividers
                if (area.x + EDGE_MARGIN <= mx <= area.x + area.width - EDGE_MARGIN and
                    area.y + EDGE_MARGIN <= my <= area.y + area.height - EDGE_MARGIN):
                    # Only capture if it's an OpenComp tree
                    space = area.spaces.active
                    if space and space.tree_type == 'OC_NT_compositor':
                        return area
        return None

    def _segments_intersect(self, p1, p2, p3, p4):
        """Check if line segment p1-p2 intersects with line segment p3-p4."""
        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

        return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and
                ccw(p1, p2, p3) != ccw(p1, p2, p4))

    def _link_intersects_cut_line(self, state, link, region):
        """Check if a Blender node link intersects with the drag cut line."""
        PORT_GAP = 14
        LINK_GAP = 18

        # Get node visuals for the link
        from_nv = state.node_visuals.get(link.from_node.name)
        to_nv = state.node_visuals.get(link.to_node.name)

        if not from_nv or not to_nv:
            return False

        # Calculate link start/end positions (same logic as renderer)
        # Output port (below node)
        from_idx = 0
        for i, out in enumerate(link.from_node.outputs):
            if out == link.from_socket:
                from_idx = i
                break
        num_outputs = max(len([o for o in link.from_node.outputs if o.enabled]), 1)
        x1 = from_nv.x + (from_idx + 1) * from_nv.width / (num_outputs + 1)
        y1 = from_nv.y - PORT_GAP - LINK_GAP

        # Input port (above node)
        to_idx = 0
        for i, inp in enumerate(link.to_node.inputs):
            if inp == link.to_socket:
                to_idx = i
                break
        num_inputs = max(len([o for o in link.to_node.inputs if o.enabled]), 1)
        x2 = to_nv.x + (to_idx + 1) * to_nv.width / (num_inputs + 1)
        y2 = to_nv.y + to_nv.height + PORT_GAP + LINK_GAP

        # Convert to screen coordinates
        sx1, sy1 = state.canvas_to_screen(x1, y1, region.width, region.height)
        sx2, sy2 = state.canvas_to_screen(x2, y2, region.width, region.height)

        # Generate bezier curve points
        offset = abs(sy2 - sy1) * 0.5
        if offset < 50:
            offset = 50

        cp1 = (sx1, sy1 - offset)
        cp2 = (sx2, sy2 + offset)

        # Sample the bezier curve
        segments = 16
        curve_points = []
        for i in range(segments + 1):
            t = i / segments
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt

            px = mt3 * sx1 + 3 * mt2 * t * cp1[0] + 3 * mt * t2 * cp2[0] + t3 * sx2
            py = mt3 * sy1 + 3 * mt2 * t * cp1[1] + 3 * mt * t2 * cp2[1] + t3 * sy2
            curve_points.append((px, py))

        # Cut line endpoints
        cut_start = (state.drag_cut_start_x, state.drag_cut_start_y)
        cut_end = (state.drag_cut_end_x, state.drag_cut_end_y)

        # Check each segment of the bezier curve against the cut line
        for i in range(len(curve_points) - 1):
            if self._segments_intersect(curve_points[i], curve_points[i + 1], cut_start, cut_end):
                return True

        return False

    def _get_link_intersection_point(self, state, link, region):
        """Get the canvas coordinates of where the cut line intersects a link.

        Returns (x, y) in canvas coordinates, or None if no intersection.
        """
        PORT_GAP = 14
        LINK_GAP = 18

        # Get node visuals for the link
        from_nv = state.node_visuals.get(link.from_node.name)
        to_nv = state.node_visuals.get(link.to_node.name)

        if not from_nv or not to_nv:
            return None

        # Calculate link start/end positions (same logic as renderer)
        from_idx = 0
        for i, out in enumerate(link.from_node.outputs):
            if out == link.from_socket:
                from_idx = i
                break
        num_outputs = max(len([o for o in link.from_node.outputs if o.enabled]), 1)
        x1 = from_nv.x + (from_idx + 1) * from_nv.width / (num_outputs + 1)
        y1 = from_nv.y - PORT_GAP - LINK_GAP

        to_idx = 0
        for i, inp in enumerate(link.to_node.inputs):
            if inp == link.to_socket:
                to_idx = i
                break
        num_inputs = max(len([o for o in link.to_node.inputs if o.enabled]), 1)
        x2 = to_nv.x + (to_idx + 1) * to_nv.width / (num_inputs + 1)
        y2 = to_nv.y + to_nv.height + PORT_GAP + LINK_GAP

        # Convert to screen coordinates
        sx1, sy1 = state.canvas_to_screen(x1, y1, region.width, region.height)
        sx2, sy2 = state.canvas_to_screen(x2, y2, region.width, region.height)

        # Generate bezier curve points
        offset = abs(sy2 - sy1) * 0.5
        if offset < 50:
            offset = 50

        cp1 = (sx1, sy1 - offset)
        cp2 = (sx2, sy2 + offset)

        # Sample the bezier curve
        segments = 16
        curve_points = []
        for i in range(segments + 1):
            t = i / segments
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt

            px = mt3 * sx1 + 3 * mt2 * t * cp1[0] + 3 * mt * t2 * cp2[0] + t3 * sx2
            py = mt3 * sy1 + 3 * mt2 * t * cp1[1] + 3 * mt * t2 * cp2[1] + t3 * sy2
            curve_points.append((px, py))

        # Cut line endpoints
        cut_start = (state.drag_cut_start_x, state.drag_cut_start_y)
        cut_end = (state.drag_cut_end_x, state.drag_cut_end_y)

        # Check each segment and find intersection point
        for i in range(len(curve_points) - 1):
            if self._segments_intersect(curve_points[i], curve_points[i + 1], cut_start, cut_end):
                # Return the midpoint of this curve segment as the intersection
                mid_x = (curve_points[i][0] + curve_points[i + 1][0]) / 2
                mid_y = (curve_points[i][1] + curve_points[i + 1][1]) / 2
                # Convert back to canvas coordinates
                cx, cy = state.screen_to_canvas(mid_x, mid_y, region.width, region.height)
                return (cx, cy)

        return None

    def modal(self, context, event):
        # Always redraw on timer
        if event.type == 'TIMER':
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    area.tag_redraw()
            return {'PASS_THROUGH'}

        # CRITICAL: Pass through empty/unknown event types immediately
        # These include internal drag-and-drop events (type 20515) that FileHandler needs
        if event.type == '' or event.type == 'NONE':
            return {'PASS_THROUGH'}

        # Get absolute mouse position
        abs_x = event.mouse_x
        abs_y = event.mouse_y

        # Check if mouse is over a Node Editor
        node_area = self._find_node_editor_area(context, abs_x, abs_y)

        # Track if we're in an active drag operation that needs to continue
        in_active_drag = (self._is_panning or self._is_moving or
                         self._is_box_selecting or self._is_drag_cutting or self._is_linking)

        # If mouse is not over Node Editor, pass through most events
        if node_area is None:
            if in_active_drag:
                if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                    # Cancel the drag operation if released outside
                    self._is_panning = False
                    self._is_moving = False
                    self._is_box_selecting = False
                    self._is_linking = False
                    self._is_drag_cutting = False
                    state = get_canvas_state()
                    state.is_box_selecting = False
                    state.is_linking = False
                    state.is_drag_cutting = False
                    state.link_from_node = None
                    # Tag Node Editor for redraw to clear drag visuals
                    for area in context.screen.areas:
                        if area.type == 'NODE_EDITOR':
                            area.tag_redraw()
                    return {'PASS_THROUGH'}
                elif event.type == 'MOUSEMOVE':
                    # For panning, we can still update even outside the area
                    if self._is_panning:
                        state = get_canvas_state()
                        # Find any Node Editor to use for reference
                        for area in context.screen.areas:
                            if area.type == 'NODE_EDITOR':
                                for r in area.regions:
                                    if r.type == 'WINDOW':
                                        mx = event.mouse_x - r.x
                                        my = event.mouse_y - r.y
                                        dx = mx - self._last_x
                                        dy = my - self._last_y
                                        state.pan_x += dx / state.zoom
                                        state.pan_y += dy / state.zoom
                                        self._last_x = mx
                                        self._last_y = my
                                        area.tag_redraw()
                                        return {'RUNNING_MODAL'}
                    # For other drags outside, just pass through mouse moves
                    return {'PASS_THROUGH'}
                else:
                    return {'PASS_THROUGH'}
            else:
                # Not in a drag, pass through all events (clicks for timeline, etc)
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

        # Only handle events for OpenComp trees
        space = node_area.spaces.active
        if space.tree_type != 'OC_NT_compositor':
            return {'PASS_THROUGH'}

        state = get_canvas_state()
        mx = event.mouse_x - region.x
        my = event.mouse_y - region.y

        # ESC to cancel current operation or clear pending link
        if event.type == 'ESC' and event.value == 'PRESS':
            # Cancel current operation
            self._is_panning = False
            self._is_moving = False
            self._is_box_selecting = False
            self._is_linking = False
            self._cut_mode_active = False
            self._cut_mode_reroute = False
            self._is_drag_cutting = False
            self._cut_was_performed = False
            state.is_box_selecting = False
            state.is_linking = False
            state.is_drag_cutting = False
            state.link_from_node = None

            # Also clear pending link state (clears lingering link line after menu dismiss)
            state.pending_link_node = None
            state.pending_link_port = -1
            state.add_node_location = None

            node_area.tag_redraw()
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

        # ===== SELECTION, MOVEMENT & LINKING (Left Mouse) =====
        # Skip if in cut mode - cut mode handles its own LEFTMOUSE
        if event.type == 'LEFTMOUSE' and not self._cut_mode_active:
            if event.value == 'PRESS':
                cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)

                # First, check if we clicked on a port (for linking)
                port_hit = state.hit_test_port(cx, cy)
                if port_hit:
                    port_node, port_index, is_output = port_hit
                    # Start link dragging
                    self._is_linking = True
                    state.is_linking = True
                    state.link_from_node = port_node
                    state.link_from_port = port_index
                    state.link_is_output = is_output
                    state.link_end_x = mx
                    state.link_end_y = my

                    # Debug: show port position info
                    nv = state.node_visuals.get(port_node)
                    if nv:
                        num_ports = max(len(nv.output_ports if is_output else nv.input_ports), 1)
                        px = nv.x + (port_index + 1) * nv.width / (num_ports + 1)
                        py = nv.y if is_output else nv.y + nv.height
                        sx, sy = state.canvas_to_screen(px, py, region.width, region.height)
                        print(f"[OpenComp] Link from {port_node}[{port_index}] ({'out' if is_output else 'in'})")
                        print(f"  Node: pos=({nv.x:.0f},{nv.y:.0f}) size=({nv.width:.0f}x{nv.height:.0f})")
                        print(f"  Port canvas: ({px:.0f},{py:.0f}) -> screen: ({sx:.0f},{sy:.0f})")
                        print(f"  Click screen: ({mx:.0f},{my:.0f}) canvas: ({cx:.0f},{cy:.0f})")
                        print(f"  Pan: ({state.pan_x:.0f},{state.pan_y:.0f}) Zoom: {state.zoom:.2f}")

                    node_area.tag_redraw()
                    return {'RUNNING_MODAL'}

                # Check if we clicked on a node (for selection/movement)
                node_name = state.hit_test_node(cx, cy)

                if node_name:
                    # Clicked on a node - select and prepare to move
                    if not event.shift and node_name not in state.selected_nodes:
                        state.deselect_all()
                    state.select_node(node_name, extend=True)
                    self._is_moving = True
                    self._last_x = cx
                    self._last_y = cy

                    # Reset shake detection
                    self._shake_history = []
                    self._shake_direction_changes = 0
                    self._shake_last_direction = 0
                    self._shake_disconnected = False

                    # Clear pending link state (clears lingering link line after menu dismiss)
                    state.pending_link_node = None
                    state.pending_link_port = -1
                    state.add_node_location = None

                    # Write selection back to Blender node tree
                    tree = node_area.spaces.active.node_tree if node_area else None
                    if tree:
                        write_selection_to_tree(state, tree)
                else:
                    # Clicked on empty - start box selection
                    if not event.shift:
                        state.deselect_all()
                        tree = node_area.spaces.active.node_tree if node_area else None
                        if tree:
                            write_selection_to_tree(state, tree)

                    # Clear pending link state (clears lingering link line after menu dismiss)
                    state.pending_link_node = None
                    state.pending_link_port = -1
                    state.add_node_location = None

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
                if self._is_linking:
                    # Complete link creation
                    cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
                    port_hit = state.hit_test_port(cx, cy)

                    tree = node_area.spaces.active.node_tree if node_area else None
                    if port_hit and tree:
                        to_node, to_port, to_is_output = port_hit
                        # Only connect output -> input or input -> output
                        if state.link_is_output != to_is_output:
                            try:
                                if state.link_is_output:
                                    # Dragged from output to input
                                    from_node = tree.nodes[state.link_from_node]
                                    target_node = tree.nodes[to_node]
                                    from_socket = from_node.outputs[state.link_from_port]
                                    to_socket = target_node.inputs[to_port]
                                else:
                                    # Dragged from input to output
                                    from_node = tree.nodes[to_node]
                                    target_node = tree.nodes[state.link_from_node]
                                    from_socket = from_node.outputs[to_port]
                                    to_socket = target_node.inputs[state.link_from_port]

                                tree.links.new(from_socket, to_socket)
                                print(f"[OpenComp] Created link: {from_node.name} -> {target_node.name}")
                            except Exception as e:
                                print(f"[OpenComp] Link creation failed: {e}")

                        # Reset link state
                        self._is_linking = False
                        state.is_linking = False
                        state.link_from_node = None
                        state.link_from_port = -1
                    else:
                        # Released in empty space - show Add menu and auto-connect
                        # Store pending link info for auto-connection
                        state.pending_link_node = state.link_from_node
                        state.pending_link_port = state.link_from_port
                        state.pending_link_is_output = state.link_is_output
                        state.add_node_location = (cx, cy)

                        # Reset visual link state
                        self._is_linking = False
                        state.is_linking = False
                        state.link_from_node = None
                        state.link_from_port = -1

                        # Set up cleanup timer to clear pending link if menu dismissed
                        tree = node_area.spaces.active.node_tree if node_area else None
                        if tree:
                            _pending_link_check['active'] = True
                            _pending_link_check['node_count'] = len(tree.nodes)
                            _pending_link_check['tree_name'] = tree.name
                            _pending_link_check['checks'] = 0
                            # Start checking after a short delay
                            bpy.app.timers.register(_check_pending_link_cleanup, first_interval=0.15)

                        # Show the Add menu with top-left at cursor
                        try:
                            bpy.ops.wm.call_menu(name='OC_MT_add_node')
                        except Exception as e:
                            print(f"[OpenComp] Could not open Add menu: {e}")

                elif self._is_moving:
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

                    # Write selection back to Blender node tree
                    tree = node_area.spaces.active.node_tree if node_area else None
                    if tree:
                        write_selection_to_tree(state, tree)

                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

        # Mouse move during operations
        if event.type == 'MOUSEMOVE':
            if self._is_linking:
                # Update link end position
                state.link_end_x = mx
                state.link_end_y = my
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif self._is_moving:
                import time
                cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
                dx = cx - self._last_x
                dy = cy - self._last_y

                # Shake detection - track horizontal movement
                if not self._shake_disconnected and abs(dx) > 2:  # Minimum movement threshold
                    current_time = time.time()
                    current_direction = 1 if dx > 0 else -1

                    # Add to history
                    self._shake_history.append((cx, current_time))

                    # Keep only recent history (last 0.5 seconds)
                    self._shake_history = [(x, t) for x, t in self._shake_history
                                           if current_time - t < 0.5]

                    # Detect direction change
                    if self._shake_last_direction != 0 and current_direction != self._shake_last_direction:
                        self._shake_direction_changes += 1

                    self._shake_last_direction = current_direction

                    # If we have 4+ direction changes in quick succession, disconnect
                    if self._shake_direction_changes >= 4:
                        tree = node_area.spaces.active.node_tree if node_area else None
                        if tree:
                            # Disconnect all links from selected nodes
                            links_to_remove = []
                            for link in tree.links:
                                if (link.from_node.name in state.selected_nodes or
                                    link.to_node.name in state.selected_nodes):
                                    links_to_remove.append(link)

                            for link in links_to_remove:
                                tree.links.remove(link)

                            if links_to_remove:
                                print(f"[OpenComp] Shake disconnect: removed {len(links_to_remove)} links")

                        self._shake_disconnected = True  # Prevent multiple disconnects
                        self._shake_direction_changes = 0

                for name in state.selected_nodes:
                    if name in state.node_visuals:
                        nv = state.node_visuals[name]
                        nv.x += dx
                        nv.y += dy

                self._last_x = cx
                self._last_y = cy

                # Write positions back to Blender node tree in real-time
                tree = node_area.spaces.active.node_tree if node_area else None
                if tree:
                    write_node_positions_to_tree(state, tree)

                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif self._is_box_selecting:
                state.drag_current_x = mx
                state.drag_current_y = my
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

            elif self._is_drag_cutting:
                # Update drag cut end position
                state.drag_cut_end_x = mx
                state.drag_cut_end_y = my
                node_area.tag_redraw()
                return {'RUNNING_MODAL'}

        # ===== KEYBOARD SHORTCUTS =====
        # Get tree from node_area (more reliable than context.space_data)
        tree = node_area.spaces.active.node_tree if node_area else None

        if event.type == 'A' and event.value == 'PRESS' and not event.shift:
            # A = select all, Alt+A = deselect all (Shift+A is handled separately for Add menu)
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

            # Write selection back to Blender node tree
            if tree:
                write_selection_to_tree(state, tree)

            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # ===== DRAG CUT (X or Y key + click drag) / REROUTE (R key + click drag) =====
        # Step 1: Enter cut mode when X/Y/R is pressed
        if event.type in {'X', 'Y'} and event.value == 'PRESS' and not self._cut_mode_active:
            self._cut_mode_active = True
            self._cut_mode_reroute = False  # Cut mode
            self._cut_was_performed = False
            return {'RUNNING_MODAL'}

        if event.type == 'B' and event.value == 'PRESS' and not self._cut_mode_active:
            self._cut_mode_active = True
            self._cut_mode_reroute = True  # Reroute mode
            self._cut_was_performed = False
            return {'RUNNING_MODAL'}

        # Step 2: Start drawing cut line on left click while in cut mode
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and self._cut_mode_active:
            self._is_drag_cutting = True
            state.is_drag_cutting = True
            state.drag_cut_start_x = mx
            state.drag_cut_start_y = my
            state.drag_cut_end_x = mx
            state.drag_cut_end_y = my
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Step 3: Perform cut/reroute on mouse release while dragging
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self._is_drag_cutting:
            if tree:
                if self._cut_mode_reroute:
                    # Insert reroute nodes at intersections
                    reroute_count = 0
                    for link in list(tree.links):
                        intersection = self._get_link_intersection_point(state, link, region)
                        if intersection:
                            cx, cy = intersection
                            from_socket = link.from_socket
                            to_socket = link.to_socket

                            tree.links.remove(link)

                            reroute = tree.nodes.new('OC_N_reroute')
                            # Center the reroute at intersection (location is bottom-left)
                            # Default collapsed size is 140x32
                            reroute.location.x = cx - 70
                            reroute.location.y = cy - 16
                            reroute.hide = True

                            tree.links.new(from_socket, reroute.inputs[0])
                            tree.links.new(reroute.outputs[0], to_socket)
                            reroute_count += 1

                    if reroute_count:
                        print(f"[OpenComp] Inserted {reroute_count} reroute nodes")
                        self._cut_was_performed = True
                else:
                    # Cut mode - remove intersecting links
                    links_to_remove = []
                    for link in tree.links:
                        if self._link_intersects_cut_line(state, link, region):
                            links_to_remove.append(link)

                    for link in links_to_remove:
                        tree.links.remove(link)

                    if links_to_remove:
                        print(f"[OpenComp] Cut {len(links_to_remove)} links")
                        self._cut_was_performed = True

            # End drag cutting (but stay in cut mode if key still held)
            self._is_drag_cutting = False
            state.is_drag_cutting = False
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Step 4: Exit cut mode when key is released
        if event.type in {'X', 'Y'} and event.value == 'RELEASE':
            if self._cut_mode_active and not self._cut_mode_reroute:
                # If we never performed a cut, X deletes selected nodes
                if not self._cut_was_performed and event.type == 'X' and tree:
                    for name in list(state.selected_nodes):
                        if name in tree.nodes:
                            tree.nodes.remove(tree.nodes[name])
                    state.selected_nodes.clear()
                    state.active_node = None
                    node_area.tag_redraw()

                self._cut_mode_active = False
                self._cut_mode_reroute = False
                self._is_drag_cutting = False
                self._cut_was_performed = False
                state.is_drag_cutting = False
            return {'RUNNING_MODAL'}

        if event.type == 'B' and event.value == 'RELEASE':
            if self._cut_mode_active and self._cut_mode_reroute:
                self._cut_mode_active = False
                self._cut_mode_reroute = False
                self._is_drag_cutting = False
                self._cut_was_performed = False
                state.is_drag_cutting = False
            return {'RUNNING_MODAL'}

        if event.type == 'DEL' and event.value == 'PRESS':
            # DEL always deletes selected nodes
            if tree:
                for name in list(state.selected_nodes):
                    if name in tree.nodes:
                        tree.nodes.remove(tree.nodes[name])

            state.selected_nodes.clear()
            state.active_node = None
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type in {'F', 'HOME'} and event.value == 'PRESS':
            state.frame_all(region.width, region.height)
            node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # ===== ADD MENU (Right-click, Tab, Shift+A, Backtick) =====
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            # Store cursor position for new node placement
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
            state.add_node_location = (cx, cy)
            # Clear any pending link (this is a fresh add, not from link drag)
            state.pending_link_node = None
            state.pending_link_port = -1

            # Open our custom Add menu with top-left at cursor
            try:
                bpy.ops.wm.call_menu(name='OC_MT_add_node')
            except Exception as e:
                print(f"[OpenComp] Could not open Add menu: {e}")
            return {'RUNNING_MODAL'}

        if event.type == 'ACCENT_GRAVE' and event.value == 'PRESS':
            # Store cursor position for new node placement
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
            state.add_node_location = (cx, cy)
            # Clear any pending link (this is a fresh add, not from link drag)
            state.pending_link_node = None
            state.pending_link_port = -1

            # Open our custom Add menu (Backtick - Nuke style)
            try:
                bpy.ops.wm.call_menu(name='OC_MT_add_node')
            except Exception as e:
                print(f"[OpenComp] Could not open Add menu: {e}")
            return {'RUNNING_MODAL'}

        if event.type == 'TAB' and event.value == 'PRESS':
            # Tab also opens Add menu (Nuke style)
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
            state.add_node_location = (cx, cy)
            # Clear any pending link (this is a fresh add, not from link drag)
            state.pending_link_node = None
            state.pending_link_port = -1

            try:
                bpy.ops.wm.call_menu(name='OC_MT_add_node')
            except Exception as e:
                print(f"[OpenComp] Could not open Add menu: {e}")
            return {'RUNNING_MODAL'}

        if event.type == 'A' and event.value == 'PRESS' and event.shift:
            # Shift+A also opens Add menu (Blender style)
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
            state.add_node_location = (cx, cy)
            # Clear any pending link (this is a fresh add, not from link drag)
            state.pending_link_node = None
            state.pending_link_port = -1

            try:
                bpy.ops.wm.call_menu(name='OC_MT_add_node')
            except Exception as e:
                print(f"[OpenComp] Could not open Add menu: {e}")
            return {'RUNNING_MODAL'}

        # L key - cycle connection line style
        if event.type == 'L' and event.value == 'PRESS' and not event.shift and not event.ctrl:
            tree = node_area.spaces.active.node_tree
            if tree and hasattr(tree, 'connection_style'):
                styles = ['BEZIER', 'STRAIGHT', 'DIRECTIONAL', 'STEP', 'SMOOTH_STEP']
                current = tree.connection_style
                try:
                    idx = styles.index(current)
                    next_idx = (idx + 1) % len(styles)
                except ValueError:
                    next_idx = 0
                tree.connection_style = styles[next_idx]
                node_area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Ctrl+V - paste file path from clipboard and create Read node
        if event.type == 'V' and event.value == 'PRESS' and event.ctrl and not event.shift:
            import os
            clipboard = context.window_manager.clipboard
            # Check if clipboard contains a file path
            if clipboard and os.path.exists(clipboard.strip()):
                filepath = clipboard.strip()
                # Check file extension
                ext = os.path.splitext(filepath)[1].lower()
                if ext in {'.exr', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.hdr', '.dpx', '.cin'}:
                    cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)
                    # Call drop operator which handles sequence detection
                    bpy.ops.oc.read_drop(filepath=filepath)
                    node_area.tag_redraw()
                    return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        # R key - quick add Read node and open file browser
        if event.type == 'R' and event.value == 'PRESS' and not event.shift and not event.ctrl:
            cx, cy = state.screen_to_canvas(mx, my, region.width, region.height)

            # Create Read node at cursor
            tree = node_area.spaces.active.node_tree
            if tree:
                new_node = tree.nodes.new('OC_N_read')
                new_node.location = (cx, cy)

                # Deselect all nodes and select new node
                for n in tree.nodes:
                    n.select = False
                new_node.select = True
                tree.nodes.active = new_node

                # Sync to canvas state
                sync_from_tree(state, tree)
                node_area.tag_redraw()

                # Open file browser for this node
                try:
                    bpy.ops.oc.read_browse('INVOKE_DEFAULT', node_name=new_node.name)
                except Exception as e:
                    print(f"[OpenComp] Could not open file browser: {e}")

            return {'RUNNING_MODAL'}

        # Pass through other events
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
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


class OC_OT_add_node(Operator):
    """Add a node at the cursor position without grab mode"""
    bl_idname = "oc.add_node"
    bl_label = "Add Node"
    bl_options = {'REGISTER', 'UNDO'}

    node_type: bpy.props.StringProperty(
        name="Node Type",
        description="The bl_idname of the node to add",
        default=""
    )

    def execute(self, context):
        # Try to get tree from current space
        space = context.space_data
        tree = None

        if space and space.type == 'NODE_EDITOR':
            tree = getattr(space, 'node_tree', None)

        # Fallback: search all screens for OpenComp tree
        if not tree or tree.bl_idname != 'OC_NT_compositor':
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type == 'NODE_EDITOR':
                        for sp in area.spaces:
                            if sp.type == 'NODE_EDITOR' and sp.node_tree:
                                if sp.node_tree.bl_idname == 'OC_NT_compositor':
                                    tree = sp.node_tree
                                    break

        if not tree or tree.bl_idname != 'OC_NT_compositor':
            self.report({'WARNING'}, "No OpenComp node tree found")
            return {'CANCELLED'}

        # Get position from canvas state
        state = get_canvas_state()
        pos = state.add_node_location or (0, 0)

        # Create the node directly - no grab mode
        try:
            node = tree.nodes.new(self.node_type)
            node.location = pos
            # Select only this node
            for n in tree.nodes:
                n.select = False
            node.select = True
            tree.nodes.active = node
            # Clear the add location
            state.add_node_location = None
            # Update known nodes so sync doesn't reposition
            state._known_nodes.add(node.name)

            # Auto-connect if we have a pending link (dragged from port to empty space)
            if state.pending_link_node is not None:
                try:
                    from_node_obj = tree.nodes.get(state.pending_link_node)
                    if from_node_obj:
                        if state.pending_link_is_output:
                            # Dragged from output - connect to new node's first input
                            if len(from_node_obj.outputs) > state.pending_link_port and len(node.inputs) > 0:
                                from_socket = from_node_obj.outputs[state.pending_link_port]
                                to_socket = node.inputs[0]
                                tree.links.new(from_socket, to_socket)
                                print(f"[OpenComp] Auto-connected: {from_node_obj.name} -> {node.name}")
                        else:
                            # Dragged from input - connect new node's first output to that input
                            if len(from_node_obj.inputs) > state.pending_link_port and len(node.outputs) > 0:
                                from_socket = node.outputs[0]
                                to_socket = from_node_obj.inputs[state.pending_link_port]
                                tree.links.new(from_socket, to_socket)
                                print(f"[OpenComp] Auto-connected: {node.name} -> {from_node_obj.name}")
                except Exception as e:
                    print(f"[OpenComp] Auto-connect failed: {e}")

                # Clear pending link state
                state.pending_link_node = None
                state.pending_link_port = -1

        except Exception as e:
            self.report({'ERROR'}, f"Could not add node: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


# Custom Add Node Menu - positioned with top-left at cursor
class OC_MT_add_node(bpy.types.Menu):
    """OpenComp Node Add Menu"""
    bl_idname = "OC_MT_add_node"
    bl_label = "Add"

    def draw(self, context):
        layout = self.layout

        # Input nodes
        layout.label(text="Input", icon='IMPORT')
        op = layout.operator("oc.add_node", text="Read")
        op.node_type = "OC_N_read"
        op = layout.operator("oc.add_node", text="Constant")
        op.node_type = "OC_N_constant"

        layout.separator()

        # Color nodes
        layout.label(text="Color", icon='COLOR')
        op = layout.operator("oc.add_node", text="Grade")
        op.node_type = "OC_N_grade"
        op = layout.operator("oc.add_node", text="CDL")
        op.node_type = "OC_N_cdl"

        layout.separator()

        # Merge nodes
        layout.label(text="Merge", icon='NODE_COMPOSITING')
        op = layout.operator("oc.add_node", text="Over")
        op.node_type = "OC_N_over"
        op = layout.operator("oc.add_node", text="Merge")
        op.node_type = "OC_N_merge"
        op = layout.operator("oc.add_node", text="Shuffle")
        op.node_type = "OC_N_shuffle"

        layout.separator()

        # Filter nodes
        layout.label(text="Filter", icon='MOD_SMOOTH')
        op = layout.operator("oc.add_node", text="Blur")
        op.node_type = "OC_N_blur"
        op = layout.operator("oc.add_node", text="Sharpen")
        op.node_type = "OC_N_sharpen"

        layout.separator()

        # Transform nodes
        layout.label(text="Transform", icon='ORIENTATION_GLOBAL')
        op = layout.operator("oc.add_node", text="Transform")
        op.node_type = "OC_N_transform"
        op = layout.operator("oc.add_node", text="Crop")
        op.node_type = "OC_N_crop"

        layout.separator()

        # Output nodes
        layout.label(text="Output", icon='EXPORT')
        op = layout.operator("oc.add_node", text="Write")
        op.node_type = "OC_N_write"
        op = layout.operator("oc.add_node", text="Viewer")
        op.node_type = "OC_N_viewer"

        layout.separator()

        # Draw nodes
        layout.label(text="Draw", icon='MESH_CIRCLE')
        op = layout.operator("oc.add_node", text="Roto")
        op.node_type = "OC_N_roto"

        layout.separator()

        # Utility nodes
        layout.label(text="Utility", icon='ARROW_LEFTRIGHT')
        op = layout.operator("oc.add_node", text="Reroute")
        op.node_type = "OC_N_reroute"


# ============================================================================
# Toolbar Panel (shows in Node Editor's TOOLS region)
# ============================================================================

class OC_PT_toolbar(bpy.types.Panel):
    """OpenComp Toolbar - Nuke-style tool icons."""
    bl_idname = "OC_PT_toolbar"
    bl_label = "Tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return (context.space_data and
                context.space_data.tree_type == 'OC_NT_compositor')

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.3

        # File operations
        col = layout.column(align=True)
        col.operator("wm.open_mainfile", text="", icon='FILE_FOLDER')
        col.operator("wm.save_mainfile", text="", icon='FILE_TICK')
        col.operator("wm.save_as_mainfile", text="", icon='FILE_NEW')

        layout.separator()

        # Add nodes
        col = layout.column(align=True)
        op = col.operator("oc.add_node", text="", icon='FILE_IMAGE')
        op.node_type = "OC_N_read"
        op = col.operator("oc.add_node", text="", icon='COLOR')
        op.node_type = "OC_N_grade"
        op = col.operator("oc.add_node", text="", icon='SELECT_SUBTRACT')
        op.node_type = "OC_N_over"
        op = col.operator("oc.add_node", text="", icon='MOD_SMOOTH')
        op.node_type = "OC_N_blur"
        op = col.operator("oc.add_node", text="", icon='ORIENTATION_GLOBAL')
        op.node_type = "OC_N_transform"

        layout.separator()

        # View operations
        col = layout.column(align=True)
        col.operator("oc.add_node", text="", icon='HIDE_OFF').node_type = "OC_N_viewer"


# Registration
classes = [
    OC_OT_canvas_modal,
    OC_OT_canvas_start,
    OC_OT_add_node,
    OC_OT_set_connection_style,
    OC_MT_add_node,
    OC_MT_connection_style,
    OC_PT_toolbar,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register draw handlers for custom canvas overlay
    ensure_draw_handler()

    # Toolbar disabled - too distracting
    # from . import toolbar
    # toolbar.register()

    # Auto-start the canvas modal after a short delay
    def _start_canvas():
        try:
            bpy.ops.oc.canvas_modal('INVOKE_DEFAULT')
        except Exception as e:
            print(f"[OpenComp] Canvas auto-start failed: {e}")
        return None  # Don't repeat

    bpy.app.timers.register(_start_canvas, first_interval=0.5)

    print("[OpenComp] Canvas operators registered")


def unregister():
    # Toolbar disabled
    # from . import toolbar
    # toolbar.unregister()

    remove_draw_handler()

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
