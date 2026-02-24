"""OpenComp Node Canvas — Canvas state management.

Tracks pan, zoom, selection, and interaction state for the node graph.
"""

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple, List
import math

# Port positioning constant (must match renderer.py)
PORT_GAP = 14  # Gap between port center and node edge


@dataclass
class NodeVisual:
    """Visual representation of a node in the canvas."""
    node_name: str  # Reference to bpy node by name
    x: float = 0.0
    y: float = 0.0
    width: float = 140.0
    height: float = 32.0  # Default to collapsed height (matches NODE_HEADER_HEIGHT)
    color: Tuple[float, float, float] = (0.3, 0.3, 0.3)
    selected: bool = False
    collapsed: bool = True  # Nodes start collapsed by default
    label: str = ""  # Node type label (e.g., "Read", "Grade")
    node_type: str = ""  # Node bl_idname for icon lookup

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

        # Add node state - position for newly added nodes
        self.add_node_location: Optional[Tuple[float, float]] = None
        self._known_nodes: Set[str] = set()  # Track known node names

        # Pending link state - for auto-connecting after drag-to-empty-space
        self.pending_link_node: Optional[str] = None
        self.pending_link_port: int = -1
        self.pending_link_is_output: bool = True

        # Node visuals cache (synced from bpy nodes)
        self.node_visuals: dict[str, NodeVisual] = {}

        # Drag cut state (X or Y key + drag to cut links)
        self.is_drag_cutting: bool = False
        self.drag_cut_start_x: float = 0.0
        self.drag_cut_start_y: float = 0.0
        self.drag_cut_end_x: float = 0.0
        self.drag_cut_end_y: float = 0.0

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
        # nv.y is bottom-left, so node spans y: [nv.y, nv.y + height]
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        for nv in self.node_visuals.values():
            min_x = min(min_x, nv.x)
            min_y = min(min_y, nv.y)
            max_x = max(max_x, nv.x + nv.width)
            max_y = max(max_y, nv.y + nv.height)

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
        # In Blender, node.location is bottom-left, so node spans:
        # x: [nv.x, nv.x + width]
        # y: [nv.y, nv.y + height] (Y increases upward)
        for name, nv in reversed(list(self.node_visuals.items())):
            # Special handling for reroute nodes - use circular hit test
            if nv.node_type == 'OC_N_reroute':
                center_x = nv.x + nv.width / 2
                center_y = nv.y + nv.height / 2
                # Use radius of 18 (slightly larger than visual 10) for easier clicking
                if math.hypot(cx - center_x, cy - center_y) <= 18:
                    return name
            elif (nv.x <= cx <= nv.x + nv.width and
                  nv.y <= cy <= nv.y + nv.height):
                return name
        return None

    def hit_test_port(self, cx: float, cy: float,
                      radius: float = 18.0) -> Optional[Tuple[str, int, bool]]:
        """Find port at canvas coordinates. Returns (node_name, port_index, is_output) or None."""
        for name, nv in self.node_visuals.items():
            # Special handling for reroute nodes - ports are centered
            if nv.node_type == 'OC_N_reroute':
                center_x = nv.x + nv.width / 2
                center_y = nv.y + nv.height / 2
                # Output port below center
                if math.hypot(cx - center_x, cy - (center_y - PORT_GAP)) <= radius:
                    return (name, 0, True)
                # Input port above center
                if math.hypot(cx - center_x, cy - (center_y + PORT_GAP)) <= radius:
                    return (name, 0, False)
                continue

            # Calculate port positions inline (they may not be updated yet)
            # nv.y is bottom-left, so top = nv.y + height, bottom = nv.y
            # Ports are offset by PORT_GAP from node edges
            # Respect actual port counts (don't force minimum of 1)
            num_inputs = len(nv.input_ports)
            num_outputs = len(nv.output_ports)

            # Check output ports (below node with gap)
            if num_outputs > 0:
                for i in range(num_outputs):
                    px = nv.x + (i + 1) * nv.width / (num_outputs + 1)
                    py = nv.y - PORT_GAP  # Below node
                    if math.hypot(cx - px, cy - py) <= radius:
                        return (name, i, True)

            # Check input ports (above node with gap)
            if num_inputs > 0:
                for i in range(num_inputs):
                    px = nv.x + (i + 1) * nv.width / (num_inputs + 1)
                    py = nv.y + nv.height + PORT_GAP  # Above node
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
            # Node spans x: [nv.x, nv.x + width], y: [nv.y, nv.y + height]
            if (nv.x + nv.width >= min_x and nv.x <= max_x and
                nv.y + nv.height >= min_y and nv.y <= max_y):
                self.selected_nodes.add(name)

        # Update visuals
        for name, nv in self.node_visuals.items():
            nv.selected = name in self.selected_nodes


# Node type to color mapping (Nuke-style)
NODE_COLORS = {
    # Input nodes - green tint
    'OC_N_read': (0.2, 0.4, 0.25),
    'OC_N_constant': (0.2, 0.35, 0.25),
    # Output nodes - purple tint
    'OC_N_write': (0.35, 0.2, 0.4),
    'OC_N_viewer': (0.3, 0.2, 0.35),
    # Color nodes - orange/warm tint
    'OC_N_grade': (0.4, 0.3, 0.2),
    'OC_N_cdl': (0.4, 0.28, 0.2),
    # Merge nodes - blue tint
    'OC_N_over': (0.2, 0.3, 0.4),
    'OC_N_merge': (0.2, 0.28, 0.38),
    'OC_N_shuffle': (0.25, 0.3, 0.4),
    # Filter nodes - cyan tint
    'OC_N_blur': (0.2, 0.35, 0.4),
    'OC_N_sharpen': (0.2, 0.38, 0.4),
    # Transform nodes - yellow tint
    'OC_N_transform': (0.4, 0.38, 0.2),
    'OC_N_crop': (0.38, 0.35, 0.2),
    # Utility nodes - neutral gray
    'OC_N_reroute': (0.35, 0.35, 0.35),
}
DEFAULT_NODE_COLOR = (0.3, 0.3, 0.3)


def sync_from_tree(state: 'CanvasState', tree) -> List[LinkVisual]:
    """Sync canvas state from a Blender node tree.

    Args:
        state: The canvas state to update
        tree: A bpy.types.NodeTree (OC_NT_compositor)

    Returns:
        List of LinkVisual for all connections
    """
    if tree is None:
        state.node_visuals.clear()
        state._known_nodes.clear()
        return []

    # Track which nodes still exist
    existing_names = set()

    # Detect new nodes and reposition them if we have an add_node_location
    current_node_names = {node.name for node in tree.nodes}
    new_nodes = current_node_names - state._known_nodes

    if new_nodes and state.add_node_location:
        for node in tree.nodes:
            if node.name in new_nodes:
                # Position new node at the stored cursor location
                node.location.x = state.add_node_location[0]
                node.location.y = state.add_node_location[1]
        # Clear the add location after using it
        state.add_node_location = None

    # Update known nodes
    state._known_nodes = current_node_names

    for node in tree.nodes:
        existing_names.add(node.name)

        # Get or create visual for this node
        if node.name in state.node_visuals:
            nv = state.node_visuals[node.name]
        else:
            nv = NodeVisual(node_name=node.name)
            state.node_visuals[node.name] = nv

        # Sync position - use Blender's coordinates directly
        # node.location is the top-left corner of the node
        # No Y flip needed - we use Blender's coordinate system
        nv.x = node.location.x
        nv.y = node.location.y

        # Sync dimensions and collapsed state
        nv.width = max(node.width, 140)
        nv.collapsed = getattr(node, 'hide', True)  # Blender's node.hide = collapsed
        if nv.collapsed:
            nv.height = 32  # Just the header (matches NODE_HEADER_HEIGHT)
        else:
            nv.height = max(node.height, 80) if hasattr(node, 'height') else 80

        # Sync color based on node type
        nv.color = NODE_COLORS.get(node.bl_idname, DEFAULT_NODE_COLOR)

        # Sync label from node's editable label property (only show if user set one)
        nv.label = getattr(node, 'label', '')

        # Sync node type for icon lookup
        nv.node_type = node.bl_idname

        # Sync selection
        nv.selected = node.select

        # Count inputs/outputs for port rendering (respect 0 for nodes without ports)
        num_inputs = len([s for s in node.inputs if s.enabled])
        num_outputs = len([s for s in node.outputs if s.enabled])
        nv.input_ports = [(0, 0)] * num_inputs
        nv.output_ports = [(0, 0)] * num_outputs

    # Remove visuals for deleted nodes
    for name in list(state.node_visuals.keys()):
        if name not in existing_names:
            del state.node_visuals[name]

    # Update active node
    if tree.nodes.active:
        state.active_node = tree.nodes.active.name
    else:
        state.active_node = None

    # Sync selected_nodes set
    state.selected_nodes = {name for name in existing_names
                           if state.node_visuals.get(name, NodeVisual("")).selected}

    # Build link visuals from actual connections
    links = []
    for node in tree.nodes:
        for out_idx, output in enumerate(node.outputs):
            if not output.enabled:
                continue
            for link in output.links:
                if link.to_node and link.to_socket:
                    # Find input index
                    to_idx = 0
                    for i, inp in enumerate(link.to_node.inputs):
                        if inp == link.to_socket:
                            to_idx = i
                            break
                    links.append(LinkVisual(
                        from_node=node.name,
                        from_port=out_idx,
                        to_node=link.to_node.name,
                        to_port=to_idx
                    ))

    return links


def write_node_positions_to_tree(state: 'CanvasState', tree):
    """Write node positions from canvas state back to Blender node tree.

    Args:
        state: The canvas state with updated positions
        tree: A bpy.types.NodeTree (OC_NT_compositor)
    """
    if tree is None:
        return

    for node in tree.nodes:
        if node.name in state.node_visuals:
            nv = state.node_visuals[node.name]
            # Direct mapping - no coordinate conversion needed
            node.location.x = nv.x
            node.location.y = nv.y


def write_selection_to_tree(state: 'CanvasState', tree):
    """Write selection state from canvas back to Blender node tree.

    Args:
        state: The canvas state with selection info
        tree: A bpy.types.NodeTree (OC_NT_compositor)
    """
    if tree is None:
        return

    for node in tree.nodes:
        node.select = node.name in state.selected_nodes
        if node.name == state.active_node:
            tree.nodes.active = node


# Global canvas state (one per Blender session for now)
_canvas_state: Optional[CanvasState] = None


def get_canvas_state() -> CanvasState:
    """Get or create the global canvas state."""
    global _canvas_state
    if _canvas_state is None:
        _canvas_state = CanvasState()
    return _canvas_state
