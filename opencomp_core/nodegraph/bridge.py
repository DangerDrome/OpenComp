"""OpenComp NodeGraph Bridge — Direct Python communication.

This module provides direct Python communication between NodeGraphQt
and Blender. Both run in the same process, sharing state via this module.

Key responsibilities:
- Sync node selection from NodeGraphQt to Blender's active node
- Sync node connections from NodeGraphQt to Blender's node tree
- Sync parameter changes between both sides
- Trigger evaluation when the graph changes
"""

import bpy
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
import uuid
from .. import console


@dataclass
class NodeState:
    """State of a single node."""
    oc_id: str
    bl_idname: str  # Blender node type
    name: str
    x: float
    y: float
    properties: Dict[str, Any] = field(default_factory=dict)
    selected: bool = False


@dataclass
class LinkState:
    """State of a single link."""
    from_node_id: str
    from_port: str
    to_node_id: str
    to_port: str


class NodeGraphBridge:
    """Bridge between NodeGraphQt and Blender's node tree.

    This is a singleton that manages synchronization between the
    external Qt node editor and Blender's internal node tree.

    Usage:
        bridge = NodeGraphBridge.instance()
        bridge.set_blender_tree(tree)
        bridge.on_qt_node_selected(node_id)  # Called from Qt
    """

    _instance = None

    @classmethod
    def instance(cls) -> 'NodeGraphBridge':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # The Blender node tree we're syncing with
        self._blender_tree: Optional[bpy.types.NodeTree] = None

        # NodeGraphQt graph instance (set when Qt launches)
        self._qt_graph = None

        # Mapping between oc_id and Blender node names
        self._id_to_bl_name: Dict[str, str] = {}
        self._bl_name_to_id: Dict[str, str] = {}

        # Callbacks for Qt to call when events happen
        self._selection_callbacks: List[Callable[[str], None]] = []
        self._connection_callbacks: List[Callable[[str, str, str, str], None]] = []
        self._param_callbacks: List[Callable[[str, str, Any], None]] = []

        # Flag to prevent recursive updates
        self._syncing = False

        # Last selected node in Qt (for N-Panel sync)
        self._qt_selected_node_id: Optional[str] = None

    def set_blender_tree(self, tree: bpy.types.NodeTree) -> None:
        """Set the Blender node tree to sync with.

        Args:
            tree: The OpenComp node tree.
        """
        self._blender_tree = tree
        self._rebuild_id_mappings()

    def set_qt_graph(self, graph) -> None:
        """Set the NodeGraphQt graph instance.

        Args:
            graph: The OpenCompGraph instance from Qt.
        """
        self._qt_graph = graph

    def _rebuild_id_mappings(self) -> None:
        """Rebuild the id-to-name mappings from the Blender tree."""
        self._id_to_bl_name.clear()
        self._bl_name_to_id.clear()

        if self._blender_tree is None:
            return

        for node in self._blender_tree.nodes:
            # Try to get existing oc_id or create new one
            oc_id = getattr(node, 'oc_id', None)
            if not oc_id:
                oc_id = str(uuid.uuid4())[:8]
                # Store on node if possible
                try:
                    node['oc_id'] = oc_id
                except Exception:
                    pass

            self._id_to_bl_name[oc_id] = node.name
            self._bl_name_to_id[node.name] = oc_id

    def get_blender_tree(self) -> Optional[bpy.types.NodeTree]:
        """Get the current Blender node tree."""
        return self._blender_tree

    def get_qt_graph(self):
        """Get the current NodeGraphQt graph."""
        return self._qt_graph

    # =========================================================================
    # Selection Sync (Qt → Blender)
    # =========================================================================

    def on_qt_node_selected(self, oc_id: Optional[str]) -> None:
        """Called when a node is selected in NodeGraphQt.

        This updates Blender's active node so the N-Panel shows its properties.

        Args:
            oc_id: The selected node's oc_id, or None if deselected.
        """
        if self._syncing:
            return

        self._qt_selected_node_id = oc_id

        if self._blender_tree is None:
            return

        try:
            self._syncing = True

            # Deselect all nodes first
            for node in self._blender_tree.nodes:
                node.select = False

            if oc_id is None:
                self._blender_tree.nodes.active = None
            else:
                # Find the Blender node by oc_id
                bl_name = self._id_to_bl_name.get(oc_id)
                if bl_name and bl_name in self._blender_tree.nodes:
                    node = self._blender_tree.nodes[bl_name]
                    node.select = True
                    self._blender_tree.nodes.active = node

            # Trigger redraw of Properties panel
            self._redraw_properties()

        finally:
            self._syncing = False

    def on_qt_nodes_selected(self, oc_ids: List[str]) -> None:
        """Called when multiple nodes are selected in NodeGraphQt.

        Args:
            oc_ids: List of selected node oc_ids.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            # Deselect all
            for node in self._blender_tree.nodes:
                node.select = False

            # Select matching nodes
            active_node = None
            for oc_id in oc_ids:
                bl_name = self._id_to_bl_name.get(oc_id)
                if bl_name and bl_name in self._blender_tree.nodes:
                    node = self._blender_tree.nodes[bl_name]
                    node.select = True
                    if active_node is None:
                        active_node = node

            # Set first selected as active
            self._blender_tree.nodes.active = active_node
            self._qt_selected_node_id = oc_ids[0] if oc_ids else None

            self._redraw_properties()

        finally:
            self._syncing = False

    # =========================================================================
    # Connection Sync (Qt → Blender)
    # =========================================================================

    def on_qt_port_connected(self, from_oc_id: str, from_port: str,
                              to_oc_id: str, to_port: str) -> None:
        """Called when a connection is made in NodeGraphQt.

        Args:
            from_oc_id: Source node oc_id.
            from_port: Source port name.
            to_oc_id: Target node oc_id.
            to_port: Target port name.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            from_bl = self._id_to_bl_name.get(from_oc_id)
            to_bl = self._id_to_bl_name.get(to_oc_id)

            if not from_bl or not to_bl:
                return

            from_node = self._blender_tree.nodes.get(from_bl)
            to_node = self._blender_tree.nodes.get(to_bl)

            if not from_node or not to_node:
                return

            # Find the sockets by name or index
            from_socket = self._find_socket(from_node.outputs, from_port)
            to_socket = self._find_socket(to_node.inputs, to_port)

            if from_socket and to_socket:
                self._blender_tree.links.new(from_socket, to_socket)
                console.connection_made(from_bl, from_port, to_bl, to_port)

        finally:
            self._syncing = False

    def on_qt_port_disconnected(self, from_oc_id: str, from_port: str,
                                 to_oc_id: str, to_port: str) -> None:
        """Called when a connection is removed in NodeGraphQt.

        Args:
            from_oc_id: Source node oc_id.
            from_port: Source port name.
            to_oc_id: Target node oc_id.
            to_port: Target port name.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            from_bl = self._id_to_bl_name.get(from_oc_id)
            to_bl = self._id_to_bl_name.get(to_oc_id)

            if not from_bl or not to_bl:
                return

            # Find and remove the link
            for link in list(self._blender_tree.links):
                if (link.from_node.name == from_bl and
                    link.to_node.name == to_bl):
                    self._blender_tree.links.remove(link)
                    console.connection_removed(from_bl, from_port, to_bl, to_port)
                    break

        finally:
            self._syncing = False

    # =========================================================================
    # Node Operations (Qt → Blender)
    # =========================================================================

    def on_qt_node_created(self, oc_id: str, bl_idname: str,
                           x: float, y: float) -> Optional[str]:
        """Called when a node is created in NodeGraphQt.

        Args:
            oc_id: New node's oc_id.
            bl_idname: Blender node type to create.
            x: X position.
            y: Y position.

        Returns:
            The Blender node name, or None if creation failed.
        """
        if self._syncing or self._blender_tree is None:
            return None

        try:
            self._syncing = True

            node = self._blender_tree.nodes.new(bl_idname)
            node.location = (x, y)

            # Store oc_id
            try:
                node['oc_id'] = oc_id
            except Exception:
                pass

            # Update mappings
            self._id_to_bl_name[oc_id] = node.name
            self._bl_name_to_id[node.name] = oc_id

            console.node_created(node.name, bl_idname, (x, y))
            return node.name

        finally:
            self._syncing = False

    def on_qt_node_deleted(self, oc_id: str) -> None:
        """Called when a node is deleted in NodeGraphQt.

        Args:
            oc_id: The deleted node's oc_id.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            bl_name = self._id_to_bl_name.get(oc_id)
            if bl_name and bl_name in self._blender_tree.nodes:
                self._blender_tree.nodes.remove(self._blender_tree.nodes[bl_name])
                console.node_deleted(bl_name)

            # Clean up mappings
            if oc_id in self._id_to_bl_name:
                del self._id_to_bl_name[oc_id]
            if bl_name in self._bl_name_to_id:
                del self._bl_name_to_id[bl_name]

        finally:
            self._syncing = False

    def on_qt_node_moved(self, oc_id: str, x: float, y: float) -> None:
        """Called when a node is moved in NodeGraphQt.

        Args:
            oc_id: The moved node's oc_id.
            x: New X position.
            y: New Y position.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            bl_name = self._id_to_bl_name.get(oc_id)
            if bl_name and bl_name in self._blender_tree.nodes:
                self._blender_tree.nodes[bl_name].location = (x, y)

        finally:
            self._syncing = False

    # =========================================================================
    # Parameter Sync (Qt ↔ Blender)
    # =========================================================================

    def on_qt_param_changed(self, oc_id: str, param: str, value: Any) -> None:
        """Called when a parameter is changed in NodeGraphQt.

        Args:
            oc_id: The node's oc_id.
            param: Parameter name.
            value: New value.
        """
        if self._syncing or self._blender_tree is None:
            return

        try:
            self._syncing = True

            bl_name = self._id_to_bl_name.get(oc_id)
            if bl_name and bl_name in self._blender_tree.nodes:
                node = self._blender_tree.nodes[bl_name]
                if hasattr(node, param):
                    setattr(node, param, value)
                    console.param_changed(bl_name, param, value)

        finally:
            self._syncing = False

    def get_blender_param(self, oc_id: str, param: str) -> Any:
        """Get a parameter value from a Blender node.

        Args:
            oc_id: The node's oc_id.
            param: Parameter name.

        Returns:
            The parameter value, or None if not found.
        """
        if self._blender_tree is None:
            return None

        bl_name = self._id_to_bl_name.get(oc_id)
        if bl_name and bl_name in self._blender_tree.nodes:
            node = self._blender_tree.nodes[bl_name]
            if hasattr(node, param):
                return getattr(node, param)

        return None

    # =========================================================================
    # Sync from Blender to Qt
    # =========================================================================

    def sync_blender_to_qt(self) -> None:
        """Sync the entire Blender tree state to NodeGraphQt.

        Call this after loading a .blend file or when the tree changes
        outside of the bridge (e.g., via Blender's native node editor).
        """
        if self._syncing or self._qt_graph is None:
            return

        if self._blender_tree is None:
            return

        try:
            self._syncing = True

            # Build state dict
            state = self._build_state_from_blender()

            # Push to Qt graph
            self._apply_state_to_qt(state)

            # Rebuild mappings
            self._rebuild_id_mappings()

            console.synced(len(state['nodes']), "nodes to Qt")

        finally:
            self._syncing = False

    def _build_state_from_blender(self) -> Dict[str, Any]:
        """Build a state dict from the Blender tree."""
        nodes = []
        links = []

        for node in self._blender_tree.nodes:
            oc_id = self._bl_name_to_id.get(node.name)
            if not oc_id:
                oc_id = str(uuid.uuid4())[:8]
                self._id_to_bl_name[oc_id] = node.name
                self._bl_name_to_id[node.name] = oc_id

            node_state = {
                'oc_id': oc_id,
                'bl_idname': node.bl_idname,
                'name': node.name,
                'x': node.location.x,
                'y': node.location.y,
                'selected': node.select,
            }
            nodes.append(node_state)

        for link in self._blender_tree.links:
            from_id = self._bl_name_to_id.get(link.from_node.name)
            to_id = self._bl_name_to_id.get(link.to_node.name)
            if from_id and to_id:
                links.append({
                    'from_node_id': from_id,
                    'from_port': link.from_socket.name,
                    'to_node_id': to_id,
                    'to_port': link.to_socket.name,
                })

        return {'nodes': nodes, 'links': links}

    def _apply_state_to_qt(self, state: Dict[str, Any]) -> None:
        """Apply a state dict to the Qt graph."""
        # This will be implemented when Qt integration is active
        # For now, just store the state
        pass

    # =========================================================================
    # Evaluation Trigger
    # =========================================================================

    def trigger_evaluation(self) -> None:
        """Trigger re-evaluation of the node graph.

        Called when the graph structure changes (connections, node deletions).
        """
        if self._blender_tree is None:
            return

        # Mark tree as needing evaluation
        if hasattr(self._blender_tree, '_eval_needed'):
            self._blender_tree._eval_needed = True

        # Redraw all node editors
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_socket(self, sockets, name_or_index):
        """Find a socket by name or index."""
        # Try by name first
        for socket in sockets:
            if socket.name == name_or_index:
                return socket

        # Try by index
        try:
            idx = int(name_or_index)
            if 0 <= idx < len(sockets):
                return sockets[idx]
        except (ValueError, TypeError):
            pass

        # Return first available
        if sockets:
            return sockets[0]

        return None

    def _redraw_properties(self) -> None:
        """Trigger redraw of the Properties area."""
        for area in bpy.context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()


# Module-level convenience function
def get_bridge() -> NodeGraphBridge:
    """Get the NodeGraph bridge singleton."""
    return NodeGraphBridge.instance()
