"""OpenComp Node Canvas — Native GPU-rendered node graph.

A Nuke-style top-to-bottom node graph built using Blender's GPU module.
Renders directly in a VIEW_3D area using draw handlers.

No external dependencies (Qt, PySide, etc.) — pure Blender Python + GPU.
"""

from .renderer import NodeCanvasRenderer
from .state import CanvasState
from .operators import register, unregister

__all__ = [
    'NodeCanvasRenderer',
    'CanvasState',
    'register',
    'unregister',
]
