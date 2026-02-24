"""OpenComp UI — Complete Nuke-style interface.

Replaces all Blender UI with custom Nuke-inspired panels.
Timeline is integrated into the viewer panel.

Expected layout (like Nuke):
- PROPERTIES on left
- VIEW_3D on top right (viewer with timeline)
- NODE_EDITOR on bottom right (node graph)
"""

from . import hide_blender_ui
from . import theme
from . import viewer  # Includes integrated timeline at bottom
from . import properties
from . import toolbar
from . import headers

modules = [
    hide_blender_ui,  # Must be first - hides all default UI
    theme,
    headers,  # Custom headers for all areas
    viewer,  # Viewer with integrated timeline
    properties,
    toolbar,
]


def register():
    """Register all UI modules."""
    for mod in modules:
        mod.register()
    print("[OpenComp] Nuke-style UI registered")


def unregister():
    """Unregister all UI modules."""
    for mod in reversed(modules):
        mod.unregister()
