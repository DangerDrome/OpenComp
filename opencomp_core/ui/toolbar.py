"""OpenComp Toolbar — Nuke-style top toolbar.

Replaces Blender's top bar with OpenComp menus and tools.
All UI is GPU-drawn to completely replace Blender's look.
"""

import bpy
from bpy.types import Header, Menu
import gpu
from gpu_extras.batch import batch_for_shader
import blf


_topbar_draw_handler = None


def _draw_topbar_overlay():
    """Draw custom GPU topbar."""
    context = bpy.context
    if context.area is None or context.area.type != 'TOPBAR':
        return

    # Find header region
    region = None
    for r in context.area.regions:
        if r.type == 'WINDOW':
            region = r
            break

    if region is None or region.height < 5:
        return

    scene = context.scene
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    # Draw dark background
    verts = [(0, 0), (region.width, 0), (region.width, region.height), (0, region.height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", (0.18, 0.18, 0.18, 1.0))
    batch.draw(shader)

    x = 15
    y = (region.height - 14) // 2 + 3

    # OpenComp logo/name
    blf.size(0, 15)
    blf.color(0, 0.2, 0.55, 0.35, 1.0)  # OpenComp accent
    blf.position(0, x, y, 0)
    blf.draw(0, "OpenComp")
    x += 100

    # Separator
    sep_verts = [(x, 8), (x, region.height - 8)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 20

    # Menu items
    blf.size(0, 12)
    menus = ["File", "Edit", "Node", "Render", "Window", "Help"]

    for menu in menus:
        blf.color(0, 0.75, 0.75, 0.75, 1.0)
        blf.position(0, x, y, 0)
        blf.draw(0, menu)
        text_width, _ = blf.dimensions(0, menu)
        x += text_width + 25

    # Right side - project info
    info_text = f"{scene.render.resolution_x}x{scene.render.resolution_y} @ {scene.render.fps}fps"
    text_width, _ = blf.dimensions(0, info_text)
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    blf.position(0, region.width - text_width - 20, y, 0)
    blf.draw(0, info_text)

    gpu.state.blend_set('NONE')


class OC_MT_file_menu(Menu):
    """OpenComp File menu."""
    bl_label = "File"
    bl_idname = "OC_MT_file_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("wm.read_homefile", text="New", icon='FILE_NEW')
        layout.operator("wm.open_mainfile", text="Open...", icon='FILE_FOLDER')

        layout.separator()

        layout.operator("wm.save_mainfile", text="Save", icon='FILE_TICK')
        layout.operator("wm.save_as_mainfile", text="Save As...", icon='FILE_BACKUP')

        layout.separator()

        layout.menu("OC_MT_import_menu", text="Import", icon='IMPORT')
        layout.menu("OC_MT_export_menu", text="Export", icon='EXPORT')

        layout.separator()

        layout.operator("wm.quit_blender", text="Quit", icon='QUIT')


class OC_MT_import_menu(Menu):
    """Import submenu."""
    bl_label = "Import"
    bl_idname = "OC_MT_import_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("wm.open_mainfile", text="OpenComp Project (.blend)")
        layout.separator()
        layout.label(text="Image Sequences...")
        layout.label(text="EXR...")
        layout.label(text="Nuke Script (.nk)...")


class OC_MT_export_menu(Menu):
    """Export submenu."""
    bl_label = "Export"
    bl_idname = "OC_MT_export_menu"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Render to File...")
        layout.separator()
        layout.label(text="Nuke Script (.nk)...")


class OC_MT_edit_menu(Menu):
    """OpenComp Edit menu."""
    bl_label = "Edit"
    bl_idname = "OC_MT_edit_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("ed.undo", text="Undo", icon='LOOP_BACK')
        layout.operator("ed.redo", text="Redo", icon='LOOP_FORWARDS')

        layout.separator()

        layout.operator("wm.search_menu", text="Search...", icon='VIEWZOOM')

        layout.separator()

        layout.operator("wm.window_fullscreen_toggle", text="Toggle Fullscreen")


class OC_MT_node_menu(Menu):
    """OpenComp Node menu."""
    bl_label = "Node"
    bl_idname = "OC_MT_node_menu"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Add Nodes:", icon='NODE')
        layout.separator()

        # IO nodes
        layout.label(text="Input/Output")
        layout.operator("oc.canvas_add_node", text="Read")
        layout.operator("oc.canvas_add_node", text="Write")
        layout.operator("oc.canvas_add_node", text="Viewer")

        layout.separator()

        # Color nodes
        layout.label(text="Color")
        layout.operator("oc.canvas_add_node", text="Grade")
        layout.operator("oc.canvas_add_node", text="ColorCorrect")
        layout.operator("oc.canvas_add_node", text="Saturation")

        layout.separator()

        # Merge nodes
        layout.label(text="Merge")
        layout.operator("oc.canvas_add_node", text="Merge")
        layout.operator("oc.canvas_add_node", text="Over")

        layout.separator()

        # Transform
        layout.label(text="Transform")
        layout.operator("oc.canvas_add_node", text="Transform")
        layout.operator("oc.canvas_add_node", text="Crop")

        layout.separator()

        # Filter
        layout.label(text="Filter")
        layout.operator("oc.canvas_add_node", text="Blur")
        layout.operator("oc.canvas_add_node", text="Sharpen")


class OC_MT_render_menu(Menu):
    """OpenComp Render menu."""
    bl_label = "Render"
    bl_idname = "OC_MT_render_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("render.render", text="Render Frame", icon='RENDER_STILL')
        layout.operator("render.render", text="Render Animation", icon='RENDER_ANIMATION').animation = True

        layout.separator()

        layout.label(text="Render Settings...", icon='PREFERENCES')


class OC_MT_window_menu(Menu):
    """OpenComp Window menu."""
    bl_label = "Window"
    bl_idname = "OC_MT_window_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("wm.window_new", text="New Window", icon='WINDOW')
        layout.operator("wm.window_fullscreen_toggle", text="Toggle Fullscreen")

        layout.separator()

        layout.label(text="Layouts:", icon='WORKSPACE')
        layout.operator("workspace.append_activate", text="Compositing")
        layout.operator("workspace.append_activate", text="Review")


class OC_MT_help_menu(Menu):
    """OpenComp Help menu."""
    bl_label = "Help"
    bl_idname = "OC_MT_help_menu"

    def draw(self, context):
        layout = self.layout

        layout.label(text="OpenComp v0.1.0", icon='INFO')
        layout.separator()
        layout.operator("wm.url_open", text="Documentation").url = "https://github.com/opencomp"
        layout.operator("wm.url_open", text="Report Bug").url = "https://github.com/opencomp/issues"


class OC_HT_topbar(Header):
    """Empty topbar header - we draw our own via GPU."""
    bl_space_type = 'TOPBAR'

    def draw(self, context):
        # Draw minimal menu triggers that work with our menus
        layout = self.layout

        # These invisible menu triggers make the menus work when clicking on our GPU text
        row = layout.row(align=True)
        row.menu("OC_MT_file_menu", text="")
        row.menu("OC_MT_edit_menu", text="")
        row.menu("OC_MT_node_menu", text="")
        row.menu("OC_MT_render_menu", text="")
        row.menu("OC_MT_window_menu", text="")
        row.menu("OC_MT_help_menu", text="")


# Classes to register
classes = [
    OC_MT_file_menu,
    OC_MT_import_menu,
    OC_MT_export_menu,
    OC_MT_edit_menu,
    OC_MT_node_menu,
    OC_MT_render_menu,
    OC_MT_window_menu,
    OC_MT_help_menu,
    OC_HT_topbar,
]


def register():
    global _topbar_draw_handler

    for cls in classes:
        bpy.utils.register_class(cls)

    # Register draw handler for topbar (if available)
    try:
        _topbar_draw_handler = bpy.types.SpaceTopBar.draw_handler_add(
            _draw_topbar_overlay, (), 'WINDOW', 'POST_PIXEL'
        )
    except AttributeError:
        # SpaceTopBar not available in this Blender version
        _topbar_draw_handler = None

    # DISABLED for v0.2: Keep default topbar visible
    # try:
    #     bpy.utils.unregister_class(bpy.types.TOPBAR_HT_upper_bar)
    # except:
    #     pass

    # try:
    #     bpy.utils.unregister_class(bpy.types.TOPBAR_MT_editor_menus)
    # except:
    #     pass
    pass


def unregister():
    global _topbar_draw_handler

    if _topbar_draw_handler:
        bpy.types.SpaceTopBar.draw_handler_remove(_topbar_draw_handler, 'WINDOW')
        _topbar_draw_handler = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
