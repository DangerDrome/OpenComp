"""OpenComp Qt Canvas — Main graph class.

OpenCompGraph is the NodeGraphQt subclass that provides top-to-bottom
node flow like Nuke and Houdini.
"""

from NodeGraphQt import NodeGraph


class OpenCompGraph(NodeGraph):
    """OpenComp node graph with top-to-bottom flow.

    This is the main canvas that replaces Blender's built-in left-to-right
    node editor with a Nuke/Houdini-style vertical flow.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Top-to-bottom flow — the whole reason we're doing this
        # MUST be set before adding any nodes
        self.set_layout_direction(1)  # 1 = vertical (top-to-bottom)

        # Nuke-style pipe (bezier curves)
        self.set_pipe_style(0)  # 0 = curved bezier

        # Enable pipe collision for drag-to-insert on wires
        # Note: set_pipe_collision may not exist in all NodeGraphQt versions
        try:
            self.set_pipe_collision(True)
        except AttributeError:
            pass

        # Acyclic graph only (no feedback loops in compositor)
        self.set_acyclic(True)

    def get_layout_direction(self):
        """Return the current layout direction.

        Returns:
            int: 0 = horizontal, 1 = vertical
        """
        return self._layout_direction if hasattr(self, '_layout_direction') else 1

    def set_layout_direction(self, direction):
        """Set the graph layout direction.

        Args:
            direction: 0 = horizontal (left-to-right), 1 = vertical (top-to-bottom)
        """
        self._layout_direction = direction
        super().set_layout_direction(direction)
