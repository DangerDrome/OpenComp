"""OpenComp Node sidebar panel — node properties in the Node Editor.

Provides node properties in the NODE_EDITOR sidebar under the "Node" tab.
This is the standard Blender approach for editing node properties.
"""

import bpy


def _get_active_node(context):
    """Get the active node from the current space's node tree."""
    sd = getattr(context, "space_data", None)
    if sd is None:
        return None

    tree = getattr(sd, "node_tree", None)
    if tree is None:
        return None

    return tree.nodes.active


class OC_PT_node_item(bpy.types.Panel):
    """Active node name and label."""

    bl_idname = "OC_PT_node_item"
    bl_label = "Node"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Node"

    @classmethod
    def poll(cls, context):
        sd = getattr(context, "space_data", None)
        return sd and getattr(sd, "tree_type", "") == "OC_NT_compositor"

    def draw(self, context):
        layout = self.layout
        node = _get_active_node(context)

        if node is None:
            layout.label(text="Select a node", icon='NODE')
            return

        col = layout.column()
        col.prop(node, "name")
        if hasattr(node, "label"):
            col.prop(node, "label")


class OC_PT_node_properties(bpy.types.Panel):
    """Active node properties (draw_buttons)."""

    bl_idname = "OC_PT_node_properties"
    bl_label = "Properties"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Node"
    bl_parent_id = "OC_PT_node_item"

    @classmethod
    def poll(cls, context):
        sd = getattr(context, "space_data", None)
        if not (sd and getattr(sd, "tree_type", "") == "OC_NT_compositor"):
            return False
        node = _get_active_node(context)
        return node is not None and hasattr(node, 'draw_buttons')

    def draw(self, context):
        layout = self.layout
        node = _get_active_node(context)

        if node and hasattr(node, 'draw_buttons'):
            node.draw_buttons(context, layout)


def register():
    bpy.utils.register_class(OC_PT_node_item)
    bpy.utils.register_class(OC_PT_node_properties)


def unregister():
    try:
        bpy.utils.unregister_class(OC_PT_node_properties)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(OC_PT_node_item)
    except RuntimeError:
        pass
