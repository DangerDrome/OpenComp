"""OpenComp Node Canvas — Canvas state management.

Tracks pan, zoom, selection, and interaction state for the node graph.
"""

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple, List
import math


@dataclass
class NodeVisual:
    """Visual representation of a node in the canvas."""
    node_name: str  # Reference to bpy node by name
    x: float = 0.0
    y: float = 0.0
    width: float = 140.0
    height: float = 80.0
    color: Tuple[float, float, float] = (0.3, 0.3, 0.3)
    selected: bool = False

    # Computed port positions (updated by renderer)
    input_ports: List[Tuple[float, float]] = field(default_factory=list)
    output_ports: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class LinkVisual:
    """Visual representation of a connection."""
    from_node: str
    from_port: int
    to_node: str
    to_port: int


class CanvasState:
    """Manages the state of the node canvas."""

    def __init__(self):
        # View transform
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.zoom: float = 1.0

        # Selection
        self.selected_nodes: Set[str] = set()
        self.active_node: Optional[str] = None

        # Interaction state
        self.is_panning: bool = False
        self.is_dragging_nodes: bool = False
        self.is_box_selecting: bool = False
        self.is_linking: bool = False

        # Drag state
        self.drag_start_x: float = 0.0
        self.drag_start_y: float = 0.0
        self.drag_current_x: float = 0.0
        self.drag_current_y: float = 0.0

        # Link drag state
        self.link_from_node: Optional[str] = None
        self.link_from_port: int = -1
        self.link_is_output: bool = True
        self.link_end_x: float = 0.0
        self.link_end_y: float = 0.0

        # Node visuals cache (synced from bpy nodes)
        self.node_visuals: dict[str, NodeVisual] = {}

        # Draw handler reference
        self._draw_handler = None

    def screen_to_canvas(self, sx: float, sy: float,
                         region_width: float, region_height: float) -> Tuple[float, float]:
        """Convert screen coordinates to canvas coordinates."""
        # Center of region is (0, 0) in canvas space
        cx = (sx - region_width / 2) / self.zoom - self.pan_x
        cy = (sy - region_height / 2) / self.zoom - self.pan_y
        return cx, cy

    def canvas_to_screen(self, cx: float, cy: float,
                         region_width: float, region_height: float) -> Tuple[float, float]:
        """Convert canvas coordinates to screen coordinates."""
        sx = (cx + self.pan_x) * self.zoom + region_width / 2
        sy = (cy + self.pan_y) * self.zoom + region_height / 2
        return sx, sy

    def zoom_at(self, factor: float, screen_x: float, screen_y: float,
                region_width: float, region_height: float):
        """Zoom centered on a screen position."""
        # Get canvas position before zoom
        cx, cy = self.screen_to_canvas(screen_x, screen_y, region_width, region_height)

        # Apply zoom
        old_zoom = self.zoom
        self.zoom = max(0.1, min(4.0, self.zoom * factor))

        # Adjust pan to keep the point under cursor stationary
        if self.zoom != old_zoom:
            # Get new screen position of the same canvas point
            new_sx, new_sy = self.canvas_to_screen(cx, cy, region_width, region_height)

            # Adjust pan to compensate
            self.pan_x += (screen_x - new_sx) / self.zoom
            self.pan_y += (screen_y - new_sy) / self.zoom

    def frame_all(self, region_width: float, region_height: float):
        """Frame all nodes in view."""
        if not self.node_visuals:
            self.pan_x = 0
            self.pan_y = 0
            self.zoom = 1.0
            return

        # Find bounding box
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        for nv in self.node_visuals.values():
            min_x = min(min_x, nv.x)
            min_y = min(min_y, nv.y - nv.height)
            max_x = max(max_x, nv.x + nv.width)
            max_y = max(max_y, nv.y)

        if min_x == float('inf'):
            return

        # Add padding
        padding = 50
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding

        # Calculate zoom to fit
        bbox_width = max_x - min_x
        bbox_height = max_y - min_y

        zoom_x = region_width / bbox_width if bbox_width > 0 else 1.0
        zoom_y = region_height / bbox_height if bbox_height > 0 else 1.0
        self.zoom = min(zoom_x, zoom_y, 2.0)  # Cap at 2x

        # Center on bounding box
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        self.pan_x = -center_x
        self.pan_y = -center_y

    def hit_test_node(self, cx: float, cy: float) -> Optional[str]:
        """Find node at canvas coordinates. Returns node name or None."""
        # Check in reverse order (top-most first)
        for name, nv in reversed(list(self.node_visuals.items())):
            if (nv.x <= cx <= nv.x + nv.width and
                nv.y - nv.height <= cy <= nv.y):
                return name
        return None

    def hit_test_port(self, cx: float, cy: float,
                      radius: float = 8.0) -> Optional[Tuple[str, int, bool]]:
        """Find port at canvas coordinates. Returns (node_name, port_index, is_output) or None."""
        for name, nv in self.node_visuals.items():
            # Check output ports (bottom of node in top-to-bottom flow)
            for i, (px, py) in enumerate(nv.output_ports):
                if math.hypot(cx - px, cy - py) <= radius:
                    return (name, i, True)

            # Check input ports (top of node)
            for i, (px, py) in enumerate(nv.input_ports):
                if math.hypot(cx - px, cy - py) <= radius:
                    return (name, i, False)

        return None

    def select_node(self, node_name: str, extend: bool = False):
        """Select a node."""
        if not extend:
            self.selected_nodes.clear()
        self.selected_nodes.add(node_name)
        self.active_node = node_name

        # Update visuals
        for name, nv in self.node_visuals.items():
            nv.selected = name in self.selected_nodes

    def deselect_all(self):
        """Deselect all nodes."""
        self.selected_nodes.clear()
        self.active_node = None
        for nv in self.node_visuals.values():
            nv.selected = False

    def box_select(self, x1: float, y1: float, x2: float, y2: float, extend: bool = False):
        """Select nodes within a box (canvas coordinates)."""
        if not extend:
            self.selected_nodes.clear()

        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)

        for name, nv in self.node_visuals.items():
            # Check if node intersects box
            if (nv.x + nv.width >= min_x and nv.x <= max_x and
                nv.y >= min_y and nv.y - nv.height <= max_y):
                self.selected_nodes.add(name)

        # Update visuals
        for name, nv in self.node_visuals.items():
            nv.selected = name in self.selected_nodes


# Global canvas state (one per Blender session for now)
_canvas_state: Optional[CanvasState] = None


def get_canvas_state() -> CanvasState:
    """Get or create the global canvas state."""
    global _canvas_state
    if _canvas_state is None:
        _canvas_state = CanvasState()
    return _canvas_state
