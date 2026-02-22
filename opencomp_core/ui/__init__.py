"""OpenComp UI — Complete Nuke-style interface.

Replaces all Blender UI with custom Nuke-inspired panels.
"""

from . import hide_blender_ui
from . import theme
from . import viewer
from . import properties
from . import timeline
from . import toolbar

modules = [
    hide_blender_ui,  # Must be first - hides all default UI
    theme,
    viewer,
    properties,
    timeline,
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
