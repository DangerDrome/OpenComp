"""OpenComp Qt Canvas — Node type definitions.

Registers all OpenComp node types for the NodeGraphQt canvas.
Each node matches its corresponding Blender node type.
"""

import uuid
from NodeGraphQt import BaseNode


# Node category colors (RGB 0-1 for node.set_color)
NODE_COLORS = {
    'io':        (0.2, 0.4, 0.7),    # blue
    'color':     (0.7, 0.4, 0.1),    # orange
    'merge':     (0.2, 0.6, 0.3),    # green
    'filter':    (0.5, 0.2, 0.7),    # purple
    'transform': (0.1, 0.5, 0.6),    # teal
    'viewer':    (0.7, 0.15, 0.15),  # red
}

# Convert 0-1 to 0-255 for NodeGraphQt
def _color_255(color):
    return tuple(int(c * 255) for c in color)


class OpenCompBaseNode(BaseNode):
    """Base class for all OpenComp nodes.

    Adds OpenComp-specific functionality:
    - Unique oc_id for IPC identification
    - Thumbnail placeholder
    - Category color
    """

    # Subclasses must set these
    __identifier__ = 'opencomp'
    NODE_NAME = 'Base'
    CATEGORY = 'io'

    def __init__(self):
        super().__init__()

        # Store our own UUID for IPC (NodeGraphQt's ID changes on session restore)
        self._oc_id = str(uuid.uuid4())

        # Apply category color
        if self.CATEGORY in NODE_COLORS:
            r, g, b = _color_255(NODE_COLORS[self.CATEGORY])
            self.set_color(r, g, b)

    def get_oc_id(self):
        """Get the OpenComp unique ID for this node."""
        return getattr(self, '_oc_id', None)

    def set_oc_id(self, oc_id):
        """Set the OpenComp unique ID for this node."""
        self._oc_id = oc_id


# ── I/O Nodes ──────────────────────────────────────────────────────────────


class ReadNode(OpenCompBaseNode):
    """Read image from disk."""

    __identifier__ = 'opencomp.io'
    NODE_NAME = 'Read'
    CATEGORY = 'io'

    def __init__(self):
        super().__init__()

        # Inputs (none for Read)

        # Outputs
        self.add_output('Image')

        # Properties
        self.add_text_input('file_path', 'File Path', text='')


class WriteNode(OpenCompBaseNode):
    """Write image to disk."""

    __identifier__ = 'opencomp.io'
    NODE_NAME = 'Write'
    CATEGORY = 'io'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs (none for Write)

        # Properties
        self.add_text_input('file_path', 'File Path', text='')


class ConstantNode(OpenCompBaseNode):
    """Generate a constant color."""

    __identifier__ = 'opencomp.io'
    NODE_NAME = 'Constant'
    CATEGORY = 'io'

    def __init__(self):
        super().__init__()

        # Outputs
        self.add_output('Image')


# ── Color Nodes ────────────────────────────────────────────────────────────


class GradeNode(OpenCompBaseNode):
    """Primary color grading — lift/gamma/gain."""

    __identifier__ = 'opencomp.color'
    NODE_NAME = 'Grade'
    CATEGORY = 'color'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


class CDLNode(OpenCompBaseNode):
    """ASC CDL color correction."""

    __identifier__ = 'opencomp.color'
    NODE_NAME = 'CDL'
    CATEGORY = 'color'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


class ShuffleNode(OpenCompBaseNode):
    """Channel shuffling and reordering."""

    __identifier__ = 'opencomp.color'
    NODE_NAME = 'Shuffle'
    CATEGORY = 'color'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')
        self.add_input('Image2')

        # Outputs
        self.add_output('Image')


# ── Merge Nodes ────────────────────────────────────────────────────────────


class OverNode(OpenCompBaseNode):
    """Over composite (A over B)."""

    __identifier__ = 'opencomp.merge'
    NODE_NAME = 'Over'
    CATEGORY = 'merge'

    def __init__(self):
        super().__init__()

        # Inputs (B at top, A below — Nuke convention)
        self.add_input('B')
        self.add_input('A')

        # Outputs
        self.add_output('Image')


class MergeNode(OpenCompBaseNode):
    """Generic merge with selectable operation."""

    __identifier__ = 'opencomp.merge'
    NODE_NAME = 'Merge'
    CATEGORY = 'merge'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('B')
        self.add_input('A')

        # Outputs
        self.add_output('Image')


# ── Filter Nodes ───────────────────────────────────────────────────────────


class BlurNode(OpenCompBaseNode):
    """Gaussian blur."""

    __identifier__ = 'opencomp.filter'
    NODE_NAME = 'Blur'
    CATEGORY = 'filter'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


class SharpenNode(OpenCompBaseNode):
    """Sharpening filter."""

    __identifier__ = 'opencomp.filter'
    NODE_NAME = 'Sharpen'
    CATEGORY = 'filter'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


# ── Transform Nodes ────────────────────────────────────────────────────────


class TransformNode(OpenCompBaseNode):
    """2D transform — translate, rotate, scale."""

    __identifier__ = 'opencomp.transform'
    NODE_NAME = 'Transform'
    CATEGORY = 'transform'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


class CropNode(OpenCompBaseNode):
    """Crop image to region."""

    __identifier__ = 'opencomp.transform'
    NODE_NAME = 'Crop'
    CATEGORY = 'transform'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs
        self.add_output('Image')


# ── Viewer Nodes ───────────────────────────────────────────────────────────


class ViewerNode(OpenCompBaseNode):
    """Viewer — displays result in Blender viewport."""

    __identifier__ = 'opencomp.viewer'
    NODE_NAME = 'Viewer'
    CATEGORY = 'viewer'

    def __init__(self):
        super().__init__()

        # Inputs
        self.add_input('Image')

        # Outputs (none for Viewer)


# ── Node Registration ──────────────────────────────────────────────────────

# All node classes to register
NODE_CLASSES = [
    # I/O
    ReadNode,
    WriteNode,
    ConstantNode,
    # Color
    GradeNode,
    CDLNode,
    ShuffleNode,
    # Merge
    OverNode,
    MergeNode,
    # Filter
    BlurNode,
    SharpenNode,
    # Transform
    TransformNode,
    CropNode,
    # Viewer
    ViewerNode,
]


def register_nodes(graph):
    """Register all OpenComp node types with a NodeGraph instance.

    Args:
        graph: OpenCompGraph instance to register nodes with.
    """
    for node_class in NODE_CLASSES:
        graph.register_node(node_class)


def get_node_class_by_type(node_type):
    """Get a node class by its Blender type identifier.

    Args:
        node_type: Blender node type like 'OC_N_grade'

    Returns:
        Node class or None if not found.
    """
    # Map Blender types to Qt node classes
    type_map = {
        'OC_N_read': ReadNode,
        'OC_N_write': WriteNode,
        'OC_N_constant': ConstantNode,
        'OC_N_grade': GradeNode,
        'OC_N_cdl': CDLNode,
        'OC_N_shuffle': ShuffleNode,
        'OC_N_over': OverNode,
        'OC_N_merge': MergeNode,
        'OC_N_blur': BlurNode,
        'OC_N_sharpen': SharpenNode,
        'OC_N_transform': TransformNode,
        'OC_N_crop': CropNode,
        'OC_N_viewer': ViewerNode,
    }
    return type_map.get(node_type)
