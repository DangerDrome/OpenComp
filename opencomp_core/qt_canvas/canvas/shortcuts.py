"""OpenComp Qt Canvas — Nuke-compatible keyboard shortcuts.

Defines keyboard shortcuts that match Nuke's behavior for familiarity.
"""

from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence


# Nuke-compatible keyboard shortcuts
SHORTCUTS = {
    # View/Navigation
    'zoom_to_fit': QKeySequence('1'),
    'frame_selected': QKeySequence('F'),
    'frame_all': QKeySequence('Home'),

    # Selection
    'select_all': QKeySequence('A'),
    'deselect_all': QKeySequence('Shift+A'),
    'invert_selection': QKeySequence('Ctrl+I'),

    # Edit
    'undo': QKeySequence('Ctrl+Z'),
    'redo': QKeySequence('Ctrl+Shift+Z'),
    'delete': QKeySequence(Qt.Key_Delete),
    'delete_alt': QKeySequence(Qt.Key_Backspace),
    'duplicate': QKeySequence('Ctrl+D'),
    'copy': QKeySequence('Ctrl+C'),
    'paste': QKeySequence('Ctrl+V'),
    'cut': QKeySequence('Ctrl+X'),

    # Node operations
    'add_node': QKeySequence(Qt.Key_Tab),
    'disable_node': QKeySequence('D'),
    'group_nodes': QKeySequence('Ctrl+G'),
    'ungroup_nodes': QKeySequence('Ctrl+Shift+G'),

    # Layout
    'auto_layout': QKeySequence('L'),
    'snap_to_grid': QKeySequence('Shift+S'),
    'align_horizontal': QKeySequence('Shift+H'),
    'align_vertical': QKeySequence('Shift+V'),

    # View
    'toggle_minimap': QKeySequence('M'),
    'toggle_grid': QKeySequence('G'),
}


def setup_shortcuts(graph):
    """Set up keyboard shortcuts for the graph.

    Args:
        graph: OpenCompGraph instance.
    """
    # NodeGraphQt has built-in hotkey support via set_shortcut
    # If not available, skip (shortcuts are secondary functionality)

    if not hasattr(graph, 'set_shortcut'):
        # Older NodeGraphQt version - shortcuts are already built-in
        return

    # Get the graph widget (viewer)
    viewer = graph.viewer()
    if viewer is None:
        return

    # Register hotkeys with the graph
    # Note: Some of these may already be set by NodeGraphQt defaults
    try:
        # View shortcuts
        graph.set_shortcut('fit_to_selection', SHORTCUTS['frame_selected'])
        graph.set_shortcut('zoom_in', QKeySequence('+'))
        graph.set_shortcut('zoom_out', QKeySequence('-'))

        # Edit shortcuts
        graph.set_shortcut('delete', SHORTCUTS['delete'])
        graph.set_shortcut('copy', SHORTCUTS['copy'])
        graph.set_shortcut('paste', SHORTCUTS['paste'])
        graph.set_shortcut('cut', SHORTCUTS['cut'])
        graph.set_shortcut('undo', SHORTCUTS['undo'])
        graph.set_shortcut('redo', SHORTCUTS['redo'])
        graph.set_shortcut('duplicate', SHORTCUTS['duplicate'])

        # Node operations
        graph.set_shortcut('search_nodes', SHORTCUTS['add_node'])
        graph.set_shortcut('disable', SHORTCUTS['disable_node'])
    except (AttributeError, TypeError):
        # Shortcut API not available or different signature
        pass
