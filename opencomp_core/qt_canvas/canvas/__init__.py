"""Canvas module — NodeGraphQt graph and node definitions."""

from .graph import OpenCompGraph
from .nodes import register_nodes, NODE_COLORS
from .style import apply_style, STYLE

__all__ = ['OpenCompGraph', 'register_nodes', 'NODE_COLORS', 'apply_style', 'STYLE']
