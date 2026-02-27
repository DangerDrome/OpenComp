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
# 7. node_canvas (GPU-rendered canvas)
# 8. conform tool
# 9. openclaw_integration (last — depends on everything)

import bpy
from . import console


# ── Node Add menu override ─────────────────────────────────────────────

_original_node_add_menu_draw = None


def _opencomp_node_add_menu_draw(self, context):
    """NODE_MT_add override — shows our nodes when in OpenComp tree."""
    snode = context.space_data
    tree_type = getattr(snode, 'tree_type', '')

    # Only override for OpenComp trees; fall back for others
    if tree_type != "OC_NT_compositor":
        if _original_node_add_menu_draw:
            _original_node_add_menu_draw(self, context)
        return
    layout = self.layout

    # Input
    layout.label(text="Input", icon='IMPORT')
    layout.operator("oc.add_node", text="Read").node_type = "OC_N_read"
    layout.operator("oc.add_node", text="Constant").node_type = "OC_N_constant"
    layout.separator()

    # Output
    layout.label(text="Output", icon='EXPORT')
    layout.operator("oc.add_node", text="Write").node_type = "OC_N_write"
    layout.operator("oc.add_node", text="Viewer").node_type = "OC_N_viewer"
    layout.separator()

    # Color
    layout.label(text="Color", icon='COLOR')
    layout.operator("oc.add_node", text="Grade").node_type = "OC_N_grade"
    layout.operator("oc.add_node", text="CDL").node_type = "OC_N_cdl"
    layout.separator()

    # Merge
    layout.label(text="Merge", icon='SELECT_EXTEND')
    layout.operator("oc.add_node", text="Over").node_type = "OC_N_over"
    layout.operator("oc.add_node", text="Merge").node_type = "OC_N_merge"
    layout.operator("oc.add_node", text="Shuffle").node_type = "OC_N_shuffle"
    layout.separator()

    # Filter
    layout.label(text="Filter", icon='MATFLUID')
    layout.operator("oc.add_node", text="Blur").node_type = "OC_N_blur"
    layout.operator("oc.add_node", text="Sharpen").node_type = "OC_N_sharpen"
    layout.separator()

    # Transform
    layout.label(text="Transform", icon='ORIENTATION_GLOBAL')
    layout.operator("oc.add_node", text="Transform").node_type = "OC_N_transform"
    layout.operator("oc.add_node", text="Crop").node_type = "OC_N_crop"
    layout.separator()

    # Draw
    layout.label(text="Draw", icon='MESH_CIRCLE')
    layout.operator("oc.add_node", text="Roto").node_type = "OC_N_roto"
    layout.separator()

    # Utility
    layout.label(text="Utility", icon='ARROW_LEFTRIGHT')
    layout.operator("oc.add_node", text="Reroute").node_type = "OC_N_reroute"


def _override_node_add_menu():
    global _original_node_add_menu_draw
    try:
        cls = bpy.types.NODE_MT_add
        _original_node_add_menu_draw = cls.draw
        cls.draw = _opencomp_node_add_menu_draw
    except Exception as e:
        console.warning(f"Node add menu override skipped: {e}")


def _restore_node_add_menu():
    global _original_node_add_menu_draw
    if _original_node_add_menu_draw is not None:
        try:
            bpy.types.NODE_MT_add.draw = _original_node_add_menu_draw
            _original_node_add_menu_draw = None
        except Exception:
            pass


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
        console.warning(f"Node context menu override skipped: {e}")


def _restore_node_context_menu():
    global _original_node_context_menu_draw
    if _original_node_context_menu_draw is not None:
        try:
            bpy.types.NODE_MT_context_menu.draw = _original_node_context_menu_draw
            _original_node_context_menu_draw = None
        except Exception:
            pass


# ── Active Node Properties panel (appears in PROPERTIES area) ──────────

def _find_active_oc_node():
    """Find the active node from any OpenComp tree."""
    # Check all node groups
    for tree in bpy.data.node_groups:
        if tree.bl_idname == "OC_NT_compositor" and tree.nodes.active:
            return tree.nodes.active

    # Also check node editor spaces directly
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR' and space.tree_type == "OC_NT_compositor":
                            tree = space.node_tree
                            if tree and tree.nodes.active:
                                return tree.nodes.active
    except Exception:
        pass

    return None


class OC_PT_active_node(bpy.types.Panel):
    """Node properties panel - custom tab in Properties editor."""

    bl_idname = "OC_PT_active_node"
    bl_label = "Active Node"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'  # Custom context = new tab
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return True  # Always show

    def draw(self, context):
        layout = self.layout
        node = _find_active_oc_node()
        if node is None:
            layout.label(text="Select a node", icon='NODE')
            return

        col = layout.column()
        col.prop(node, "name", icon=node.bl_icon)
        if hasattr(node, "label"):
            col.prop(node, "label")


class OC_PT_active_node_properties(bpy.types.Panel):
    """Node controls - properties exposed by draw_buttons()."""

    bl_idname = "OC_PT_active_node_properties"
    bl_label = "Properties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_parent_id = "OC_PT_active_node"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        node = _find_active_oc_node()
        return node is not None and hasattr(node, 'draw_buttons')

    def draw(self, context):
        layout = self.layout
        node = _find_active_oc_node()
        if node and hasattr(node, 'draw_buttons'):
            node.draw_buttons(context, layout)


# ── Custom Add Menu (Blender 5.0 compatible) ─────────────────────────────
# nodeitems_utils is deprecated in Blender 4.0+. Add menu is defined via
# NodeTree.draw_add() classmethod (in tree.py). These menu classes are
# legacy fallbacks that append to NODE_MT_add for broader compatibility.

def _is_opencomp_tree(context):
    """Check if we're in an OpenComp node tree."""
    sd = getattr(context, "space_data", None)
    return sd is not None and getattr(sd, "tree_type", "") == "OC_NT_compositor"


class OC_MT_add_input(bpy.types.Menu):
    bl_idname = "OC_MT_add_input"
    bl_label = "Input"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Read", icon='IMAGE_DATA').node_type = "OC_N_read"
        layout.operator("oc.add_node", text="Constant", icon='COLOR').node_type = "OC_N_constant"


class OC_MT_add_output(bpy.types.Menu):
    bl_idname = "OC_MT_add_output"
    bl_label = "Output"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Write", icon='EXPORT').node_type = "OC_N_write"
        layout.operator("oc.add_node", text="Viewer", icon='HIDE_OFF').node_type = "OC_N_viewer"


class OC_MT_add_color(bpy.types.Menu):
    bl_idname = "OC_MT_add_color"
    bl_label = "Color"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Grade", icon='COLOR').node_type = "OC_N_grade"
        layout.operator("oc.add_node", text="CDL", icon='COLOR').node_type = "OC_N_cdl"


class OC_MT_add_merge(bpy.types.Menu):
    bl_idname = "OC_MT_add_merge"
    bl_label = "Merge"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Over", icon='SELECT_EXTEND').node_type = "OC_N_over"
        layout.operator("oc.add_node", text="Merge", icon='SELECT_EXTEND').node_type = "OC_N_merge"
        layout.operator("oc.add_node", text="Shuffle", icon='MOD_ARRAY').node_type = "OC_N_shuffle"


class OC_MT_add_filter(bpy.types.Menu):
    bl_idname = "OC_MT_add_filter"
    bl_label = "Filter"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Blur", icon='MATFLUID').node_type = "OC_N_blur"
        layout.operator("oc.add_node", text="Sharpen", icon='SHARPCURVE').node_type = "OC_N_sharpen"


class OC_MT_add_transform(bpy.types.Menu):
    bl_idname = "OC_MT_add_transform"
    bl_label = "Transform"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Transform", icon='ORIENTATION_GLOBAL').node_type = "OC_N_transform"
        layout.operator("oc.add_node", text="Crop", icon='SELECT_INTERSECT').node_type = "OC_N_crop"


class OC_MT_add_draw(bpy.types.Menu):
    bl_idname = "OC_MT_add_draw"
    bl_label = "Draw"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Roto", icon='MESH_CIRCLE').node_type = "OC_N_roto"


class OC_MT_add_utility(bpy.types.Menu):
    bl_idname = "OC_MT_add_utility"
    bl_label = "Utility"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.add_node", text="Reroute", icon='ARROW_LEFTRIGHT').node_type = "OC_N_reroute"


class OC_MT_add(bpy.types.Menu):
    """OpenComp Add Node Menu"""
    bl_idname = "OC_MT_add"
    bl_label = "Add"

    def draw(self, context):
        layout = self.layout
        layout.menu("OC_MT_add_input", icon='IMPORT')
        layout.menu("OC_MT_add_output", icon='EXPORT')
        layout.menu("OC_MT_add_color", icon='COLOR')
        layout.menu("OC_MT_add_merge", icon='SELECT_EXTEND')
        layout.menu("OC_MT_add_filter", icon='MATFLUID')
        layout.menu("OC_MT_add_transform", icon='ORIENTATION_GLOBAL')
        layout.menu("OC_MT_add_draw", icon='MESH_CIRCLE')
        layout.menu("OC_MT_add_utility", icon='ARROW_LEFTRIGHT')


_add_menu_classes = [
    OC_MT_add_input,
    OC_MT_add_output,
    OC_MT_add_color,
    OC_MT_add_merge,
    OC_MT_add_filter,
    OC_MT_add_transform,
    OC_MT_add_draw,
    OC_MT_add_utility,
    OC_MT_add,
]


def _draw_opencomp_add_menu(self, context):
    """Append OpenComp categories to NODE_MT_add when in OpenComp tree."""
    if _is_opencomp_tree(context):
        layout = self.layout
        layout.separator()
        layout.menu("OC_MT_add_input", icon='IMPORT')
        layout.menu("OC_MT_add_output", icon='EXPORT')
        layout.menu("OC_MT_add_color", icon='COLOR')
        layout.menu("OC_MT_add_merge", icon='SELECT_EXTEND')
        layout.menu("OC_MT_add_filter", icon='MATFLUID')
        layout.menu("OC_MT_add_transform", icon='ORIENTATION_GLOBAL')
        layout.menu("OC_MT_add_draw", icon='MESH_CIRCLE')
        layout.menu("OC_MT_add_utility", icon='ARROW_LEFTRIGHT')


# All node modules with their classes
_node_modules = []


def _import_nodes():
    """Import all node modules."""
    from .nodes.io import read, write
    from .nodes.color import grade, cdl, constant
    from .nodes.merge import over, merge, shuffle
    from .nodes.filter import blur, sharpen
    from .nodes.transform import transform, crop
    from .nodes.draw import roto
    from .nodes.utility import reroute
    from .nodes import viewer  # import the package, not just viewer.py
    from .nodes import node_panel  # Node Editor sidebar panels
    return [
        read, write,
        grade, cdl, constant,
        over, merge, shuffle,
        blur, sharpen,
        transform, crop,
        roto,
        reroute,
        viewer,
        node_panel,
    ]


# Node categories for the Add menu
_category_name = "OC_NODE_CATEGORIES"


def register():
    from .node_graph import tree, sockets
    tree.register()
    sockets.register()

    # Register all node classes
    global _node_modules
    _node_modules = _import_nodes()
    for mod in _node_modules:
        mod.register()

    # Register custom Add menu classes (Blender 5.0 compatible)
    for cls in _add_menu_classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

    # Append our menu to NODE_MT_add
    try:
        bpy.types.NODE_MT_add.append(_draw_opencomp_add_menu)
    except Exception:
        pass

    # Register UI panels
    bpy.utils.register_class(OC_PT_active_node)
    bpy.utils.register_class(OC_PT_active_node_properties)

    # Register native GPU node canvas (replaces Qt canvas)
    from .node_canvas import operators as canvas_ops
    canvas_ops.register()

    # Register NodeGraphQt integration (direct Python bridge)
    try:
        from .nodegraph import qt_integration
        qt_integration.register()
    except ImportError as e:
        console.info(f"NodeGraphQt integration not available: {e}")

    # DISABLED: Custom timeline UI (using native Blender timeline instead)
    # from . import ui
    # ui.register()

    # Print startup banner
    console.print_startup_banner(
        f"{bl_info['version'][0]}.{bl_info['version'][1]}.{bl_info['version'][2]}"
    )
    console.registered("OpenComp add-on")

    # Override node editor menus
    _override_node_add_menu()
    _override_node_context_menu()


def unregister():
    # Clear GPU shader cache first
    from .gpu_pipeline import executor
    executor.clear_cache()

    # Restore node editor menus
    _restore_node_add_menu()
    _restore_node_context_menu()

    # DISABLED: Custom timeline UI
    # from . import ui
    # ui.unregister()
    pass

    # Unregister NodeGraphQt integration
    try:
        from .nodegraph import qt_integration
        qt_integration.unregister()
    except ImportError:
        pass

    # Unregister native GPU node canvas
    from .node_canvas import operators as canvas_ops
    canvas_ops.unregister()

    # Unregister UI panels
    for cls in (OC_PT_active_node_properties, OC_PT_active_node):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    # Remove our menu from NODE_MT_add
    try:
        bpy.types.NODE_MT_add.remove(_draw_opencomp_add_menu)
    except Exception:
        pass

    # Unregister custom Add menu classes
    for cls in reversed(_add_menu_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    # Unregister all node classes (reverse order)
    for mod in reversed(_node_modules):
        mod.unregister()

    from .node_graph import sockets, tree
    sockets.unregister()
    tree.unregister()
