# OpenComp — Blender Add-on
# See CLAUDE.md for architecture

bl_info = {
    "name":        "OpenComp",
    "author":      "Danger Studio",
    "version":     (0, 1, 0),
    "blender":     (5, 0, 0),
    "location":    "Node Editor",
    "description": "Open source Nuke-like VFX compositor",
    "category":    "Compositing",
    "doc_url":     "https://github.com/danger-studio/opencomp",
    "tracker_url": "https://github.com/danger-studio/opencomp/issues",
}

# Registration order:
# 1. compat (version detection)
# 2. node_graph (tree, sockets)
# 3. nodes (all node classes)
# 4. node categories (Add menu)
# 5. gpu_pipeline (executor, pool, framebuffer)
# 6. ui panels and operators
# 7. conform tool
# 8. openclaw_integration (last — depends on everything)

import bpy
import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem


# ── Node context menu override ─────────────────────────────────────────

_original_node_context_menu_draw = None


def _opencomp_node_context_menu_draw(self, context):
    """Node context menu — always shows Add submenu, even with selection."""
    snode = context.space_data

    # Only override for OpenComp trees; fall back for others
    if snode.tree_type != "OC_NT_compositor":
        if _original_node_context_menu_draw:
            _original_node_context_menu_draw(self, context)
        return

    layout = self.layout
    selected_nodes = context.selected_nodes
    selected_nodes_len = len(selected_nodes)

    # Always show Add menu at top
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.menu("NODE_MT_add", icon='ADD')
    layout.separator()

    if selected_nodes_len > 0:
        layout.operator("node.clipboard_copy", text="Copy", icon='COPYDOWN')
        layout.operator("node.clipboard_paste", text="Paste", icon='PASTEDOWN')
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator("node.duplicate_move", icon='DUPLICATE')
        layout.separator()
        layout.operator("node.delete", icon='X')
        layout.operator_context = 'EXEC_REGION_WIN'
        layout.operator("node.delete_reconnect", text="Dissolve")

        if selected_nodes_len > 1:
            layout.separator()
            layout.operator("node.link_make").replace = False
            layout.operator("node.link_make", text="Make and Replace Links").replace = True
            layout.operator("node.links_detach")

        layout.separator()
        layout.operator("node.join", text="Join in New Frame")
        layout.operator("node.detach", text="Remove from Frame")
    else:
        layout.operator("node.clipboard_paste", text="Paste", icon='PASTEDOWN')

    layout.separator()
    layout.operator("node.find_node", text="Find...", icon='VIEWZOOM')


def _override_node_context_menu():
    global _original_node_context_menu_draw
    try:
        cls = bpy.types.NODE_MT_context_menu
        _original_node_context_menu_draw = cls.draw
        cls.draw = _opencomp_node_context_menu_draw
    except Exception as e:
        print(f"[OpenComp] Node context menu override skipped: {e}")


def _restore_node_context_menu():
    global _original_node_context_menu_draw
    if _original_node_context_menu_draw is not None:
        try:
            bpy.types.NODE_MT_context_menu.draw = _original_node_context_menu_draw
            _original_node_context_menu_draw = None
        except Exception:
            pass


# ── Active Node Properties panel (appears in PROPERTIES area) ──────────

class OC_PT_active_node(bpy.types.Panel):
    """Node header — name and label (mirrors Node Editor sidebar)."""

    bl_idname = "OC_PT_active_node"
    bl_label = "Node"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return True

    def _get_active_node(self):
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor" and tree.nodes.active:
                return tree.nodes.active
        return None

    def draw(self, context):
        layout = self.layout
        node = self._get_active_node()
        if node is None:
            layout.label(text="Select a node", icon='NODE')
            return

        col = layout.column()
        col.prop(node, "name", icon=node.bl_icon)
        col.prop(node, "label")


class OC_PT_active_node_properties(bpy.types.Panel):
    """Node controls — the properties exposed by draw_buttons()."""

    bl_idname = "OC_PT_active_node_properties"
    bl_label = "Properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor" and tree.nodes.active:
                if hasattr(tree.nodes.active, 'draw_buttons'):
                    return True
        return False

    def draw(self, context):
        layout = self.layout
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor" and tree.nodes.active:
                tree.nodes.active.draw_buttons(context, layout)
                break


class OpenCompNodeCategory(NodeCategory):
    """Node category that only appears in OC_NT_compositor trees."""
    @classmethod
    def poll(cls, context):
        sd = getattr(context, "space_data", None)
        return sd is not None and getattr(sd, "tree_type", "") == "OC_NT_compositor"


# All node modules with their classes
_node_modules = []


def _import_nodes():
    """Import all node modules."""
    from .nodes.io import read, write
    from .nodes.color import grade, cdl, constant
    from .nodes.merge import over, merge, shuffle
    from .nodes.filter import blur, sharpen
    from .nodes.transform import transform, crop
    from .nodes import viewer  # import the package, not just viewer.py
    return [
        read, write,
        grade, cdl, constant,
        over, merge, shuffle,
        blur, sharpen,
        transform, crop,
        viewer,
    ]


# Node categories for the Add menu
_category_name = "OC_NODE_CATEGORIES"

def _draw_canvas_button(self, context):
    """Draw the 'Open Qt Canvas' button in the Node Editor header."""
    if context.space_data.tree_type == "OC_NT_compositor":
        layout = self.layout
        layout.operator("oc.launch_canvas", text="", icon='WINDOW')


_node_categories = [
    OpenCompNodeCategory("OC_CAT_INPUT", "Input", items=[
        NodeItem("OC_N_read"),
        NodeItem("OC_N_constant"),
    ]),
    OpenCompNodeCategory("OC_CAT_OUTPUT", "Output", items=[
        NodeItem("OC_N_write"),
        NodeItem("OC_N_viewer"),
    ]),
    OpenCompNodeCategory("OC_CAT_COLOR", "Color", items=[
        NodeItem("OC_N_grade"),
        NodeItem("OC_N_cdl"),
    ]),
    OpenCompNodeCategory("OC_CAT_MERGE", "Merge", items=[
        NodeItem("OC_N_over"),
        NodeItem("OC_N_merge"),
        NodeItem("OC_N_shuffle"),
    ]),
    OpenCompNodeCategory("OC_CAT_FILTER", "Filter", items=[
        NodeItem("OC_N_blur"),
        NodeItem("OC_N_sharpen"),
    ]),
    OpenCompNodeCategory("OC_CAT_TRANSFORM", "Transform", items=[
        NodeItem("OC_N_transform"),
        NodeItem("OC_N_crop"),
    ]),
]


def register():
    from .node_graph import tree, sockets
    tree.register()
    sockets.register()

    # Register all node classes
    global _node_modules
    _node_modules = _import_nodes()
    for mod in _node_modules:
        mod.register()

    # Register node categories for the Add menu
    nodeitems_utils.register_node_categories(_category_name, _node_categories)

    # Register UI panels
    bpy.utils.register_class(OC_PT_active_node)
    bpy.utils.register_class(OC_PT_active_node_properties)

    # Register Qt canvas launch operator
    from .qt_canvas.blender_launch import register_operator as register_canvas_operator
    register_canvas_operator()

    # Override node editor context menu
    _override_node_context_menu()

    # Add menu item to Node Editor header
    bpy.types.NODE_HT_header.append(_draw_canvas_button)


def unregister():
    # Remove canvas button from header
    try:
        bpy.types.NODE_HT_header.remove(_draw_canvas_button)
    except Exception:
        pass

    # Restore node editor context menu
    _restore_node_context_menu()

    # Unregister Qt canvas launch operator
    from .qt_canvas.blender_launch import unregister_operator as unregister_canvas_operator
    unregister_canvas_operator()

    # Unregister UI panels
    for cls in (OC_PT_active_node_properties, OC_PT_active_node):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    # Unregister node categories
    try:
        nodeitems_utils.unregister_node_categories(_category_name)
    except Exception:
        pass

    # Unregister all node classes (reverse order)
    for mod in reversed(_node_modules):
        mod.unregister()

    from .node_graph import sockets, tree
    sockets.unregister()
    tree.unregister()
