"""OpenComp Qt Canvas — Main window.

The main application window containing the node graph canvas and properties panel.
"""

from qtpy.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel,
)
from qtpy.QtCore import Qt, Signal

# Support both relative imports (as package) and absolute imports (standalone)
try:
    from ..canvas.graph import OpenCompGraph
    from ..canvas.nodes import register_nodes
    from ..canvas.style import apply_style
    from ..canvas.shortcuts import setup_shortcuts
    from .properties import PropertiesPanel
except ImportError:
    from canvas.graph import OpenCompGraph
    from canvas.nodes import register_nodes
    from canvas.style import apply_style
    from canvas.shortcuts import setup_shortcuts
    from ui.properties import PropertiesPanel


class OpenCompMainWindow(QMainWindow):
    """OpenComp main window — canvas + properties panel."""

    # Signals for IPC communication
    node_created = Signal(str, str, float, float)  # oc_id, node_type, x, y
    node_deleted = Signal(str)  # oc_id
    port_connected = Signal(str, str, str, str)  # from_node, from_port, to_node, to_port
    port_disconnected = Signal(str, str, str, str)
    param_changed = Signal(str, str, object)  # node_id, param, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._graph = None
        self._props_panel = None

        self._setup_ui()
        self._setup_graph()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("OpenComp")
        self.setMinimumSize(1280, 720)

        # Dark window styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QSplitter::handle {
                background-color: #333;
            }
            QStatusBar {
                background-color: #222;
                color: #888;
            }
        """)

        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter: canvas (80%) | properties (20%)
        splitter = QSplitter(Qt.Horizontal)

        # Node graph canvas (placeholder — will be set up in _setup_graph)
        self._canvas_widget = QWidget()
        splitter.addWidget(self._canvas_widget)

        # Properties panel
        self._props_panel = PropertiesPanel()
        splitter.addWidget(self._props_panel)

        # Set initial sizes (80/20 split)
        splitter.setSizes([1024, 256])

        layout.addWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self._status_label = QLabel("Ready")
        self._status.addWidget(self._status_label)
        self.setStatusBar(self._status)

    def _setup_graph(self):
        """Set up the NodeGraphQt graph."""
        # Create graph
        self._graph = OpenCompGraph()

        # Register all OpenComp node types
        register_nodes(self._graph)

        # Apply dark theme
        apply_style(self._graph)

        # Set up keyboard shortcuts
        setup_shortcuts(self._graph)

        # Get the graph widget and add it to the canvas area
        graph_widget = self._graph.widget
        if graph_widget:
            # Replace placeholder with actual graph widget
            layout = self._canvas_widget.layout()
            if layout is None:
                layout = QHBoxLayout(self._canvas_widget)
                layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(graph_widget)

    def _connect_signals(self):
        """Connect graph signals to window signals."""
        if self._graph is None:
            return

        # Node selection changed → update properties panel
        self._graph.node_selected.connect(self._on_node_selected)
        self._graph.nodes_deleted.connect(self._on_nodes_deleted)

        # Node creation/deletion for IPC
        self._graph.node_created.connect(self._on_node_created)
        self._graph.nodes_deleted.connect(self._on_nodes_deleted_ipc)

        # Port connections for IPC
        self._graph.port_connected.connect(self._on_port_connected)
        self._graph.port_disconnected.connect(self._on_port_disconnected)

        # Property changes from panel → IPC
        self._props_panel.property_changed.connect(self._on_param_changed)

    def _on_node_selected(self, node):
        """Handle node selection change.

        Args:
            node: Selected node, or None.
        """
        self._props_panel.set_node(node)
        if node:
            self._status_label.setText(f"Selected: {node.name()}")
        else:
            self._status_label.setText("Ready")

    def _on_nodes_deleted(self, node_ids):
        """Handle node deletion — clear properties if deleted node was selected.

        Args:
            node_ids: List of deleted node IDs.
        """
        # Clear properties panel
        self._props_panel.set_node(None)

    def _on_node_created(self, node):
        """Handle node creation for IPC.

        Args:
            node: The created node.
        """
        oc_id = node.get_oc_id()
        node_type = node.__class__.__identifier__ + '.' + node.__class__.NODE_NAME
        x, y = node.pos()
        self.node_created.emit(oc_id, node_type, x, y)

    def _on_nodes_deleted_ipc(self, node_ids):
        """Handle node deletion for IPC.

        Args:
            node_ids: List of deleted NodeGraphQt node IDs.
        """
        # Note: We need to emit the oc_id, not NodeGraphQt's internal ID
        # This requires tracking the mapping elsewhere
        for node_id in node_ids:
            self.node_deleted.emit(node_id)

    def _on_port_connected(self, input_port, output_port):
        """Handle port connection for IPC.

        Args:
            input_port: Input port that was connected.
            output_port: Output port that was connected.
        """
        from_node = output_port.node().get_oc_id()
        from_port = output_port.name()
        to_node = input_port.node().get_oc_id()
        to_port = input_port.name()
        self.port_connected.emit(from_node, from_port, to_node, to_port)

    def _on_port_disconnected(self, input_port, output_port):
        """Handle port disconnection for IPC.

        Args:
            input_port: Input port that was disconnected.
            output_port: Output port that was disconnected.
        """
        from_node = output_port.node().get_oc_id()
        from_port = output_port.name()
        to_node = input_port.node().get_oc_id()
        to_port = input_port.name()
        self.port_disconnected.emit(from_node, from_port, to_node, to_port)

    def _on_param_changed(self, node_id, param, value):
        """Handle parameter change from properties panel.

        Args:
            node_id: Node's oc_id.
            param: Parameter name.
            value: New value.
        """
        self.param_changed.emit(node_id, param, value)

    @property
    def graph(self):
        """Return the NodeGraphQt graph instance."""
        return self._graph

    def set_status(self, message):
        """Set status bar message.

        Args:
            message: Status message to display.
        """
        self._status_label.setText(message)
