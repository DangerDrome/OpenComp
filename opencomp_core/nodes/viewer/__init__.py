"""OpenComp Viewer module — aggregates viewer, panel, operators, keymaps."""

from . import viewer, panel, operators, keymaps


def register():
    viewer.register()
    panel.register()
    operators.register()
    keymaps.register()


def unregister():
    keymaps.unregister()
    operators.unregister()
    panel.unregister()
    viewer.unregister()
