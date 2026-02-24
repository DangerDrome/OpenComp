"""OpenComp NodeGraphQt Integration — Run Qt in Blender's process.

This module handles launching NodeGraphQt as a window within Blender's
process, enabling direct Python communication without IPC.

The Qt event loop is integrated with Blender via timers that process
Qt events periodically.
"""

import bpy
import os
import sys
from typing import Optional

# Global state
_qt_app = None
_qt_window = None
_qt_timer_handle = None
_qt_available = False


def _check_qt_available() -> bool:
    """Check if Qt/PySide6 is available."""
    global _qt_available

    try:
        # Try to import required modules
        os.environ.setdefault('QT_API', 'pyside6')

        from qtpy.QtWidgets import QApplication
        from qtpy.QtCore import QTimer

        _qt_available = True
        return True

    except ImportError as e:
        print(f"[OpenComp] Qt not available: {e}")
        print("[OpenComp] Install PySide6: pip install PySide6 NodeGraphQt")
        _qt_available = False
        return False


def is_qt_available() -> bool:
    """Check if Qt is available for use."""
    return _qt_available or _check_qt_available()


def _process_qt_events():
    """Timer callback to process Qt events.

    This is called periodically by Blender's timer system to keep
    Qt's event loop running.
    """
    global _qt_app

    if _qt_app is None:
        return None  # Stop timer

    try:
        _qt_app.processEvents()
    except Exception as e:
        print(f"[OpenComp] Qt event processing error: {e}")

    return 0.016  # ~60 FPS


def launch_nodegraph() -> bool:
    """Launch the NodeGraphQt window.

    Returns:
        True if successful, False otherwise.
    """
    global _qt_app, _qt_window, _qt_timer_handle

    if not is_qt_available():
        return False

    # Already running?
    if _qt_window is not None:
        try:
            _qt_window.show()
            _qt_window.raise_()
            _qt_window.activateWindow()
            return True
        except:
            pass

    try:
        from qtpy.QtWidgets import QApplication
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QPalette, QColor

        # Create Qt application if not exists
        if _qt_app is None:
            # Check if QApplication already exists (might be shared)
            _qt_app = QApplication.instance()
            if _qt_app is None:
                # Enable high DPI
                QApplication.setHighDpiScaleFactorRoundingPolicy(
                    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
                )
                _qt_app = QApplication(sys.argv)
                _qt_app.setApplicationName("OpenComp")

                # Apply dark palette
                palette = QPalette()
                palette.setColor(QPalette.Window, QColor(30, 30, 30))
                palette.setColor(QPalette.WindowText, QColor(200, 200, 200))
                palette.setColor(QPalette.Base, QColor(40, 40, 40))
                palette.setColor(QPalette.AlternateBase, QColor(50, 50, 50))
                palette.setColor(QPalette.Text, QColor(200, 200, 200))
                palette.setColor(QPalette.Button, QColor(50, 50, 50))
                palette.setColor(QPalette.ButtonText, QColor(200, 200, 200))
                palette.setColor(QPalette.Highlight, QColor(76, 204, 115))
                palette.setColor(QPalette.HighlightedText, QColor(30, 30, 30))
                _qt_app.setPalette(palette)

        # Create main window
        from ..qt_canvas.ui.main_window import OpenCompMainWindow
        from .bridge import get_bridge

        _qt_window = OpenCompMainWindow()
        _qt_window.setWindowTitle("OpenComp Node Graph")

        # Connect signals to bridge
        bridge = get_bridge()
        bridge.set_qt_graph(_qt_window.graph)

        # Connect Qt signals to bridge methods
        _connect_qt_signals(_qt_window, bridge)

        # Sync current Blender state to Qt
        _sync_blender_to_qt()

        # Show window
        _qt_window.show()

        # Start Qt event processing timer
        if _qt_timer_handle is None:
            _qt_timer_handle = bpy.app.timers.register(
                _process_qt_events,
                first_interval=0.016,
                persistent=True
            )

        print("[OpenComp] NodeGraphQt window launched")
        return True

    except Exception as e:
        print(f"[OpenComp] Failed to launch NodeGraphQt: {e}")
        import traceback
        traceback.print_exc()
        return False


def _connect_qt_signals(window, bridge):
    """Connect Qt window signals to the bridge.

    Args:
        window: OpenCompMainWindow instance.
        bridge: NodeGraphBridge instance.
    """
    graph = window.graph

    if graph is None:
        return

    # Node selection
    def on_selection_changed():
        """Handle selection change in Qt graph."""
        selected = graph.selected_nodes()
        if selected:
            # Get oc_ids of selected nodes
            oc_ids = []
            for node in selected:
                oc_id = getattr(node, '_oc_id', None)
                if oc_id:
                    oc_ids.append(oc_id)
            if oc_ids:
                bridge.on_qt_nodes_selected(oc_ids)
        else:
            bridge.on_qt_node_selected(None)

    # Try to connect selection signal (name varies by NodeGraphQt version)
    try:
        graph.node_selection_changed.connect(on_selection_changed)
    except AttributeError:
        try:
            graph.nodes_selected.connect(lambda nodes: on_selection_changed())
        except AttributeError:
            pass

    # Node creation
    if hasattr(graph, 'node_created'):
        def on_node_created(node):
            oc_id = getattr(node, '_oc_id', None) or str(id(node))[:8]
            node._oc_id = oc_id
            # Map Qt node type to Blender node type
            bl_idname = _qt_type_to_bl_idname(node)
            x, y = node.pos()
            bridge.on_qt_node_created(oc_id, bl_idname, x, y)

        graph.node_created.connect(on_node_created)

    # Node deletion
    if hasattr(graph, 'nodes_deleted'):
        def on_nodes_deleted(nodes):
            for node_id in nodes:
                bridge.on_qt_node_deleted(node_id)

        graph.nodes_deleted.connect(on_nodes_deleted)

    # Port connection
    if hasattr(graph, 'port_connected'):
        def on_port_connected(input_port, output_port):
            from_node = output_port.node()
            to_node = input_port.node()
            from_id = getattr(from_node, '_oc_id', str(id(from_node))[:8])
            to_id = getattr(to_node, '_oc_id', str(id(to_node))[:8])
            bridge.on_qt_port_connected(
                from_id, output_port.name(),
                to_id, input_port.name()
            )
            bridge.trigger_evaluation()

        graph.port_connected.connect(on_port_connected)

    # Port disconnection
    if hasattr(graph, 'port_disconnected'):
        def on_port_disconnected(input_port, output_port):
            from_node = output_port.node()
            to_node = input_port.node()
            from_id = getattr(from_node, '_oc_id', str(id(from_node))[:8])
            to_id = getattr(to_node, '_oc_id', str(id(to_node))[:8])
            bridge.on_qt_port_disconnected(
                from_id, output_port.name(),
                to_id, input_port.name()
            )
            bridge.trigger_evaluation()

        graph.port_disconnected.connect(on_port_disconnected)

    # Property changes from panel
    if hasattr(window, 'param_changed'):
        window.param_changed.connect(
            lambda node_id, param, value: bridge.on_qt_param_changed(node_id, param, value)
        )


def _qt_type_to_bl_idname(node) -> str:
    """Convert a Qt node type to Blender node bl_idname.

    Args:
        node: NodeGraphQt node instance.

    Returns:
        Blender node type string.
    """
    # Get the node class identifier
    identifier = getattr(node.__class__, '__identifier__', '')
    name = getattr(node.__class__, 'NODE_NAME', node.__class__.__name__)

    # Map common types
    type_map = {
        'Read': 'OC_N_read',
        'Write': 'OC_N_write',
        'Viewer': 'OC_N_viewer',
        'Grade': 'OC_N_grade',
        'CDL': 'OC_N_cdl',
        'Over': 'OC_N_over',
        'Merge': 'OC_N_merge',
        'Shuffle': 'OC_N_shuffle',
        'Blur': 'OC_N_blur',
        'Sharpen': 'OC_N_sharpen',
        'Transform': 'OC_N_transform',
        'Crop': 'OC_N_crop',
        'Constant': 'OC_N_constant',
        'Reroute': 'OC_N_reroute',
        'Roto': 'OC_N_roto',
    }

    return type_map.get(name, f'OC_N_{name.lower()}')


def _sync_blender_to_qt():
    """Sync current Blender tree state to Qt graph."""
    from .bridge import get_bridge

    bridge = get_bridge()

    # Find the OpenComp node tree
    tree = None
    for ng in bpy.data.node_groups:
        if ng.bl_idname == 'OC_NT_compositor':
            tree = ng
            break

    if tree:
        bridge.set_blender_tree(tree)
        bridge.sync_blender_to_qt()


def close_nodegraph():
    """Close the NodeGraphQt window."""
    global _qt_window, _qt_timer_handle

    if _qt_window is not None:
        try:
            _qt_window.close()
        except:
            pass
        _qt_window = None

    if _qt_timer_handle is not None:
        try:
            bpy.app.timers.unregister(_qt_timer_handle)
        except:
            pass
        _qt_timer_handle = None

    print("[OpenComp] NodeGraphQt window closed")


def is_nodegraph_open() -> bool:
    """Check if the NodeGraphQt window is currently open."""
    global _qt_window
    if _qt_window is not None:
        try:
            return _qt_window.isVisible()
        except:
            pass
    return False


def get_qt_window():
    """Get the current Qt window instance."""
    return _qt_window


# Blender Operators for launching NodeGraphQt

class OC_OT_launch_nodegraph(bpy.types.Operator):
    """Launch the NodeGraphQt node editor window"""
    bl_idname = "oc.launch_nodegraph"
    bl_label = "Open Node Graph"
    bl_description = "Open the NodeGraphQt node editor (Tab)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if is_nodegraph_open():
            # If already open, focus it
            if _qt_window:
                _qt_window.raise_()
                _qt_window.activateWindow()
            return {'FINISHED'}

        if launch_nodegraph():
            self.report({'INFO'}, "NodeGraphQt window opened")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Could not open NodeGraphQt. Is PySide6 installed?")
            return {'CANCELLED'}


class OC_OT_close_nodegraph(bpy.types.Operator):
    """Close the NodeGraphQt node editor window"""
    bl_idname = "oc.close_nodegraph"
    bl_label = "Close Node Graph"
    bl_options = {'REGISTER'}

    def execute(self, context):
        close_nodegraph()
        return {'FINISHED'}


class OC_OT_toggle_nodegraph(bpy.types.Operator):
    """Toggle the NodeGraphQt node editor window"""
    bl_idname = "oc.toggle_nodegraph"
    bl_label = "Toggle Node Graph"
    bl_description = "Toggle the NodeGraphQt window (Tab)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if is_nodegraph_open():
            close_nodegraph()
        else:
            launch_nodegraph()
        return {'FINISHED'}


# Registration
_classes = [
    OC_OT_launch_nodegraph,
    OC_OT_close_nodegraph,
    OC_OT_toggle_nodegraph,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    print("[OpenComp] NodeGraphQt integration registered")


def unregister():
    # Close Qt window first
    close_nodegraph()

    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
