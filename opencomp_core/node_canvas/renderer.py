"""OpenComp Node Canvas — GPU renderer.

Draws the node graph using Blender's GPU module.
Supports nodes, connections, ports, selection, and grid.
"""

import gpu
from gpu_extras.batch import batch_for_shader
import blf
import math
from typing import List, Tuple, Optional

from .state import CanvasState, NodeVisual, LinkVisual


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
    COLOR_NODE_HEADER = (0.4, 0.25, 0.1, 1.0)
    COLOR_NODE_SELECTED = (0.9, 0.5, 0.1, 1.0)
    COLOR_NODE_BORDER = (0.1, 0.1, 0.1, 1.0)
    COLOR_PORT_INPUT = (0.3, 0.6, 0.3, 1.0)
    COLOR_PORT_OUTPUT = (0.6, 0.3, 0.3, 1.0)
    COLOR_LINK = (0.8, 0.8, 0.8, 1.0)
    COLOR_LINK_DRAG = (1.0, 0.7, 0.2, 1.0)
    COLOR_BOX_SELECT = (0.3, 0.5, 0.8, 0.3)
    COLOR_BOX_SELECT_BORDER = (0.4, 0.6, 0.9, 1.0)
    COLOR_TEXT = (0.9, 0.9, 0.9, 1.0)

    # Dimensions
    NODE_HEADER_HEIGHT = 24
    PORT_RADIUS = 6
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

    def _draw_background(self, rw: float, rh: float):
        """Draw solid background to completely cover Blender's node editor."""
        shader = self._get_shader()
        verts = [(0, 0), (rw, 0), (rw, rh), (0, rh)]
        indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", self.COLOR_BG)
        batch.draw(shader)

    def draw(self, state: CanvasState, region_width: float, region_height: float,
             links: List[LinkVisual] = None):
        """Draw the entire canvas."""
        gpu.state.blend_set('ALPHA')

        # Draw solid background to completely hide Blender's node editor
        self._draw_background(region_width, region_height)

        # Draw grid
        self._draw_grid(state, region_width, region_height)

        # Draw links
        if links:
            for link in links:
                self._draw_link(state, link, region_width, region_height)

        # Draw link being dragged
        if state.is_linking and state.link_from_node:
            self._draw_drag_link(state, region_width, region_height)

        # Draw nodes
        for name, nv in state.node_visuals.items():
            self._draw_node(state, nv, region_width, region_height)

        # Draw box selection
        if state.is_box_selecting:
            self._draw_box_selection(state, region_width, region_height)

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
        """Draw a single node."""
        shader = self._get_shader()

        # Convert node corners to screen coords
        # In canvas space: y=0 is top, y decreases downward
        # Node is positioned at (nv.x, nv.y) with nv.y being TOP of node
        x1, y1 = state.canvas_to_screen(nv.x, nv.y, rw, rh)
        x2, y2 = state.canvas_to_screen(nv.x + nv.width, nv.y - nv.height, rw, rh)

        # Ensure correct ordering (screen Y increases upward in Blender)
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        # Node body
        body_verts = [
            (min_x, min_y), (max_x, min_y),
            (max_x, max_y), (min_x, max_y)
        ]
        body_indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": body_verts}, indices=body_indices)
        shader.bind()
        shader.uniform_float("color", self.COLOR_NODE_BG)
        batch.draw(shader)

        # Header (top portion)
        header_screen_height = self.NODE_HEADER_HEIGHT * state.zoom
        header_verts = [
            (min_x, max_y - header_screen_height), (max_x, max_y - header_screen_height),
            (max_x, max_y), (min_x, max_y)
        ]
        batch = batch_for_shader(shader, 'TRIS', {"pos": header_verts}, indices=body_indices)
        shader.bind()
        color = self.COLOR_NODE_SELECTED if nv.selected else self.COLOR_NODE_HEADER
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Border
        border_verts = [
            (min_x, min_y), (max_x, min_y),
            (max_x, max_y), (min_x, max_y),
            (min_x, min_y)
        ]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
        shader.bind()
        border_color = self.COLOR_NODE_SELECTED if nv.selected else self.COLOR_NODE_BORDER
        shader.uniform_float("color", border_color)
        batch.draw(shader)

        # Node name text
        blf.size(self._font_id, int(12 * state.zoom))
        blf.color(self._font_id, *self.COLOR_TEXT)
        text_x = min_x + 8 * state.zoom
        text_y = max_y - 16 * state.zoom
        blf.position(self._font_id, text_x, text_y, 0)
        blf.draw(self._font_id, nv.node_name)

        # Calculate and draw ports
        self._update_port_positions(state, nv, rw, rh)
        self._draw_ports(state, nv, rw, rh)

    def _update_port_positions(self, state: CanvasState, nv: NodeVisual,
                               rw: float, rh: float):
        """Update port positions for a node (canvas coordinates)."""
        # Input ports at top of node
        num_inputs = len(nv.input_ports) if nv.input_ports else 1
        nv.input_ports = []
        for i in range(num_inputs):
            px = nv.x + (i + 1) * nv.width / (num_inputs + 1)
            py = nv.y  # Top of node
            nv.input_ports.append((px, py))

        # Output ports at bottom of node
        num_outputs = len(nv.output_ports) if nv.output_ports else 1
        nv.output_ports = []
        for i in range(num_outputs):
            px = nv.x + (i + 1) * nv.width / (num_outputs + 1)
            py = nv.y - nv.height  # Bottom of node
            nv.output_ports.append((px, py))

    def _draw_ports(self, state: CanvasState, nv: NodeVisual, rw: float, rh: float):
        """Draw input and output ports for a node."""
        shader = self._get_shader()
        radius = self.PORT_RADIUS * state.zoom

        # Draw input ports (green)
        for px, py in nv.input_ports:
            sx, sy = state.canvas_to_screen(px, py, rw, rh)
            self._draw_circle(shader, sx, sy, radius, self.COLOR_PORT_INPUT)

        # Draw output ports (red)
        for px, py in nv.output_ports:
            sx, sy = state.canvas_to_screen(px, py, rw, rh)
            self._draw_circle(shader, sx, sy, radius, self.COLOR_PORT_OUTPUT)

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

        # Get port positions
        if link.from_port < len(from_nv.output_ports):
            start_x, start_y = from_nv.output_ports[link.from_port]
        else:
            return

        if link.to_port < len(to_nv.input_ports):
            end_x, end_y = to_nv.input_ports[link.to_port]
        else:
            return

        # Convert to screen coords
        sx1, sy1 = state.canvas_to_screen(start_x, start_y, rw, rh)
        sx2, sy2 = state.canvas_to_screen(end_x, end_y, rw, rh)

        self._draw_bezier_link(sx1, sy1, sx2, sy2, self.COLOR_LINK)

    def _draw_drag_link(self, state: CanvasState, rw: float, rh: float):
        """Draw the link currently being dragged."""
        from_nv = state.node_visuals.get(state.link_from_node)
        if not from_nv:
            return

        if state.link_is_output:
            if state.link_from_port < len(from_nv.output_ports):
                start_x, start_y = from_nv.output_ports[state.link_from_port]
            else:
                return
        else:
            if state.link_from_port < len(from_nv.input_ports):
                start_x, start_y = from_nv.input_ports[state.link_from_port]
            else:
                return

        sx1, sy1 = state.canvas_to_screen(start_x, start_y, rw, rh)
        # End position is already in screen coords
        sx2, sy2 = state.link_end_x, state.link_end_y

        self._draw_bezier_link(sx1, sy1, sx2, sy2, self.COLOR_LINK_DRAG)

    def _draw_bezier_link(self, x1: float, y1: float, x2: float, y2: float,
                          color: Tuple[float, float, float, float], segments: int = 32):
        """Draw a bezier curve link (vertical flow - control points offset vertically)."""
        shader = self._get_shader()

        # Control points for vertical bezier (Nuke style)
        # Offset control points in Y direction
        offset = abs(y2 - y1) * 0.5
        if offset < 50:
            offset = 50

        # For top-to-bottom flow: output is at bottom, input is at top
        # So y1 (output/start) should have control point going down
        # and y2 (input/end) should have control point going up
        cp1 = (x1, y1 - offset)  # Down from start
        cp2 = (x2, y2 + offset)  # Up from end

        # Generate bezier points
        points = []
        for i in range(segments + 1):
            t = i / segments
            t2 = t * t
            t3 = t2 * t
            mt = 1 - t
            mt2 = mt * mt
            mt3 = mt2 * mt

            x = mt3 * x1 + 3 * mt2 * t * cp1[0] + 3 * mt * t2 * cp2[0] + t3 * x2
            y = mt3 * y1 + 3 * mt2 * t * cp1[1] + 3 * mt * t2 * cp2[1] + t3 * y2
            points.append((x, y))

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

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
