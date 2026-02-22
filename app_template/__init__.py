"""OpenComp App Template — transforms Blender into a VFX compositor UI.

Overrides the default Blender interface to present a Nuke-like compositor.
Applied when launching with: blender --app-template OpenComp

- Override TOPBAR_HT_upper_bar draw function (OpenComp menus, not Blender)
- Override VIEW3D_HT_header draw function (viewer controls in header)
- Override WM_MT_splash draw function (OpenComp splash, no Blender links)
- Multi-panel Nuke-style layout: Viewer (VIEW_3D) + Node Graph + Properties
- Hide chrome (T-panel, N-panel) on compositor areas
- Apply dark theme
- startup.blend generated programmatically via _generate_startup.py
"""

import bpy
from bpy.app.handlers import persistent


# ── Version ────────────────────────────────────────────────────────────

_OC_VERSION = "v0.4.0"

# ── Original draw function storage ──────────────────────────────────────

_original_topbar_draw = None
_original_view3d_header_draw = None
_original_splash_draw = None
_original_splash_about_draw = None
_original_splash_quick_setup_draw = None


# ── Custom Menus ─────────────────────────────────────────────────────────

class OC_MT_file(bpy.types.Menu):
    """OpenComp File menu."""
    bl_idname = "OC_MT_file"
    bl_label = "File"

    def draw(self, context):
        layout = self.layout
        layout.operator("wm.open_mainfile", text="Open...")
        layout.operator("wm.save_mainfile", text="Save")
        layout.operator("wm.save_as_mainfile", text="Save As...")
        layout.separator()
        layout.operator("wm.read_homefile", text="New")
        layout.separator()
        layout.menu("TOPBAR_MT_file_import", text="Import")
        layout.menu("TOPBAR_MT_file_export", text="Export")
        layout.separator()
        layout.operator("wm.save_homefile", text="Save Startup Layout")
        layout.separator()
        layout.operator("wm.quit_blender", text="Quit")


class OC_MT_edit(bpy.types.Menu):
    """OpenComp Edit menu."""
    bl_idname = "OC_MT_edit"
    bl_label = "Edit"

    def draw(self, context):
        layout = self.layout
        layout.operator("ed.undo", text="Undo")
        layout.operator("ed.redo", text="Redo")
        layout.separator()
        layout.operator("screen.userpref_show", text="Preferences...")


class OC_MT_view(bpy.types.Menu):
    """OpenComp View menu."""
    bl_idname = "OC_MT_view"
    bl_label = "View"

    def draw(self, context):
        layout = self.layout
        layout.operator("screen.screen_full_area", text="Toggle Fullscreen")
        layout.separator()
        layout.operator("wm.window_new", text="New Window")


class OC_OT_splash_about(bpy.types.Operator):
    """Show the OpenComp About dialog."""
    bl_idname = "oc.splash_about"
    bl_label = "About OpenComp"

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=360)

    def draw(self, context):
        layout = self.layout

        # Branding
        layout.label(text="OpenComp", icon='NODE_COMPOSITING')
        layout.label(text=_OC_VERSION)
        layout.separator()

        # Description
        col = layout.column(align=True)
        col.label(text="Open Source VFX Compositor")
        col.label(text="Built as a Blender 5.x add-on")
        col.separator()

        # Tech stack
        col.label(text="Python + GLSL  |  GPU-accelerated")
        col.label(text="OCIO colour management  |  OIIO file I/O")
        col.separator()

        # License
        col.label(text="License: GPL 3.0")


class OC_MT_help(bpy.types.Menu):
    """OpenComp Help menu."""
    bl_idname = "OC_MT_help"
    bl_label = "Help"

    def draw(self, context):
        layout = self.layout
        layout.operator("oc.splash_about", text="About OpenComp")


class OC_OT_show_add_menu(bpy.types.Operator):
    """Show the node add menu at cursor position."""
    bl_idname = "oc.show_add_menu"
    bl_label = "Add Node"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'NODE_EDITOR' and
                space.tree_type == "OC_NT_compositor")

    def invoke(self, context, event):
        # Store cursor location for node placement
        try:
            view2d = context.region.view2d
            loc = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
            context.space_data.cursor_location = loc
        except:
            pass
        bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="NODE_MT_add")
        return {'FINISHED'}


# ── Link Drag with Menu ────────────────────────────────────────────────
# Custom link dragging that shows menu on release and keeps line visible

import gpu
from gpu_extras.batch import batch_for_shader

# Global state for the link drag
_link_drag = {
    'active': False,
    'source_socket': None,
    'source_node': None,
    'source_pos': (0, 0),
    'end_pos': (0, 0),
    'tree': None,
    'draw_handler': None,
    'waiting_for_menu': False,
}


def _get_socket_position(node, socket, is_output):
    """Get the screen position of a socket."""
    # Node location is the top-left corner
    x = node.location.x
    y = node.location.y

    if is_output:
        x += node.width

    # Find socket index
    sockets = node.outputs if is_output else node.inputs
    idx = 0
    for i, s in enumerate(sockets):
        if s == socket:
            idx = i
            break

    # Approximate Y position (sockets are below the header)
    y -= 35 + (idx * 22)

    return (x, y)


def _draw_temp_link():
    """Draw the temporary link line."""
    state = _link_drag
    if not state['active'] and not state['waiting_for_menu']:
        return

    start = state['source_pos']
    end = state['end_pos']

    # Create shader and batch for a line
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)

    shader.bind()
    shader.uniform_float("color", (1.0, 0.6, 0.2, 0.9))  # Orange link color
    shader.uniform_float("lineWidth", 2.0)
    shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])

    # Draw bezier-ish curve (simplified as line segments)
    points = []
    segments = 20
    dx = end[0] - start[0]

    for i in range(segments + 1):
        t = i / segments
        # Bezier control points for a nice curve
        cx1 = start[0] + dx * 0.4
        cx2 = end[0] - dx * 0.4

        # Cubic bezier
        x = (1-t)**3 * start[0] + 3*(1-t)**2*t * cx1 + 3*(1-t)*t**2 * cx2 + t**3 * end[0]
        y = (1-t)**3 * start[1] + 3*(1-t)**2*t * start[1] + 3*(1-t)*t**2 * end[1] + t**3 * end[1]
        points.append((x, y))

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    batch.draw(shader)

    gpu.state.blend_set('NONE')


class OC_OT_link_drag(bpy.types.Operator):
    """Drag to create link. Shows add menu when released in empty space."""
    bl_idname = "oc.link_drag"
    bl_label = "Link Drag"
    bl_options = {'REGISTER', 'UNDO'}

    detach: bpy.props.BoolProperty(name="Detach", default=False)

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'NODE_EDITOR' and
                space.tree_type == "OC_NT_compositor")

    def invoke(self, context, event):
        state = _link_drag
        tree = context.space_data.edit_tree
        if not tree:
            return {'CANCELLED'}

        # Find socket under cursor
        socket, node, is_output = self._find_socket_at_cursor(context, event)
        if not socket:
            # No socket under cursor, use default behavior
            return bpy.ops.node.link('INVOKE_DEFAULT', detach=self.detach)

        # Initialize drag state
        state['active'] = True
        state['source_socket'] = socket
        state['source_node'] = node
        state['source_pos'] = _get_socket_position(node, socket, is_output)
        state['end_pos'] = state['source_pos']
        state['tree'] = tree
        state['waiting_for_menu'] = False
        state['is_output'] = is_output

        # Add draw handler
        if state['draw_handler'] is None:
            state['draw_handler'] = bpy.types.SpaceNodeEditor.draw_handler_add(
                _draw_temp_link, (), 'WINDOW', 'POST_VIEW'
            )

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        state = _link_drag
        context.area.tag_redraw()

        if state['waiting_for_menu']:
            # We're waiting for menu selection - pass through most events
            # Only cancel on ESC
            if event.type == 'ESC' and event.value == 'PRESS':
                self._cleanup(context)
                return {'CANCELLED'}

            return {'PASS_THROUGH'}

        # Update end position during drag
        if event.type == 'MOUSEMOVE':
            view2d = context.region.view2d
            state['end_pos'] = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)

        # Check for release
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # Check if we're over another socket
            target_socket, target_node, target_is_output = self._find_socket_at_cursor(context, event)

            if target_socket and target_node != state['source_node']:
                # Connect to this socket
                tree = state['tree']
                try:
                    if state['is_output']:
                        tree.links.new(state['source_socket'], target_socket)
                    else:
                        tree.links.new(target_socket, state['source_socket'])
                except:
                    pass
                self._cleanup(context)
                return {'FINISHED'}
            else:
                # Released in empty space - show menu, keep line visible
                state['waiting_for_menu'] = True
                state['active'] = False

                # Store cursor position for new node
                view2d = context.region.view2d
                loc = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
                context.space_data.cursor_location = loc

                # Store nodes before menu
                self._nodes_before = set(n.name for n in state['tree'].nodes)

                # Show the add menu
                bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="NODE_MT_add")

                # Start checking for new node
                bpy.app.timers.register(
                    lambda: self._check_for_new_node(context),
                    first_interval=0.05
                )

                return {'RUNNING_MODAL'}

        # Cancel on right click or escape
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self._cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _check_for_new_node(self, context):
        """Timer to check if user selected a node from menu."""
        state = _link_drag

        # Increment check count for timeout
        if not hasattr(self, '_menu_check_count'):
            self._menu_check_count = 0
        self._menu_check_count += 1

        # Timeout after ~3 seconds (60 * 50ms)
        if self._menu_check_count > 60 or not state['waiting_for_menu']:
            self._cleanup(context)
            return None

        tree = state['tree']
        if not tree:
            self._cleanup(context)
            return None

        # Check for new node
        for node in tree.nodes:
            if node.name not in self._nodes_before:
                # New node created - link it
                self._create_link(state, node)
                self._cleanup(context)
                return None

        # Keep checking
        return 0.05

    def _create_link(self, state, new_node):
        """Create a link between source socket and new node."""
        tree = state['tree']
        socket = state['source_socket']

        try:
            if state['is_output']:
                # Source is output, connect to new node's input
                for inp in new_node.inputs:
                    if inp.enabled:
                        tree.links.new(socket, inp)
                        break
            else:
                # Source is input, connect from new node's output
                for out in new_node.outputs:
                    if out.enabled:
                        tree.links.new(out, socket)
                        break
        except Exception as e:
            print(f"[OpenComp] Link creation failed: {e}")

    def _cleanup(self, context):
        """Clean up drag state and remove draw handler."""
        state = _link_drag
        state['active'] = False
        state['waiting_for_menu'] = False
        state['source_socket'] = None

        if state['draw_handler']:
            bpy.types.SpaceNodeEditor.draw_handler_remove(state['draw_handler'], 'WINDOW')
            state['draw_handler'] = None

        if context.area:
            context.area.tag_redraw()

    def _find_socket_at_cursor(self, context, event):
        """Find socket under cursor. Returns (socket, node, is_output) or (None, None, None)."""
        tree = context.space_data.edit_tree
        if not tree:
            return None, None, None

        view2d = context.region.view2d
        mx, my = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)

        for node in tree.nodes:
            loc = node.location

            # Check outputs
            for i, socket in enumerate(node.outputs):
                if socket.enabled:
                    sx = loc.x + node.width
                    sy = loc.y - 35 - (i * 22)
                    if abs(mx - sx) < 20 and abs(my - sy) < 15:
                        return socket, node, True

            # Check inputs
            for i, socket in enumerate(node.inputs):
                if socket.enabled:
                    sx = loc.x
                    sy = loc.y - 35 - (i * 22)
                    if abs(mx - sx) < 20 and abs(my - sy) < 15:
                        return socket, node, False

        return None, None, None


# ── Add and Link operator (Tab key workflow) ────────────────────────────
# Track the last active node for Tab-based linking

_last_active_node = None


@persistent
def _track_active_node(dummy):
    """Track the active node for Tab key connection workflow."""
    global _last_active_node
    try:
        for area in bpy.context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR' and space.tree_type == "OC_NT_compositor":
                        tree = space.edit_tree
                        if tree and tree.nodes.active:
                            _last_active_node = tree.nodes.active.name
                        return
    except:
        pass


class OC_OT_add_and_link(bpy.types.Operator):
    """Show add menu and auto-connect to the active node's output."""
    bl_idname = "oc.add_and_link"
    bl_label = "Add and Link Node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (space and space.type == 'NODE_EDITOR' and
                space.tree_type == "OC_NT_compositor")

    def invoke(self, context, event):
        global _last_active_node
        tree = context.space_data.edit_tree
        if not tree:
            return {'CANCELLED'}

        # Store active node before menu
        self._source_node_name = _last_active_node
        self._nodes_before = set(n.name for n in tree.nodes)
        self._tree = tree

        # Store cursor position for new node placement
        try:
            view2d = context.region.view2d
            loc = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
            context.space_data.cursor_location = loc
        except:
            pass

        # Show add menu
        bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="NODE_MT_add")

        # Start checking for new node
        bpy.app.timers.register(
            lambda: self._check_for_new_node(context),
            first_interval=0.05
        )

        return {'FINISHED'}

    def _check_for_new_node(self, context):
        """Timer to check if user added a node from menu."""
        tree = self._tree
        if not tree:
            return None

        # Check for new node
        for node in tree.nodes:
            if node.name not in self._nodes_before:
                # New node created - link it to active node's output
                self._auto_link(tree, node)
                return None

        # Keep checking (up to ~2 seconds)
        if not hasattr(self, '_check_count'):
            self._check_count = 0
        self._check_count += 1
        if self._check_count > 40:
            return None
        return 0.05

    def _auto_link(self, tree, new_node):
        """Link new node's input to the source node's output."""
        if not self._source_node_name:
            return

        source_node = tree.nodes.get(self._source_node_name)
        if not source_node:
            return

        # Find first enabled output on source
        source_socket = None
        for out in source_node.outputs:
            if out.enabled:
                source_socket = out
                break

        if not source_socket:
            return

        # Find first enabled input on new node
        for inp in new_node.inputs:
            if inp.enabled:
                try:
                    tree.links.new(source_socket, inp)
                except:
                    pass
                break


_menu_classes = [
    OC_MT_file,
    OC_MT_edit,
    OC_MT_view,
    OC_MT_help,
]

_operator_classes = [
    OC_OT_splash_about,
    OC_OT_show_add_menu,
    OC_OT_link_drag,
    OC_OT_add_and_link,
]


# ── TOPBAR Override ─────────────────────────────────────────────────────

def _opencomp_topbar_draw(self, context):
    """Replace Blender's top bar with OpenComp branding and menus."""
    layout = self.layout
    region = context.region

    if region.alignment == 'RIGHT':
        # Right side: scene and view layer selectors (keep useful)
        window = context.window
        scene = window.scene
        layout.template_ID(window, "scene", new="scene.new",
                           unlink="scene.delete")
        row = layout.row(align=True)
        row.template_search(
            window, "view_layer",
            scene, "view_layers",
            new="scene.view_layer_add",
            unlink="scene.view_layer_remove",
        )
    else:
        # Left side: OpenComp branding + custom menus (no workspace tabs)
        layout.label(text="OpenComp", icon='NODE_COMPOSITING')
        layout.separator(type='LINE')
        layout.menu("OC_MT_file")
        layout.menu("OC_MT_edit")
        layout.menu("OC_MT_view")
        layout.menu("OC_MT_help")
        layout.separator_spacer()
        row = layout.row(align=True)
        row.label(text=_OC_VERSION)


def _override_topbar():
    """Replace TOPBAR_HT_upper_bar draw with OpenComp version."""
    global _original_topbar_draw
    try:
        topbar_cls = bpy.types.TOPBAR_HT_upper_bar
        _original_topbar_draw = topbar_cls.draw
        topbar_cls.draw = _opencomp_topbar_draw
    except Exception as e:
        print(f"[OpenComp] TOPBAR override skipped: {e}")


def _restore_topbar():
    """Restore original TOPBAR draw function."""
    global _original_topbar_draw
    if _original_topbar_draw is not None:
        try:
            bpy.types.TOPBAR_HT_upper_bar.draw = _original_topbar_draw
            _original_topbar_draw = None
        except Exception:
            pass


# ── VIEW3D Header Override ──────────────────────────────────────────────

def _operator_exists(idname):
    """Check if a Blender operator is registered (avoids rna_uiItemO warnings).

    bpy.ops creates dynamic proxies so hasattr() always returns True there.
    The reliable check is against bpy.types where RNA structs only exist
    after bpy.utils.register_class().
    """
    # "oc.viewer_fit" → "OC_OT_viewer_fit"
    parts = idname.split(".", 1)
    if len(parts) != 2:
        return False
    cls_name = parts[0].upper() + "_OT_" + parts[1]
    return hasattr(bpy.types, cls_name)


def _opencomp_view3d_header_draw(self, context):
    """Replace the 3D viewport header with OpenComp viewer controls."""
    layout = self.layout

    try:
        settings = context.scene.oc_viewer
    except AttributeError:
        # Fallback to original if oc_viewer not registered yet
        if _original_view3d_header_draw is not None:
            _original_view3d_header_draw(self, context)
        return

    # Import viewer state for zoom display
    try:
        from opencomp_core.nodes.viewer.viewer import _viewer_state
        zoom = _viewer_state.get("zoom", 1.0)
    except ImportError:
        zoom = 1.0

    layout.separator()

    # Left: Channel buttons (expanded enum row)
    row = layout.row(align=True)
    row.label(text="Ch:")
    row.prop(settings, "channel_mode", expand=True)

    layout.separator(type='LINE')

    # Center: Gain + Gamma sliders (compact)
    row = layout.row(align=True)
    row.prop(settings, "gain", text="Gain")
    row.prop(settings, "gamma", text="Gamma")

    layout.separator(type='LINE')

    # Right: False Color + Clipping toggles
    row = layout.row(align=True)
    row.prop(settings, "false_color", toggle=True, text="FC")
    row.prop(settings, "clipping", toggle=True, text="Clip")

    layout.separator(type='LINE')

    # Background mode
    row = layout.row(align=True)
    row.label(text="BG:")
    row.prop(settings, "bg_mode", text="")

    layout.separator(type='LINE')

    # Proxy resolution
    row = layout.row(align=True)
    row.label(text="Proxy:")
    row.prop(settings, "proxy", text="")

    layout.separator()

    # Zoom display
    row = layout.row(align=True)
    row.label(text=f"{int(zoom * 100)}%")

    # Fit / Reset — operators may not be registered yet (addon loads after template)
    row = layout.row(align=True)
    if _operator_exists("oc.viewer_fit"):
        row.operator("oc.viewer_fit", text="", icon='FULLSCREEN_ENTER')
    if _operator_exists("oc.viewer_reset"):
        row.operator("oc.viewer_reset", text="", icon='HOME')


def _override_view3d_header():
    """Replace VIEW3D_HT_header draw with OpenComp viewer controls."""
    global _original_view3d_header_draw
    try:
        header_cls = bpy.types.VIEW3D_HT_header
        _original_view3d_header_draw = header_cls.draw
        header_cls.draw = _opencomp_view3d_header_draw
    except Exception as e:
        print(f"[OpenComp] VIEW3D header override skipped: {e}")


def _restore_view3d_header():
    """Restore original VIEW3D_HT_header draw function."""
    global _original_view3d_header_draw
    if _original_view3d_header_draw is not None:
        try:
            bpy.types.VIEW3D_HT_header.draw = _original_view3d_header_draw
            _original_view3d_header_draw = None
        except Exception:
            pass


# ── Splash Screen Override ─────────────────────────────────────────────

def _opencomp_splash_draw(self, context):
    """Replace Blender's splash menu with OpenComp content."""
    layout = self.layout
    layout.operator_context = 'EXEC_DEFAULT'
    layout.emboss = 'PULLDOWN_MENU'

    split = layout.split()

    # Left column: actions
    col1 = split.column()
    col1.label(text="OpenComp " + _OC_VERSION)
    col1.separator()
    col1.operator_context = 'INVOKE_DEFAULT'
    col1.operator("wm.open_mainfile", text="Open...", icon='FILE_FOLDER')
    col1.operator("wm.recover_last_session", text="Recover Session", icon='RECOVER_LAST')

    # Right column: recent files
    col2 = split.column()
    found_recent = col2.template_recent_files(rows=5)
    if found_recent:
        col2.label(text="Recent Files")
    else:
        col2.label(text="No recent files")

    layout.separator()


def _override_splash():
    """Replace WM_MT_splash draw with OpenComp version."""
    global _original_splash_draw
    try:
        cls = bpy.types.WM_MT_splash
        _original_splash_draw = cls.draw
        cls.draw = _opencomp_splash_draw
    except Exception as e:
        print(f"[OpenComp] Splash override skipped: {e}")


def _restore_splash():
    """Restore original WM_MT_splash draw function."""
    global _original_splash_draw
    if _original_splash_draw is not None:
        try:
            bpy.types.WM_MT_splash.draw = _original_splash_draw
            _original_splash_draw = None
        except Exception:
            pass


# ── Splash About Override ──────────────────────────────────────────────

def _opencomp_splash_about_draw(self, context):
    """Replace Blender's splash about with OpenComp branding."""
    layout = self.layout

    # OpenComp branding instead of Blender logo
    col = layout.column(align=True)
    col.scale_y = 1.5
    col.label(text="OpenComp", icon='NODE_COMPOSITING')
    col.label(text=_OC_VERSION)

    layout.separator()

    col = layout.column(align=True)
    col.label(text="Open Source VFX Compositor")
    col.label(text="GPU-accelerated  |  OCIO colour  |  OIIO I/O")

    layout.separator()


def _override_splash_about():
    """Replace WM_MT_splash_about draw with OpenComp version."""
    global _original_splash_about_draw
    try:
        cls = bpy.types.WM_MT_splash_about
        _original_splash_about_draw = cls.draw
        cls.draw = _opencomp_splash_about_draw
    except Exception as e:
        print(f"[OpenComp] Splash about override skipped: {e}")


def _restore_splash_about():
    """Restore original WM_MT_splash_about draw function."""
    global _original_splash_about_draw
    if _original_splash_about_draw is not None:
        try:
            bpy.types.WM_MT_splash_about.draw = _original_splash_about_draw
            _original_splash_about_draw = None
        except Exception:
            pass


# ── Quick Setup Override ───────────────────────────────────────────────

def _opencomp_quick_setup_draw(self, context):
    """Replace Blender's Quick Setup with nothing — OpenComp needs no setup."""
    # Empty draw — no quick setup needed for OpenComp
    # User just sees the splash with recent files, no configuration wizard
    pass


def _override_quick_setup():
    """Replace WM_MT_splash_quick_setup draw with empty version."""
    global _original_splash_quick_setup_draw
    try:
        cls = bpy.types.WM_MT_splash_quick_setup
        _original_splash_quick_setup_draw = cls.draw
        cls.draw = _opencomp_quick_setup_draw
    except Exception as e:
        print(f"[OpenComp] Quick setup override skipped: {e}")


def _restore_quick_setup():
    """Restore original WM_MT_splash_quick_setup draw function."""
    global _original_splash_quick_setup_draw
    if _original_splash_quick_setup_draw is not None:
        try:
            bpy.types.WM_MT_splash_quick_setup.draw = _original_splash_quick_setup_draw
            _original_splash_quick_setup_draw = None
        except Exception:
            pass


# ── Qt Canvas Auto-Launch ──────────────────────────────────────────────

def _launch_qt_canvas():
    """Auto-launch the Qt canvas — the primary node editor for OpenComp.

    The Qt canvas runs as a separate process and is THE node editor.
    Blender's built-in node editor is only used as a fallback/sync target.
    """
    try:
        from opencomp_core.qt_canvas.blender_launch import launch_canvas

        # Launch the Qt canvas (non-blocking, fire and forget)
        launch_canvas()

    except ImportError as e:
        print(f"[OpenComp] Qt canvas not available: {e}")
        print("[OpenComp] Install PySide6 and NodeGraphQt-QuiltiX-fork:")
        print("           pip3 install PySide6 NodeGraphQt-QuiltiX-fork")
    except Exception as e:
        print(f"[OpenComp] Qt canvas launch error: {e}")


# ── Window Title ───────────────────────────────────────────────────────

def _set_window_title():
    """Best-effort replace 'Blender 5.x.x' window title with OpenComp.

    Uses xdotool on Linux/X11. Fails silently on Wayland or if unavailable.
    """
    import sys
    if sys.platform != 'linux':
        return

    import subprocess, os
    title = f"OpenComp {_OC_VERSION}"
    try:
        subprocess.Popen(
            ['xdotool', 'search', '--pid', str(os.getpid()),
             '--name', 'Blender', 'set_window', '--name', title],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # xdotool not installed — try xprop fallback
        try:
            result = subprocess.run(
                ['xprop', '-root', '_NET_CLIENT_LIST'],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                for token in result.stdout.replace(',', ' ').split():
                    if token.startswith('0x'):
                        check = subprocess.run(
                            ['xprop', '-id', token, '_NET_WM_PID'],
                            capture_output=True, text=True, timeout=1,
                        )
                        if str(os.getpid()) in check.stdout:
                            subprocess.run(
                                ['xprop', '-id', token, '-f', '_NET_WM_NAME',
                                 '8u', '-set', '_NET_WM_NAME', title],
                                timeout=1,
                            )
                            break
        except Exception:
            pass
    except Exception:
        pass


# ── Hide built-in Properties panels ────────────────────────────────────

_hidden_scene_panels = []


def _hide_builtin_scene_panels():
    """Unregister all built-in 'scene' context panels from the Properties area.

    This leaves only our OC_PT_* panels visible. Panels are restored on
    unregister so regular Blender isn't affected.
    """
    global _hidden_scene_panels
    for name in dir(bpy.types):
        if name.startswith('OC_'):
            continue
        cls = getattr(bpy.types, name, None)
        if cls is None:
            continue
        if (getattr(cls, 'bl_space_type', None) == 'PROPERTIES'
                and getattr(cls, 'bl_context', None) == 'scene'):
            try:
                bpy.utils.unregister_class(cls)
                _hidden_scene_panels.append(cls)
            except Exception:
                pass


def _restore_builtin_scene_panels():
    """Re-register built-in scene panels that were hidden."""
    global _hidden_scene_panels
    for cls in _hidden_scene_panels:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            pass
    _hidden_scene_panels = []


# ── UI Configuration ───────────────────────────────────────────────────

def _configure_area_chrome():
    """Hide toolbar and sidebar on all compositor areas. Keep headers for menus."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        space.show_region_toolbar = False
                        space.show_region_ui = False
            elif area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.show_region_toolbar = False
                        space.show_region_ui = False
                        space.show_region_tool_header = False
                        space.show_gizmo = False
            elif area.type == 'DOPESHEET_EDITOR':
                for space in area.spaces:
                    if space.type == 'DOPESHEET_EDITOR':
                        space.show_region_ui = False
            elif area.type == 'PROPERTIES':
                for space in area.spaces:
                    if space.type == 'PROPERTIES':
                        space.context = 'SCENE'
                        space.show_region_header = False
        screen.show_statusbar = False


def _configure_viewer_area(area):
    """Configure a VIEW_3D area as the compositor viewer — clean, chrome-free."""
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            space.show_region_toolbar = False      # T-panel
            space.show_region_ui = False            # N-panel
            space.show_region_tool_header = False   # "Object Mode" bar
            space.show_gizmo = False                # all gizmos off
            space.overlay.show_overlays = False     # grid, axes, etc.
            space.shading.type = 'SOLID'


def _configure_node_editor_area(area):
    """Configure a NODE_EDITOR area for the OpenComp node graph."""
    for space in area.spaces:
        if space.type == 'NODE_EDITOR':
            space.show_region_toolbar = False
            space.show_region_ui = False
            space.tree_type = "OC_NT_compositor"


def _configure_properties_area(area, window=None):
    """Configure PROPERTIES area as a clean node-properties panel.

    Hides the header and navigation bar so only our OC_PT_active_node
    panels are visible in the WINDOW region — like Nuke's properties bin.
    Built-in scene panels are unregistered by _hide_builtin_scene_panels().
    """
    for space in area.spaces:
        if space.type == 'PROPERTIES':
            space.context = 'SCENE'
            space.show_region_header = False

    # Hide the navigation bar (left icon column) via region_toggle
    if window is not None:
        for region in area.regions:
            if region.type == 'NAVIGATION_BAR' and region.width > 1:
                try:
                    with bpy.context.temp_override(
                        window=window, area=area, region=region
                    ):
                        bpy.ops.screen.region_toggle(
                            region_type='NAVIGATION_BAR'
                        )
                except Exception:
                    pass
                break


def _ensure_opencomp_tree():
    """Create an OpenComp node tree if none exists and assign it to all Node Editor spaces."""
    tree_type = "OC_NT_compositor"

    # Find or create the tree
    oc_tree = None
    for tree in bpy.data.node_groups:
        if tree.bl_idname == tree_type:
            oc_tree = tree
            break
    if oc_tree is None:
        try:
            oc_tree = bpy.data.node_groups.new("OpenComp", tree_type)
        except Exception as e:
            print(f"[OpenComp] Could not create node tree: {e}")
            return

    # Assign to all Node Editor spaces
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        space.tree_type = tree_type
                        space.node_tree = oc_tree


def _configure_timeline_area(area, window=None):
    """Configure a DOPESHEET_EDITOR area as a Nuke-style timeline strip."""
    for space in area.spaces:
        if space.type == 'DOPESHEET_EDITOR':
            space.mode = 'TIMELINE'
            space.show_region_ui = False

    # Flip header to bottom so playback controls sit under the frame ruler
    if window is not None:
        for region in area.regions:
            if region.type == 'HEADER' and region.alignment != 'BOTTOM':
                try:
                    with bpy.context.temp_override(
                        window=window, area=area, region=region
                    ):
                        bpy.ops.screen.region_flip()
                except Exception:
                    pass
                break


def _try_split_timeline(window, screen):
    """Split the VIEW_3D area to insert a thin timeline strip below it.

    Layout result:
        ┌──────────────────┐
        │   VIEW_3D        │  ← viewer (large)
        ├──────────────────┤
        │   TIMELINE       │  ← thin strip (small, lowest y of the two)
        ├──────────────────┤
        │   NODE_EDITOR    │
        └──────────────────┘
    """
    # Don't split if a timeline already exists (saved startup has one)
    for area in screen.areas:
        if area.type == 'DOPESHEET_EDITOR':
            print("[OpenComp] Timeline already exists — skipping split")
            return

    view_area = None
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            view_area = area
            break
    if view_area is None:
        print("[OpenComp] No VIEW_3D found — skipping timeline split")
        return

    try:
        with bpy.context.temp_override(window=window, area=view_area, screen=screen):
            result = bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.08)
            if result != {'FINISHED'}:
                print("[OpenComp] area_split did not finish — skipping timeline")
                return
    except Exception as e:
        print(f"[OpenComp] Timeline split failed: {e}")
        return

    # After split there are two VIEW_3D areas.  The one with the lowest y
    # sits closest to NODE_EDITOR — that's where the timeline strip goes.
    view_areas = [a for a in screen.areas if a.type == 'VIEW_3D']
    if len(view_areas) < 2:
        print("[OpenComp] Could not identify split areas — skipping timeline")
        return

    view_areas.sort(key=lambda a: a.y)
    timeline_area = view_areas[0]  # lowest y → bottom strip
    timeline_area.type = 'DOPESHEET_EDITOR'
    _configure_timeline_area(timeline_area, window=window)
    print("[OpenComp] Timeline strip created below viewer")


_deferred_phase = 0
_deferred_setup_done = False


def _try_join_properties(window, screen):
    """Attempt to merge two PROPERTIES areas into one tall right panel.

    If the join fails (area_join is unreliable from scripts), convert the
    smaller area to OUTLINER in BLEND_FILE mode — useful for seeing images,
    node groups, and scene data at a glance.
    """
    props_areas = [a for a in screen.areas if a.type == 'PROPERTIES']
    if len(props_areas) < 2:
        return

    # Sort by y position (bottom first)
    props_areas.sort(key=lambda a: a.y)
    bot_area = props_areas[0]
    top_area = props_areas[1]

    # Blender 5.0 uses source_xy (area to keep) / target_xy (area to absorb)
    sx, sy = bot_area.x + bot_area.width // 2, bot_area.y + bot_area.height // 2
    tx, ty = top_area.x + top_area.width // 2, top_area.y + top_area.height // 2

    joined = False
    try:
        with bpy.context.temp_override(window=window, screen=screen):
            result = bpy.ops.screen.area_join(source_xy=(sx, sy), target_xy=(tx, ty))
            if result == {'FINISHED'}:
                joined = True
                print("[OpenComp] Joined PROPERTIES areas into one panel")
    except Exception:
        pass

    if not joined:
        # Fallback: convert the smaller (top) area to OUTLINER
        top_area.type = 'OUTLINER'
        for space in top_area.spaces:
            if space.type == 'OUTLINER':
                space.display_mode = 'LIBRARIES'
                space.show_region_header = False
        print("[OpenComp] Using Outliner + Properties dual panel layout")


def _deferred_ui_setup():
    """Deferred UI setup — runs via timer after window is fully ready.

    Three-phase approach:
      Phase 0: Try to join two PROPERTIES areas on the right into one column.
      Phase 1: Split NODE_EDITOR to insert a thin timeline strip above it.
      Phase 2: Configure all areas by type, assign tree, clean workspaces.

    Area proportions (viewer vs node graph) are baked into startup.blend
    by _generate_startup.py — no runtime adjustment needed.
    """
    global _deferred_phase, _deferred_setup_done

    if _deferred_setup_done:
        return None

    try:
        window = bpy.context.window
        if window is None:
            return 0.1  # retry

        screen = window.screen

        if _deferred_phase == 0:
            _deferred_phase = 1
            _try_join_properties(window, screen)
            return 0.1  # come back for phase 1

        if _deferred_phase == 1:
            _deferred_phase = 2
            _try_split_timeline(window, screen)
            return 0.1  # come back for phase 2

        # Phase 2 — configure every area by type
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                _configure_viewer_area(area)
            elif area.type == 'NODE_EDITOR':
                _configure_node_editor_area(area)
            elif area.type == 'PROPERTIES':
                _configure_properties_area(area, window=window)
            elif area.type == 'DOPESHEET_EDITOR':
                _configure_timeline_area(area, window=window)

        # Assign OpenComp node tree
        _ensure_opencomp_tree()

        # Remove extra workspaces
        if len(bpy.data.workspaces) > 1:
            with bpy.context.temp_override(window=window):
                bpy.ops.workspace.delete_all_others()

        # Hide status bar
        screen.show_statusbar = False

        # Replace OS window title (best-effort, X11 only)
        _set_window_title()

        # Auto-launch the Qt canvas (the primary node editor)
        print("[OpenComp] About to launch Qt canvas...")
        _launch_qt_canvas()
        print("[OpenComp] Qt canvas launch function returned")

        # Auto-save the configured layout as user startup so it persists
        try:
            bpy.ops.wm.save_homefile()
        except Exception:
            pass

        _deferred_setup_done = True

    except Exception as e:
        print(f"[OpenComp] Deferred UI setup: {e}")

    return None  # don't repeat


@persistent
def _configure_ui_on_load(dummy):
    """Configure UI after startup.blend loads."""
    # Enable the opencomp_core add-on (must happen here, not in register(),
    # because register() runs before userpref.blend resets the addon list)
    import addon_utils
    addon_utils.enable("opencomp_core", default_set=True, persistent=True)

    # Hide built-in scene panels so only OC panels show in Properties area
    _hide_builtin_scene_panels()

    # Hide chrome on all compositor areas (NODE_EDITOR, VIEW_3D)
    _configure_area_chrome()

    # Create and assign OpenComp node tree
    _ensure_opencomp_tree()

    # In GUI mode, use a deferred timer for full multi-panel setup
    if not bpy.app.background and not _deferred_setup_done:
        global _deferred_phase
        _deferred_phase = 0
        bpy.app.timers.register(_deferred_ui_setup, first_interval=0.1)


def _apply_dark_theme():
    """Apply a dark theme matching Nuke's colour language."""
    try:
        prefs = bpy.context.preferences
        theme = prefs.themes[0]

        # Node editor - dark background (back is RGB, wire is RGBA)
        theme.node_editor.space.back = (0.16, 0.16, 0.16)
        theme.node_editor.wire = (0.5, 0.5, 0.5, 1.0)
        theme.node_editor.wire_select = (1.0, 1.0, 1.0, 1.0)
    except Exception as e:
        print(f"[OpenComp] Theme apply skipped: {e}")


# ── Keymaps ────────────────────────────────────────────────────────────

# Nuke-style node shortcuts: single key → add node at cursor
_node_shortcuts = [
    # key,   node_type,         Nuke equivalent
    ('R',    'OC_N_read',       'Read'),
    ('W',    'OC_N_write',      'Write'),
    ('V',    'OC_N_viewer',     'Viewer'),
    ('G',    'OC_N_grade',      'Grade'),
    ('C',    'OC_N_cdl',        'ColorCorrect'),
    ('O',    'OC_N_over',       'Merge (Over)'),
    ('M',    'OC_N_merge',      'Merge'),
    ('B',    'OC_N_blur',       'Blur'),
    ('S',    'OC_N_shuffle',    'Shuffle'),
    ('T',    'OC_N_transform',  'Transform'),
]

_oc_keymaps = []


def _setup_keymaps():
    """Replace default Node Editor keymaps with OpenComp shortcuts.

    Wipes all default Blender Node Editor shortcuts and installs only:
    - Nuke-style single-key node creation
    - Essential navigation (pan, zoom, select, box select, link, cut)
    - Basic editing (delete, duplicate, copy/paste, undo/redo, mute)
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        print("[OpenComp] No addon keyconfig — skipping keymaps")
        return

    # ── Nuke-style node shortcuts in Node Editor ──────────────────────
    km = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    _oc_keymaps.append(km)

    for key, node_type, _label in _node_shortcuts:
        kmi = km.keymap_items.new('node.add_node', key, 'PRESS')
        kmi.properties.type = node_type
        kmi.properties.use_transform = True

    # Period — add Constant (dot node, like Nuke's "." shortcut)
    kmi = km.keymap_items.new('node.add_node', 'PERIOD', 'PRESS')
    kmi.properties.type = 'OC_N_constant'
    kmi.properties.use_transform = True

    # Shift+S — Sharpen (S alone is Shuffle, matching Nuke)
    kmi = km.keymap_items.new('node.add_node', 'S', 'PRESS', shift=True)
    kmi.properties.type = 'OC_N_sharpen'
    kmi.properties.use_transform = True

    # Shift+C — Crop
    kmi = km.keymap_items.new('node.add_node', 'C', 'PRESS', shift=True)
    kmi.properties.type = 'OC_N_crop'
    kmi.properties.use_transform = True

    # ── Selection ─────────────────────────────────────────────────────
    km_nav = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    _oc_keymaps.append(km_nav)

    # Click select (deselect_all=True means clicking empty space deselects)
    kmi = km_nav.keymap_items.new('node.select', 'LEFTMOUSE', 'PRESS')
    kmi.properties.deselect_all = True

    # Shift+click to extend selection
    kmi = km_nav.keymap_items.new('node.select', 'LEFTMOUSE', 'PRESS', shift=True)
    kmi.properties.extend = True

    # Box select (drag on empty space)
    km_nav.keymap_items.new('node.select_box', 'LEFTMOUSE', 'CLICK_DRAG')
    kmi = km_nav.keymap_items.new('node.select_box', 'LEFTMOUSE', 'CLICK_DRAG', shift=True)
    kmi.properties.mode = 'ADD'

    # Select all / deselect
    km_nav.keymap_items.new('node.select_all', 'A', 'PRESS')
    kmi = km_nav.keymap_items.new('node.select_all', 'A', 'PRESS', alt=True)
    kmi.properties.action = 'DESELECT'

    # ── Node dragging & linking ───────────────────────────────────────
    # Move nodes by dragging (must be on selected nodes)
    km_nav.keymap_items.new('node.translate_attach', 'LEFTMOUSE', 'CLICK_DRAG')

    # Link sockets by dragging with custom operator (shows menu on release in empty space)
    kmi = km_nav.keymap_items.new('oc.link_drag', 'LEFTMOUSE', 'CLICK_DRAG')
    kmi.properties.detach = False

    # Ctrl+drag to detach existing links while dragging
    kmi = km_nav.keymap_items.new('oc.link_drag', 'LEFTMOUSE', 'CLICK_DRAG', ctrl=True)
    kmi.properties.detach = True

    # Tab to show add menu and auto-connect to active node
    # Workflow: select node -> Tab -> choose node -> new node is connected
    km_nav.keymap_items.new('oc.add_and_link', 'TAB', 'PRESS')

    # Cut links (Ctrl+Right mouse drag)
    km_nav.keymap_items.new('node.links_cut', 'RIGHTMOUSE', 'CLICK_DRAG', ctrl=True)

    # Detach links (Alt+drag)
    km_nav.keymap_items.new('node.links_detach', 'LEFTMOUSE', 'CLICK_DRAG', alt=True)

    # ── Context menu ──────────────────────────────────────────────────
    km_nav.keymap_items.new('wm.call_menu', 'RIGHTMOUSE', 'PRESS').properties.name = 'NODE_MT_context_menu'

    # ── Navigation ────────────────────────────────────────────────────
    # Pan (middle mouse drag)
    km_nav.keymap_items.new('view2d.pan', 'MIDDLEMOUSE', 'PRESS')

    # Zoom at cursor (scroll wheel)
    km_nav.keymap_items.new('view2d.zoom_in', 'WHEELUPMOUSE', 'PRESS')
    km_nav.keymap_items.new('view2d.zoom_out', 'WHEELDOWNMOUSE', 'PRESS')

    # Frame all / frame selected
    km_nav.keymap_items.new('node.view_all', 'HOME', 'PRESS')
    km_nav.keymap_items.new('node.view_selected', 'NUMPAD_PERIOD', 'PRESS')
    km_nav.keymap_items.new('node.view_selected', 'F', 'PRESS')

    # ── Editing ───────────────────────────────────────────────────────
    km_edit = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    _oc_keymaps.append(km_edit)

    # Delete
    km_edit.keymap_items.new('node.delete', 'X', 'PRESS')
    km_edit.keymap_items.new('node.delete', 'DEL', 'PRESS')
    km_edit.keymap_items.new('node.delete_reconnect', 'X', 'PRESS', ctrl=True)

    # Duplicate
    km_edit.keymap_items.new('node.duplicate_move', 'D', 'PRESS', ctrl=True)

    # Copy / Paste
    km_edit.keymap_items.new('node.clipboard_copy', 'C', 'PRESS', ctrl=True)
    km_edit.keymap_items.new('node.clipboard_paste', 'V', 'PRESS', ctrl=True)

    # Undo / Redo
    km_edit.keymap_items.new('ed.undo', 'Z', 'PRESS', ctrl=True)
    km_edit.keymap_items.new('ed.redo', 'Z', 'PRESS', ctrl=True, shift=True)

    # Mute toggle (Nuke: D)
    km_edit.keymap_items.new('node.mute_toggle', 'D', 'PRESS')

    # Find
    km_edit.keymap_items.new('node.find_node', 'F', 'PRESS', ctrl=True)

    # Add menu (Shift+A or Tab)
    km_edit.keymap_items.new('wm.call_menu', 'A', 'PRESS', shift=True).properties.name = 'NODE_MT_add'

    # Join into frame / detach from frame
    km_edit.keymap_items.new('node.join', 'J', 'PRESS', ctrl=True)
    km_edit.keymap_items.new('node.detach', 'P', 'PRESS', alt=True)

    print("[OpenComp] Keymaps installed")


def _clear_default_node_keymaps():
    """Disable conflicting default Blender Node Editor keymaps.

    We disable rather than delete because the default keyconfig is read-only.
    Our addon keymaps take priority over disabled default ones.

    We keep link-related keymaps enabled for proper drag-to-menu behavior.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.default
    if kc is None:
        return

    # Keymaps to keep enabled for proper node editor functionality
    keep_enabled = {
        'node.link',           # Link dragging + popup menu on release
        'node.link_make',      # Making links
        'node.link_viewer',    # Connect to viewer
        'node.links_cut',      # Cutting links
        'node.links_detach',   # Detaching links
        'node.links_mute',     # Muting links
    }

    count = 0
    for km in kc.keymaps:
        if km.space_type == 'NODE_EDITOR':
            for kmi in km.keymap_items:
                if kmi.active and kmi.idname not in keep_enabled:
                    kmi.active = False
                    count += 1
    print(f"[OpenComp] Disabled {count} default Node Editor shortcuts (kept link operators)")


def _restore_default_node_keymaps():
    """Re-enable default Node Editor keymaps on unregister."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.default
    if kc is None:
        return

    for km in kc.keymaps:
        if km.space_type == 'NODE_EDITOR':
            for kmi in km.keymap_items:
                if not kmi.active:
                    kmi.active = True


def _teardown_keymaps():
    """Remove all OpenComp keymaps."""
    for km in _oc_keymaps:
        try:
            bpy.context.window_manager.keyconfigs.addon.keymaps.remove(km)
        except Exception:
            pass
    _oc_keymaps.clear()
    _restore_default_node_keymaps()
    print("[OpenComp] Keymaps removed")


# ── Registration ───────────────────────────────────────────────────────

def register():
    """Register app template — called by Blender on template activation."""
    # Register operator classes
    for cls in _operator_classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

    # Register custom menu classes
    for cls in _menu_classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

    _override_topbar()
    _override_view3d_header()
    _override_splash()
    _override_splash_about()
    _override_quick_setup()
    _apply_dark_theme()
    _clear_default_node_keymaps()
    _setup_keymaps()

    # Zoom at mouse cursor (industry standard, not center of panel)
    bpy.context.preferences.inputs.use_zoom_to_mouse = True

    # Auto-save preferences on quit so settings persist
    bpy.context.preferences.use_preferences_save = True

    # Use load_factory_startup_post for initial startup layout
    if _configure_ui_on_load not in bpy.app.handlers.load_factory_startup_post:
        bpy.app.handlers.load_factory_startup_post.append(_configure_ui_on_load)

    # Also run on load_post for when user opens files
    if _configure_ui_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_configure_ui_on_load)

    # Handler to track active node for Tab connection
    if _track_active_node not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_track_active_node)

    print("[OpenComp] App template registered")


def unregister():
    """Unregister app template."""
    _teardown_keymaps()
    _restore_topbar()
    _restore_view3d_header()
    _restore_splash()
    _restore_splash_about()
    _restore_quick_setup()
    _restore_builtin_scene_panels()

    if _configure_ui_on_load in bpy.app.handlers.load_factory_startup_post:
        bpy.app.handlers.load_factory_startup_post.remove(_configure_ui_on_load)

    if _configure_ui_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_configure_ui_on_load)

    if _track_active_node in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_track_active_node)

    # Unregister menu classes
    for cls in reversed(_menu_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    # Unregister operator classes
    for cls in reversed(_operator_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    print("[OpenComp] App template unregistered")
