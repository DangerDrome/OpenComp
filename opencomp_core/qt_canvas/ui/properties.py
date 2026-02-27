"""OpenComp Qt Canvas — Node properties panel.

Displays and edits properties of the selected node.
"""

from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QLineEdit, QComboBox,
    QScrollArea, QFrame,
)
from qtpy.QtCore import Signal


class PropertiesPanel(QWidget):
    """Node properties panel — right sidebar showing selected node parameters."""

    # Emitted when a property value changes: (node_id, param_name, value)
    property_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node = None
        self._widgets = {}  # param_name -> widget

        self._setup_ui()

    def _setup_ui(self):
        """Set up the properties panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        self._header = QLabel("No Selection")
        self._header.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ccc;
                padding: 4px;
            }
        """)
        layout.addWidget(self._header)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #444;")
        layout.addWidget(separator)

        # Scrollable properties area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
            }
        """)

        self._props_widget = QWidget()
        self._props_layout = QVBoxLayout(self._props_widget)
        self._props_layout.setContentsMargins(0, 0, 0, 0)
        self._props_layout.setSpacing(4)
        self._props_layout.addStretch()

        scroll.setWidget(self._props_widget)
        layout.addWidget(scroll)

        # Apply dark styling
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                color: #ccc;
            }
            QLineEdit, QDoubleSpinBox, QComboBox {
                background-color: #333;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px;
                color: #ddd;
            }
            QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #ffa500;
            }
            QPushButton {
                background-color: #444;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 8px;
                color: #ddd;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

    def set_node(self, node):
        """Display properties for the given node.

        Args:
            node: NodeGraphQt node instance, or None to clear.
        """
        self._current_node = node
        self._clear_properties()

        if node is None:
            self._header.setText("No Selection")
            return

        # Update header with node name and type
        node_name = node.name()
        node_type = node.__class__.NODE_NAME
        self._header.setText(f"{node_name} ({node_type})")

        # Build property widgets based on node type
        self._build_properties(node)

    def _clear_properties(self):
        """Remove all property widgets."""
        self._widgets.clear()

        # Remove all widgets except the stretch
        while self._props_layout.count() > 1:
            item = self._props_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _build_properties(self, node):
        """Build property widgets for a node.

        Args:
            node: NodeGraphQt node instance.
        """
        # Get node properties (NodeGraphQt stores them as model properties)
        properties = node.model.custom_properties

        for prop_name, prop_value in properties.items():
            if prop_name == 'oc_id':
                continue  # Don't show internal ID

            widget = self._create_property_widget(prop_name, prop_value)
            if widget:
                row = QHBoxLayout()
                label = QLabel(prop_name.replace('_', ' ').title())
                label.setFixedWidth(80)
                row.addWidget(label)
                row.addWidget(widget)

                container = QWidget()
                container.setLayout(row)
                self._props_layout.insertWidget(
                    self._props_layout.count() - 1,  # Before stretch
                    container
                )
                self._widgets[prop_name] = widget

    def _create_property_widget(self, prop_name, prop_value):
        """Create an appropriate widget for a property value.

        Args:
            prop_name: Property name.
            prop_value: Current property value.

        Returns:
            QWidget for editing the property.
        """
        if isinstance(prop_value, str):
            widget = QLineEdit(prop_value)
            widget.textChanged.connect(
                lambda v, n=prop_name: self._on_property_changed(n, v)
            )
            return widget

        elif isinstance(prop_value, bool):
            widget = QComboBox()
            widget.addItems(['False', 'True'])
            widget.setCurrentIndex(1 if prop_value else 0)
            widget.currentIndexChanged.connect(
                lambda i, n=prop_name: self._on_property_changed(n, i == 1)
            )
            return widget

        elif isinstance(prop_value, (int, float)):
            widget = QDoubleSpinBox()
            widget.setRange(-10000, 10000)
            widget.setDecimals(3 if isinstance(prop_value, float) else 0)
            widget.setValue(prop_value)
            widget.valueChanged.connect(
                lambda v, n=prop_name: self._on_property_changed(n, v)
            )
            return widget

        elif isinstance(prop_value, (list, tuple)) and len(prop_value) == 3:
            # Vector3 (e.g., lift/gamma/gain colors)
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)

            for i, v in enumerate(prop_value):
                spin = QDoubleSpinBox()
                spin.setRange(-10, 10)
                spin.setDecimals(3)
                spin.setValue(v)
                spin.valueChanged.connect(
                    lambda val, name=prop_name, idx=i: self._on_vector_changed(name, idx, val)
                )
                layout.addWidget(spin)

            return container

        return None

    def _on_property_changed(self, prop_name, value):
        """Handle property value change.

        Args:
            prop_name: Name of the changed property.
            value: New value.
        """
        if self._current_node:
            node_id = self._current_node.get_oc_id()
            self.property_changed.emit(node_id, prop_name, value)

    def _on_vector_changed(self, prop_name, index, value):
        """Handle vector component change.

        Args:
            prop_name: Property name.
            index: Component index (0, 1, or 2).
            value: New component value.
        """
        if self._current_node:
            # Get current vector and update component
            current = list(self._current_node.get_property(prop_name))
            current[index] = value
            node_id = self._current_node.get_oc_id()
            self.property_changed.emit(node_id, prop_name, current)
