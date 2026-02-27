"""OpenComp Node Canvas — GPU renderer.

Draws the node graph using Blender's GPU module.
Supports nodes, connections, ports, selection, and grid.
"""

import gpu
from gpu_extras.batch import batch_for_shader
import blf
import math
from typing import List, Tuple

from .state import CanvasState, NodeVisual, LinkVisual
from .icons import draw_icon, get_icon_for_node_type


# Shader sources
VERT_2D_UNIFORM_COLOR = '''
uniform mat4 ModelViewProjectionMatrix;
in vec2 pos;
void main() {
    gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
}
'''

FRAG_2D_UNIFORM_COLOR = '''
uniform vec4 color;
out vec4 fragColor;
void main() {
    fragColor = color;
}
'''


class NodeCanvasRenderer:
    """Renders the node canvas using GPU module."""

    # Colors
    COLOR_BG = (0.15, 0.15, 0.15, 1.0)
    COLOR_GRID_MINOR = (0.2, 0.2, 0.2, 0.5)
    COLOR_GRID_MAJOR = (0.25, 0.25, 0.25, 0.8)
    COLOR_NODE_BG = (0.3, 0.3, 0.3, 1.0)
    COLOR_NODE_HEADER = (0.2, 0.4, 0.3, 1.0)
    COLOR_NODE_SELECTED = (0.2, 0.55, 0.35, 1.0)
    COLOR_NODE_BORDER = (0.1, 0.1, 0.1, 1.0)
    COLOR_PORT_INPUT = (0.3, 0.6, 0.3, 1.0)
    COLOR_PORT_OUTPUT = (0.6, 0.3, 0.3, 1.0)
    COLOR_LINK = (0.8, 0.8, 0.8, 1.0)
    COLOR_LINK_DRAG = (0.2, 0.55, 0.35, 1.0)
    COLOR_BOX_SELECT = (0.2, 0.55, 0.35, 0.3)  # OpenComp accent
    COLOR_BOX_SELECT_BORDER = (0.2, 0.55, 0.35, 1.0)  # OpenComp accent
    COLOR_TEXT = (0.9, 0.9, 0.9, 1.0)

    # Dimensions
    NODE_HEADER_HEIGHT = 32
    NODE_CORNER_RADIUS = 8
    PORT_RADIUS = 6
    PORT_GAP = 14  # Gap between port center and node edge
    LINK_GAP = 18  # Gap between link endpoint and port center
    PORT_SPACING = 20
    GRID_SIZE_MINOR = 20
    GRID_SIZE_MAJOR = 100


    def __init__(self):
        self._shader = None
        self._font_id = 0

    def _get_shader(self):
        """Get or create the 2D color shader."""
        if self._shader is None:
            self._shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        return self._shader

    def _rounded_rect_verts(self, min_x: float, min_y: float, max_x: float, max_y: float,
                            radius: float, segments: int = 6):
        """Generate vertices and indices for a rounded rectangle."""
        verts = []
        indices = []

        # Clamp radius to half the smallest dimension
        w = max_x - min_x
        h = max_y - min_y
        r = min(radius, w / 2, h / 2)

        # Center point for triangle fan
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        verts.append((cx, cy))

        # Generate corner arcs
        corners = [
            (max_x - r, max_y - r, 0),           # Top-right
            (min_x + r, max_y - r, math.pi/2),   # Top-left
            (min_x + r, min_y + r, math.pi),     # Bottom-left
            (max_x - r, min_y + r, 3*math.pi/2), # Bottom-right
        ]

        for corner_x, corner_y, start_angle in corners:
            for i in range(segments + 1):
                angle = start_angle + (i / segments) * (math.pi / 2)
                x = corner_x + r * math.cos(angle)
                y = corner_y + r * math.sin(angle)
                verts.append((x, y))

        # Create triangle fan indices
        num_verts = len(verts)
        for i in range(1, num_verts - 1):
            indices.append((0, i, i + 1))
        # Close the fan
        indices.append((0, num_verts - 1, 1))

        return verts, indices

    def _rounded_rect_outline(self, min_x: float, min_y: float, max_x: float, max_y: float,
                              radius: float, segments: int = 6):
        """Generate vertices for a rounded rectangle outline (LINE_STRIP)."""
        verts = []

        # Clamp radius
        w = max_x - min_x
        h = max_y - min_y
        r = min(radius, w / 2, h / 2)

        corners = [
            (max_x - r, max_y - r, 0),           # Top-right
            (min_x + r, max_y - r, math.pi/2),   # Top-left
            (min_x + r, min_y + r, math.pi),     # Bottom-left
            (max_x - r, min_y + r, 3*math.pi/2), # Bottom-right
        ]

        for corner_x, corner_y, start_angle in corners:
            for i in range(segments + 1):
                angle = start_angle + (i / segments) * (math.pi / 2)
                x = corner_x + r * math.cos(angle)
                y = corner_y + r * math.sin(angle)
                verts.append((x, y))

        # Close the loop
        verts.append(verts[0])

        return verts

    # Header padding that extends into canvas area
    HEADER_BOTTOM_PADDING = 25

    def _draw_background(self, rw: float, rh: float):
        """Draw solid background to completely cover Blender's node editor."""
        shader = self._get_shader()
        # Leave gap at top for header padding
        top = rh - self.HEADER_BOTTOM_PADDING
        verts = [(0, 0), (rw, 0), (rw, top), (0, top)]
        indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", self.COLOR_BG)
        batch.draw(shader)

        # Draw header extension area
        header_verts = [(0, top), (rw, top), (rw, rh), (0, rh)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": header_verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", (0.18, 0.18, 0.18, 1.0))  # Match header color
        batch.draw(shader)

        # Header bottom border
        gpu.state.line_width_set(1.0)
        border_verts = [(0, top), (rw, top)]
        batch = batch_for_shader(shader, 'LINES', {"pos": border_verts})
        shader.bind()
        shader.uniform_float("color", (0.1, 0.1, 0.1, 1.0))
        batch.draw(shader)

    def _draw_edge_covers(self, rw: float, rh: float):
        """Draw covers over the edge chevrons (toolbar/sidebar toggles)."""
        shader = self._get_shader()
        indices = [(0, 1, 2), (0, 2, 3)]

        # Disable scissor test to draw OUTSIDE region bounds
        gpu.state.scissor_test_set(False)

        # Cover the right edge chevron (extends beyond region width)
        right_verts = [(rw, 0), (rw + 30, 0), (rw + 30, rh), (rw, rh)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": right_verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", self.COLOR_BG)
        batch.draw(shader)

        # Re-enable scissor test
        gpu.state.scissor_test_set(True)

    def draw(self, state: CanvasState, region_width: float, region_height: float,
             links: List[LinkVisual] = None, connection_style: str = 'BEZIER'):
        """Draw the entire canvas."""
        gpu.state.blend_set('ALPHA')

        # Store connection style for link drawing
        self._connection_style = connection_style

        # Draw solid background to completely hide Blender's node editor
        self._draw_background(region_width, region_height)

        # Cover the edge arrows (toolbar/sidebar toggles)
        self._draw_edge_covers(region_width, region_height)

        # Draw grid
        self._draw_grid(state, region_width, region_height)

        # Draw links
        if links:
            for link in links:
                self._draw_link(state, link, region_width, region_height)

        # Draw link being dragged
        if state.is_linking and state.link_from_node:
            self._draw_drag_link(state, region_width, region_height)

        # Draw pending link (when Add menu is open after dragging to empty space)
        if state.pending_link_node and state.add_node_location:
            self._draw_pending_link(state, region_width, region_height)

        # Draw nodes
        for name, nv in state.node_visuals.items():
            self._draw_node(state, nv, region_width, region_height)

        # Draw box selection
        if state.is_box_selecting:
            self._draw_box_selection(state, region_width, region_height)

        # Draw drag cut line
        if state.is_drag_cutting:
            self._draw_drag_cut_line(state)

        gpu.state.blend_set('NONE')

    def _draw_grid(self, state: CanvasState, rw: float, rh: float):
        """Draw background grid."""
        shader = self._get_shader()

        # Calculate visible canvas bounds
        left, bottom = state.screen_to_canvas(0, 0, rw, rh)
        right, top = state.screen_to_canvas(rw, rh, rw, rh)

        # Minor grid
        minor_lines = []
        x = math.floor(left / self.GRID_SIZE_MINOR) * self.GRID_SIZE_MINOR
        while x <= right:
            sx1, sy1 = state.canvas_to_screen(x, bottom, rw, rh)
            sx2, sy2 = state.canvas_to_screen(x, top, rw, rh)
            minor_lines.extend([(sx1, sy1), (sx2, sy2)])
            x += self.GRID_SIZE_MINOR

        y = math.floor(bottom / self.GRID_SIZE_MINOR) * self.GRID_SIZE_MINOR
        while y <= top:
            sx1, sy1 = state.canvas_to_screen(left, y, rw, rh)
            sx2, sy2 = state.canvas_to_screen(right, y, rw, rh)
            minor_lines.extend([(sx1, sy1), (sx2, sy2)])
            y += self.GRID_SIZE_MINOR

        if minor_lines:
            batch = batch_for_shader(shader, 'LINES', {"pos": minor_lines})
            shader.bind()
            shader.uniform_float("color", self.COLOR_GRID_MINOR)
            batch.draw(shader)

        # Major grid
        major_lines = []
        x = math.floor(left / self.GRID_SIZE_MAJOR) * self.GRID_SIZE_MAJOR
        while x <= right:
            sx1, sy1 = state.canvas_to_screen(x, bottom, rw, rh)
            sx2, sy2 = state.canvas_to_screen(x, top, rw, rh)
            major_lines.extend([(sx1, sy1), (sx2, sy2)])
            x += self.GRID_SIZE_MAJOR

        y = math.floor(bottom / self.GRID_SIZE_MAJOR) * self.GRID_SIZE_MAJOR
        while y <= top:
            sx1, sy1 = state.canvas_to_screen(left, y, rw, rh)
            sx2, sy2 = state.canvas_to_screen(right, y, rw, rh)
            major_lines.extend([(sx1, sy1), (sx2, sy2)])
            y += self.GRID_SIZE_MAJOR

        if major_lines:
            batch = batch_for_shader(shader, 'LINES', {"pos": major_lines})
            shader.bind()
            shader.uniform_float("color", self.COLOR_GRID_MAJOR)
            batch.draw(shader)

    def _draw_node(self, state: CanvasState, nv: NodeVisual, rw: float, rh: float):
        """Draw a single node with rounded corners."""
        shader = self._get_shader()

        # Special handling for reroute nodes - draw as simple circle/dot
        if nv.node_type == 'OC_N_reroute':
            self._draw_reroute_node(state, nv, rw, rh)
            return

        # Convert node corners to screen coords
        # nv.x, nv.y is bottom-left corner (Blender convention, Y increases upward)
        # Node spans from (nv.x, nv.y) to (nv.x + width, nv.y + height)
        x1, y1 = state.canvas_to_screen(nv.x, nv.y, rw, rh)
        x2, y2 = state.canvas_to_screen(nv.x + nv.width, nv.y + nv.height, rw, rh)

        # Ensure correct ordering (screen Y increases upward in Blender)
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        # Scale corner radius with zoom
        corner_r = self.NODE_CORNER_RADIUS * state.zoom

        # Use the node's assigned color for the header (not selection color)
        header_color = (*nv.color, 1.0)

        if nv.collapsed:
            # Collapsed node: just draw rounded header bar
            verts, indices = self._rounded_rect_verts(min_x, min_y, max_x, max_y, corner_r)
            batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
            shader.bind()
            shader.uniform_float("color", header_color)
            batch.draw(shader)
        else:
            # Expanded node: body + header (both rounded)
            # Node body (full rounded rect)
            body_verts, body_indices = self._rounded_rect_verts(min_x, min_y, max_x, max_y, corner_r)
            batch = batch_for_shader(shader, 'TRIS', {"pos": body_verts}, indices=body_indices)
            shader.bind()
            shader.uniform_float("color", self.COLOR_NODE_BG)
            batch.draw(shader)

            # Header (top portion with rounded top corners only)
            header_screen_height = self.NODE_HEADER_HEIGHT * state.zoom
            header_bottom = max_y - header_screen_height
            # Use rounded rect for header, but it will overlap body
            header_verts, header_indices = self._rounded_rect_verts(
                min_x, header_bottom, max_x, max_y, corner_r
            )
            batch = batch_for_shader(shader, 'TRIS', {"pos": header_verts}, indices=header_indices)
            shader.bind()
            shader.uniform_float("color", header_color)
            batch.draw(shader)

        # Rounded border - use brightened node color when selected, normal border otherwise
        if nv.selected:
            # Brighten the node color for selection (boost by 50%, clamp to 1.0)
            sel_color = (
                min(nv.color[0] * 1.5 + 0.2, 1.0),
                min(nv.color[1] * 1.5 + 0.2, 1.0),
                min(nv.color[2] * 1.5 + 0.2, 1.0),
                1.0
            )
            # Draw thicker selection outline (3 passes at different offsets for thickness)
            for offset in [0, 1, -1]:
                border_verts = self._rounded_rect_outline(
                    min_x - offset, min_y - offset,
                    max_x + offset, max_y + offset,
                    corner_r
                )
                batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
                shader.bind()
                shader.uniform_float("color", sel_color)
                batch.draw(shader)
        else:
            # Normal border
            border_verts = self._rounded_rect_outline(min_x, min_y, max_x, max_y, corner_r)
            batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
            shader.bind()
            shader.uniform_float("color", self.COLOR_NODE_BORDER)
            batch.draw(shader)

        # Draw icon on the left side of the node with left padding
        icon_size = 14 * state.zoom
        icon_x = min_x + 18 * state.zoom  # More left padding
        icon_y = (min_y + max_y) / 2
        icon_name = get_icon_for_node_type(nv.node_type)
        icon_color = (0.9, 0.9, 0.9, 0.9)
        draw_icon(icon_name, icon_x, icon_y, icon_size, icon_color, line_width=2.0)

        # Node name text (truly centered on the node)
        blf.size(self._font_id, int(11 * state.zoom))
        blf.color(self._font_id, *self.COLOR_TEXT)
        name_width, name_height = blf.dimensions(self._font_id, nv.node_name)
        text_x = (min_x + max_x) / 2 - name_width / 2  # Horizontally centered
        text_y = (min_y + max_y) / 2 - name_height / 2  # Vertically centered
        blf.position(self._font_id, text_x, text_y, 0)
        blf.draw(self._font_id, nv.node_name)

        # Node label text (to the right of the node)
        if nv.label:
            blf.size(self._font_id, int(10 * state.zoom))
            blf.color(self._font_id, 0.5, 0.5, 0.5, 1.0)  # Dimmer color for label
            label_x = max_x + 8 * state.zoom  # Right of node with small gap
            label_y = (min_y + max_y) / 2 - 4 * state.zoom  # Vertically centered
            blf.position(self._font_id, label_x, label_y, 0)
            blf.draw(self._font_id, nv.label)

        # Calculate and draw ports
        self._update_port_positions(state, nv, rw, rh)
        self._draw_ports(state, nv, rw, rh)

    def _update_port_positions(self, state: CanvasState, nv: NodeVisual,
                               rw: float, rh: float):
        """Update port positions for a node (canvas coordinates)."""
        # nv.y is bottom-left, so:
        # - Top of node is nv.y + nv.height
        # - Bottom of node is nv.y
        # Ports are offset by PORT_GAP so they sit outside the node body

        # Input ports at top of node (data flows in from above)
        # Respect 0 inputs for source nodes (e.g., Read)
        num_inputs = len(nv.input_ports) if nv.input_ports else 0
        nv.input_ports = []
        for i in range(num_inputs):
            px = nv.x + (i + 1) * nv.width / (num_inputs + 1)
            py = nv.y + nv.height + self.PORT_GAP  # Above the node
            nv.input_ports.append((px, py))

        # Output ports at bottom of node (data flows out downward)
        # Respect 0 outputs for sink nodes (e.g., Viewer)
        num_outputs = len(nv.output_ports) if nv.output_ports else 0
        nv.output_ports = []
        for i in range(num_outputs):
            px = nv.x + (i + 1) * nv.width / (num_outputs + 1)
            py = nv.y - self.PORT_GAP  # Below the node
            nv.output_ports.append((px, py))

    def _draw_ports(self, state: CanvasState, nv: NodeVisual, rw: float, rh: float):
        """Draw input and output ports for a node."""
        shader = self._get_shader()
        radius = self.PORT_RADIUS * state.zoom

        # Use node's color for ports
        port_color = (*nv.color, 1.0)

        # Draw input ports
        for px, py in nv.input_ports:
            sx, sy = state.canvas_to_screen(px, py, rw, rh)
            self._draw_circle(shader, sx, sy, radius, port_color)

        # Draw output ports
        for px, py in nv.output_ports:
            sx, sy = state.canvas_to_screen(px, py, rw, rh)
            self._draw_circle(shader, sx, sy, radius, port_color)

    def _draw_circle(self, shader, cx: float, cy: float, radius: float,
                     color: Tuple[float, float, float, float], segments: int = 16):
        """Draw a filled circle."""
        verts = [(cx, cy)]  # Center
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            verts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

        indices = [(0, i, i + 1) for i in range(1, segments + 1)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_link(self, state: CanvasState, link: LinkVisual, rw: float, rh: float):
        """Draw a connection between nodes."""
        from_nv = state.node_visuals.get(link.from_node)
        to_nv = state.node_visuals.get(link.to_node)

        if not from_nv or not to_nv:
            return

        # Calculate port positions inline (don't use cached values)
        # Special handling for reroute nodes - ports are centered
        if from_nv.node_type == 'OC_N_reroute':
            center_x = from_nv.x + from_nv.width / 2
            center_y = from_nv.y + from_nv.height / 2
            start_x = center_x
            start_y = center_y - self.PORT_GAP - self.LINK_GAP
        else:
            num_outputs = max(len(from_nv.output_ports), 1)
            start_x = from_nv.x + (link.from_port + 1) * from_nv.width / (num_outputs + 1)
            start_y = from_nv.y - self.PORT_GAP - self.LINK_GAP  # Output below node, with link gap

        if to_nv.node_type == 'OC_N_reroute':
            center_x = to_nv.x + to_nv.width / 2
            center_y = to_nv.y + to_nv.height / 2
            end_x = center_x
            end_y = center_y + self.PORT_GAP + self.LINK_GAP
        else:
            num_inputs = max(len(to_nv.input_ports), 1)
            end_x = to_nv.x + (link.to_port + 1) * to_nv.width / (num_inputs + 1)
            end_y = to_nv.y + to_nv.height + self.PORT_GAP + self.LINK_GAP  # Input above node, with link gap

        # Convert to screen coords
        sx1, sy1 = state.canvas_to_screen(start_x, start_y, rw, rh)
        sx2, sy2 = state.canvas_to_screen(end_x, end_y, rw, rh)

        # Check if either connected node is selected
        is_highlighted = from_nv.selected or to_nv.selected

        if is_highlighted:
            # Brighten the color for highlighted links
            link_color = (
                min(from_nv.color[0] * 1.5 + 0.3, 1.0),
                min(from_nv.color[1] * 1.5 + 0.3, 1.0),
                min(from_nv.color[2] * 1.5 + 0.3, 1.0),
                1.0
            )
            # Draw thicker line for highlighted links
            self._draw_bezier_link(sx1, sy1, sx2, sy2, link_color, line_width=6.0)
        else:
            # Normal link color
            link_color = (*from_nv.color, 1.0)
            self._draw_bezier_link(sx1, sy1, sx2, sy2, link_color)

    def _draw_drag_link(self, state: CanvasState, rw: float, rh: float):
        """Draw the link currently being dragged."""
        from_nv = state.node_visuals.get(state.link_from_node)
        if not from_nv:
            return

        # Calculate port position inline (don't use cached values which may be stale)
        # Special handling for reroute nodes - ports are centered
        if from_nv.node_type == 'OC_N_reroute':
            center_x = from_nv.x + from_nv.width / 2
            center_y = from_nv.y + from_nv.height / 2
            if state.link_is_output:
                start_x = center_x
                start_y = center_y - self.PORT_GAP - self.LINK_GAP
            else:
                start_x = center_x
                start_y = center_y + self.PORT_GAP + self.LINK_GAP
        else:
            # Ports are offset by PORT_GAP from node edges, link starts with additional LINK_GAP
            if state.link_is_output:
                num_ports = max(len(from_nv.output_ports), 1)
                port_idx = state.link_from_port
                start_x = from_nv.x + (port_idx + 1) * from_nv.width / (num_ports + 1)
                start_y = from_nv.y - self.PORT_GAP - self.LINK_GAP  # Output below node, with link gap
            else:
                num_ports = max(len(from_nv.input_ports), 1)
                port_idx = state.link_from_port
                start_x = from_nv.x + (port_idx + 1) * from_nv.width / (num_ports + 1)
                start_y = from_nv.y + from_nv.height + self.PORT_GAP + self.LINK_GAP  # Input above node, with link gap

        sx1, sy1 = state.canvas_to_screen(start_x, start_y, rw, rh)
        # End position is already in screen coords
        sx2, sy2 = state.link_end_x, state.link_end_y

        # Use source node's color for the dragged link
        link_color = (*from_nv.color, 1.0)
        self._draw_bezier_link(sx1, sy1, sx2, sy2, link_color)

    def _draw_pending_link(self, state: CanvasState, rw: float, rh: float):
        """Draw the pending link when Add menu is open after drag-to-empty-space."""
        from_nv = state.node_visuals.get(state.pending_link_node)
        if not from_nv or not state.add_node_location:
            return

        # Calculate port position (same logic as _draw_drag_link)
        # Special handling for reroute nodes - ports are centered
        if from_nv.node_type == 'OC_N_reroute':
            center_x = from_nv.x + from_nv.width / 2
            center_y = from_nv.y + from_nv.height / 2
            if state.pending_link_is_output:
                start_x = center_x
                start_y = center_y - self.PORT_GAP - self.LINK_GAP
            else:
                start_x = center_x
                start_y = center_y + self.PORT_GAP + self.LINK_GAP
        else:
            # Ports are offset by PORT_GAP from node edges, link starts with additional LINK_GAP
            if state.pending_link_is_output:
                num_ports = max(len(from_nv.output_ports), 1)
                port_idx = state.pending_link_port
                start_x = from_nv.x + (port_idx + 1) * from_nv.width / (num_ports + 1)
                start_y = from_nv.y - self.PORT_GAP - self.LINK_GAP  # Output below node, with link gap
            else:
                num_ports = max(len(from_nv.input_ports), 1)
                port_idx = state.pending_link_port
                start_x = from_nv.x + (port_idx + 1) * from_nv.width / (num_ports + 1)
                start_y = from_nv.y + from_nv.height + self.PORT_GAP + self.LINK_GAP  # Input above node, with link gap

        sx1, sy1 = state.canvas_to_screen(start_x, start_y, rw, rh)
        # End position is the add_node_location (in canvas coords)
        end_x, end_y = state.add_node_location
        sx2, sy2 = state.canvas_to_screen(end_x, end_y, rw, rh)

        # Use source node's color for the pending link
        link_color = (*from_nv.color, 1.0)
        self._draw_bezier_link(sx1, sy1, sx2, sy2, link_color)

    def _draw_bezier_link(self, x1: float, y1: float, x2: float, y2: float,
                          color: Tuple[float, float, float, float], segments: int = 48,
                          line_width: float = 4.0):
        """Draw a connection line using the current connection style."""
        style = getattr(self, '_connection_style', 'BEZIER')

        if style == 'STRAIGHT':
            self._draw_straight_link(x1, y1, x2, y2, color, line_width)
        elif style == 'DIRECTIONAL':
            self._draw_directional_bezier(x1, y1, x2, y2, color, segments, line_width)
        elif style == 'STEP':
            self._draw_step_link(x1, y1, x2, y2, color, line_width)
        elif style == 'SMOOTH_STEP':
            self._draw_smooth_step_link(x1, y1, x2, y2, color, segments, line_width)
        else:  # BEZIER (default)
            self._draw_classic_bezier(x1, y1, x2, y2, color, segments, line_width)

    def _draw_straight_link(self, x1: float, y1: float, x2: float, y2: float,
                            color: Tuple[float, float, float, float], line_width: float):
        """Draw a straight line."""
        shader = self._get_shader()
        gpu.state.line_width_set(line_width)

        batch = batch_for_shader(shader, 'LINES', {"pos": [(x1, y1), (x2, y2)]})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        gpu.state.line_width_set(1.0)

    def _draw_classic_bezier(self, x1: float, y1: float, x2: float, y2: float,
                             color: Tuple[float, float, float, float],
                             segments: int, line_width: float):
        """Draw classic Nuke-style vertical bezier."""
        shader = self._get_shader()

        # Vertical offset for control points
        dy = y2 - y1
        offset = max(60, abs(dy) * 0.5)
        offset = min(offset, 250)

        # Control points extend vertically (Nuke style)
        cp1 = (x1, y1 - offset)  # Down from start
        cp2 = (x2, y2 + offset)  # Up from end

        points = self._bezier_points(x1, y1, cp1[0], cp1[1], cp2[0], cp2[1], x2, y2, segments)

        gpu.state.line_width_set(line_width)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _draw_directional_bezier(self, x1: float, y1: float, x2: float, y2: float,
                                  color: Tuple[float, float, float, float],
                                  segments: int, line_width: float):
        """Draw bezier that follows connection direction."""
        shader = self._get_shader()

        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 1:
            return

        nx, ny = dx / dist, dy / dist
        cp_dist = min(max(60, dist * 0.4), 250)

        cp1 = (x1 + nx * cp_dist, y1 + ny * cp_dist)
        cp2 = (x2 - nx * cp_dist, y2 - ny * cp_dist)

        points = self._bezier_points(x1, y1, cp1[0], cp1[1], cp2[0], cp2[1], x2, y2, segments)

        gpu.state.line_width_set(line_width)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _draw_step_link(self, x1: float, y1: float, x2: float, y2: float,
                        color: Tuple[float, float, float, float], line_width: float):
        """Draw right-angle orthogonal lines (circuit diagram style)."""
        shader = self._get_shader()

        # Midpoint Y for the horizontal segment
        mid_y = (y1 + y2) / 2

        points = [
            (x1, y1),
            (x1, mid_y),
            (x2, mid_y),
            (x2, y2),
        ]

        gpu.state.line_width_set(line_width)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _draw_smooth_step_link(self, x1: float, y1: float, x2: float, y2: float,
                                color: Tuple[float, float, float, float],
                                segments: int, line_width: float):
        """Draw right-angle lines with rounded corners."""
        shader = self._get_shader()

        mid_y = (y1 + y2) / 2
        corner_radius = min(25, abs(y2 - y1) / 4, abs(x2 - x1) / 2 if x2 != x1 else 25)

        points = []

        # Start point
        points.append((x1, y1))

        # First corner (x1, mid_y) - rounded
        if corner_radius > 2:
            # Arc from vertical to horizontal
            corner1_center_y = mid_y + corner_radius if y1 > mid_y else mid_y - corner_radius
            dir_x = 1 if x2 > x1 else -1

            for i in range(segments // 4 + 1):
                t = i / (segments // 4)
                if y1 > mid_y:
                    # Coming from above
                    angle = math.pi / 2 + t * (math.pi / 2) * (-dir_x)
                else:
                    # Coming from below
                    angle = -math.pi / 2 + t * (math.pi / 2) * dir_x

                px = x1 + dir_x * corner_radius * (1 - math.cos(t * math.pi / 2))
                py = mid_y + (y1 - mid_y) * (1 - t) if abs(y1 - mid_y) > corner_radius else corner1_center_y + corner_radius * math.sin(angle)
                points.append((px, py))
        else:
            points.append((x1, mid_y))

        # Horizontal segment
        points.append((x2 - (corner_radius if x2 > x1 else -corner_radius) if corner_radius > 2 else x2, mid_y))

        # Second corner (x2, mid_y) - rounded
        if corner_radius > 2:
            dir_x = 1 if x2 > x1 else -1

            for i in range(segments // 4 + 1):
                t = i / (segments // 4)
                px = x2 - dir_x * corner_radius * (1 - t)
                py = mid_y + (y2 - mid_y) * t
                points.append((px, py))
        else:
            points.append((x2, mid_y))

        # End point
        points.append((x2, y2))

        gpu.state.line_width_set(line_width)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _bezier_points(self, x1: float, y1: float, cx1: float, cy1: float,
                       cx2: float, cy2: float, x2: float, y2: float,
                       segments: int) -> List[Tuple[float, float]]:
        """Generate points along a cubic bezier curve."""
        points = []
        for i in range(segments + 1):
            t = i / segments
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            t2 = t * t
            t3 = t2 * t

            x = mt3 * x1 + 3 * mt2 * t * cx1 + 3 * mt * t2 * cx2 + t3 * x2
            y = mt3 * y1 + 3 * mt2 * t * cy1 + 3 * mt * t2 * cy2 + t3 * y2
            points.append((x, y))
        return points

    def _draw_box_selection(self, state: CanvasState, rw: float, rh: float):
        """Draw the box selection rectangle."""
        shader = self._get_shader()

        x1, y1 = state.drag_start_x, state.drag_start_y
        x2, y2 = state.drag_current_x, state.drag_current_y

        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        # Fill
        verts = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
        indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", self.COLOR_BOX_SELECT)
        batch.draw(shader)

        # Border
        border_verts = [(min_x, min_y), (max_x, min_y), (max_x, max_y),
                        (min_x, max_y), (min_x, min_y)]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
        shader.bind()
        shader.uniform_float("color", self.COLOR_BOX_SELECT_BORDER)
        batch.draw(shader)

    def _draw_drag_cut_line(self, state: CanvasState):
        """Draw the drag cut line as dashed hot pink."""
        if not state.is_drag_cutting:
            return

        shader = self._get_shader()

        x1, y1 = state.drag_cut_start_x, state.drag_cut_start_y
        x2, y2 = state.drag_cut_end_x, state.drag_cut_end_y

        # Hot pink color
        color = (1.0, 0.1, 0.5, 1.0)

        # Calculate line direction and length
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1:
            return

        # Normalize direction
        nx = dx / length
        ny = dy / length

        # Dashed line parameters
        dash_length = 12
        gap_length = 8
        segment_length = dash_length + gap_length

        # Set line width
        gpu.state.line_width_set(3.0)

        # Draw dashes
        current_pos = 0
        while current_pos < length:
            dash_start = current_pos
            dash_end = min(current_pos + dash_length, length)

            sx = x1 + nx * dash_start
            sy = y1 + ny * dash_start
            ex = x1 + nx * dash_end
            ey = y1 + ny * dash_end

            batch = batch_for_shader(shader, 'LINES', {"pos": [(sx, sy), (ex, ey)]})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)

            current_pos += segment_length

        # Reset line width
        gpu.state.line_width_set(1.0)

    def _draw_reroute_node(self, state: CanvasState, nv: NodeVisual, rw: float, rh: float):
        """Draw a reroute node as a simple circle/dot."""
        shader = self._get_shader()

        # Reroute is just a dot at the center of its bounding box
        # Calculate center position
        center_x = nv.x + nv.width / 2
        center_y = nv.y + nv.height / 2
        sx, sy = state.canvas_to_screen(center_x, center_y, rw, rh)

        # Circle radius (scaled with zoom)
        radius = 10 * state.zoom

        # Node color
        node_color = (*nv.color, 1.0)

        # Draw filled circle
        self._draw_circle(shader, sx, sy, radius, node_color)

        # Draw selection ring if selected
        if nv.selected:
            sel_color = (
                min(nv.color[0] * 1.5 + 0.2, 1.0),
                min(nv.color[1] * 1.5 + 0.2, 1.0),
                min(nv.color[2] * 1.5 + 0.2, 1.0),
                1.0
            )
            # Draw outer ring for selection
            gpu.state.line_width_set(2.0)
            self._draw_circle_outline(shader, sx, sy, radius + 4 * state.zoom, sel_color)
            gpu.state.line_width_set(1.0)

        # Update port positions for the reroute (centered on the node)
        # Input port at top, output port at bottom
        nv.input_ports = [(center_x, center_y + self.PORT_GAP)]
        nv.output_ports = [(center_x, center_y - self.PORT_GAP)]

        # Draw ports using the same method as regular nodes
        self._draw_ports(state, nv, rw, rh)

    def _draw_circle_outline(self, shader, cx: float, cy: float, radius: float,
                             color: Tuple[float, float, float, float], segments: int = 24):
        """Draw a circle outline."""
        points = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
