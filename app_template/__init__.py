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

        row = layout.row()
        row.scale_y = 2.0
        row.alignment = 'CENTER'
        row.label(text="OPENCOMP")

        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text=_OC_VERSION)


class OC_MT_nodes(bpy.types.Menu):
    """OpenComp Nodes menu."""
    bl_idname = "OC_MT_nodes"
    bl_label = "Nodes"

    def draw(self, context):
        layout = self.layout
        layout.menu("NODE_MT_add", text="Add")
        layout.separator()
        layout.operator("node.delete", text="Delete")
        layout.operator("node.duplicate_move", text="Duplicate")
        layout.separator()
        layout.operator("node.mute_toggle", text="Mute")
        layout.operator("node.hide_toggle", text="Collapse")
        layout.separator()
        layout.operator("node.select_all", text="Select All").action = 'SELECT'
        layout.operator("node.select_all", text="Deselect All").action = 'DESELECT'


class OC_MT_render(bpy.types.Menu):
    """OpenComp Render menu."""
    bl_idname = "OC_MT_render"
    bl_label = "Render"

    def draw(self, context):
        layout = self.layout
        # Force re-evaluate operator
        if hasattr(bpy.types, "OC_OT_force_evaluate"):
            layout.operator("oc.force_evaluate", text="Force Re-evaluate", icon='FILE_REFRESH')
        else:
            layout.label(text="Force Re-evaluate (F5)")
        layout.separator()
        layout.operator("render.render", text="Render Image", icon='RENDER_STILL')
        layout.operator("render.render", text="Render Animation", icon='RENDER_ANIMATION').animation = True


class OC_MT_window(bpy.types.Menu):
    """OpenComp Window menu."""
    bl_idname = "OC_MT_window"
    bl_label = "Window"

    def draw(self, context):
        layout = self.layout
        # NodeGraphQt launcher
        if hasattr(bpy.types, "OC_OT_launch_nodegraph"):
            layout.operator("oc.launch_nodegraph", text="Node Graph (Tab)", icon='NODETREE')
        else:
            layout.label(text="Node Graph (Tab)")
        layout.separator()
        layout.operator("wm.window_new", text="New Window")
        layout.operator("screen.screen_full_area", text="Toggle Fullscreen")
        layout.separator()
        # Area type changes
        layout.operator("screen.area_dupli", text="Duplicate Area into New Window")


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
    'nodes_before': set(),
}


def _cleanup_link_drag():
    """Module-level cleanup for link drag state."""
    state = _link_drag
    state['active'] = False
    state['waiting_for_menu'] = False
    state['source_socket'] = None
    state['nodes_before'] = set()

    if state['draw_handler']:
        try:
            bpy.types.SpaceNodeEditor.draw_handler_remove(state['draw_handler'], 'WINDOW')
        except Exception:
            pass
        state['draw_handler'] = None

    # Force redraw
    for area in bpy.context.screen.areas:
        if area.type == 'NODE_EDITOR':
            area.tag_redraw()


def _check_menu_dismissed():
    """Timer callback to check if menu was dismissed without selection."""
    state = _link_drag

    if not state['waiting_for_menu']:
        return None  # Already cleaned up

    tree = state['tree']
    if tree:
        # Check if a new node was created
        current_nodes = set(n.name for n in tree.nodes)
        new_nodes = current_nodes - state['nodes_before']
        if new_nodes:
            # Node was created - don't clean up yet, let the link timer handle it
            return None

    # No node created, clean up the link
    _cleanup_link_drag()
    return None


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
    shader.uniform_float("color", (0.3, 0.85, 0.5, 0.9))  # Green link color
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
            # We're waiting for menu selection
            # Cancel on ESC
            if event.type == 'ESC' and event.value == 'PRESS':
                _cleanup_link_drag()
                return {'CANCELLED'}

            # If user clicks elsewhere (dismisses menu), clean up after short delay
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                bpy.app.timers.register(_check_menu_dismissed, first_interval=0.15)
                return {'PASS_THROUGH'}

            # Also check for right-click dismiss
            if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
                _cleanup_link_drag()
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
                    if state.get('is_output'):
                        tree.links.new(state['source_socket'], target_socket)
                    else:
                        tree.links.new(target_socket, state['source_socket'])
                except:
                    pass
                _cleanup_link_drag()
                return {'FINISHED'}
            else:
                # Released in empty space - show menu, keep line visible
                state['waiting_for_menu'] = True
                state['active'] = False

                # Store cursor position for new node
                view2d = context.region.view2d
                loc = view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)
                context.space_data.cursor_location = loc

                # Store nodes before menu in global state
                state['nodes_before'] = set(n.name for n in state['tree'].nodes)

                # Show the add menu
                bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="NODE_MT_add")

                # Start checking for new node
                self._menu_check_count = 0
                bpy.app.timers.register(
                    self._check_for_new_node_timer,
                    first_interval=0.05
                )

                return {'RUNNING_MODAL'}

        # Cancel on right click or escape
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            _cleanup_link_drag()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def _check_for_new_node_timer(self):
        """Timer to check if user selected a node from menu."""
        state = _link_drag

        self._menu_check_count += 1

        # Timeout after ~1 second (20 * 50ms)
        if self._menu_check_count > 20 or not state['waiting_for_menu']:
            _cleanup_link_drag()
            return None

        tree = state['tree']
        if not tree:
            _cleanup_link_drag()
            return None

        # Check for new node
        current_nodes = set(n.name for n in tree.nodes)
        new_nodes = current_nodes - state['nodes_before']
        if new_nodes:
            # New node created - link it
            new_node_name = list(new_nodes)[0]
            new_node = tree.nodes.get(new_node_name)
            if new_node:
                self._create_link(state, new_node)
            _cleanup_link_drag()
            return None

        # Keep checking
        return 0.05

    def _create_link(self, state, new_node):
        """Create a link between source socket and new node."""
        tree = state['tree']
        socket = state['source_socket']

        try:
            if state.get('is_output'):
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
        """Clean up drag state - delegates to module function."""
        _cleanup_link_drag()

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
    OC_MT_nodes,
    OC_MT_render,
    OC_MT_window,
    OC_MT_help,
]

class OC_OT_force_evaluate(bpy.types.Operator):
    """Force re-evaluation of the node graph"""
    bl_idname = "oc.force_evaluate"
    bl_label = "Force Re-evaluate"
    bl_description = "Force re-evaluation of all nodes (F5)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Find OpenComp node tree and trigger evaluation
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor":
                if hasattr(tree, '_eval_needed'):
                    tree._eval_needed = True
                # Also mark all nodes as dirty
                for node in tree.nodes:
                    if hasattr(node, '_dirty'):
                        node._dirty = True
                break

        # Redraw all node editors
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()
            elif area.type == 'VIEW_3D':
                area.tag_redraw()

        self.report({'INFO'}, "Graph re-evaluation triggered")
        return {'FINISHED'}


_operator_classes = [
    OC_OT_splash_about,
    OC_OT_show_add_menu,
    OC_OT_link_drag,
    OC_OT_add_and_link,
    OC_OT_force_evaluate,
]


# ── Left Toolbar Panel ─────────────────────────────────────────────────

class OC_PT_left_toolbar(bpy.types.Panel):
    """OpenComp left toolbar — Nuke-style tool icons."""
    bl_idname = "OC_PT_left_toolbar"
    bl_label = ""  # No label, just icons
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        # Only show in narrow IMAGE_EDITOR areas (toolbar areas)
        return context.area and context.area.width < 100

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.5

        # Tool buttons - each adds a node or performs an action
        col = layout.column(align=True)

        # File operations
        col.operator("wm.open_mainfile", text="", icon='FILEBROWSER')
        col.operator("wm.save_mainfile", text="", icon='FILE_TICK')
        col.separator()

        # Node creation shortcuts
        col.operator("node.add_node", text="", icon='IMAGE_DATA').type = 'OC_N_read'
        col.operator("node.add_node", text="", icon='COLOR').type = 'OC_N_grade'
        col.operator("node.add_node", text="", icon='OVERLAY').type = 'OC_N_over'
        col.operator("node.add_node", text="", icon='MOD_SMOOTH').type = 'OC_N_blur'
        col.operator("node.add_node", text="", icon='ORIENTATION_GIMBAL').type = 'OC_N_transform'
        col.separator()

        col.operator("node.add_node", text="", icon='RESTRICT_VIEW_OFF').type = 'OC_N_viewer'
        col.operator("node.add_node", text="", icon='EXPORT').type = 'OC_N_write'


_panel_classes = [
    OC_PT_left_toolbar,
]


# ── TOPBAR Override ─────────────────────────────────────────────────────

def _opencomp_topbar_draw(self, context):
    """Replace Blender's top bar with OpenComp branding and menus."""
    layout = self.layout
    region = context.region

    # Debug: print once to confirm this is being called
    if not hasattr(_opencomp_topbar_draw, '_printed'):
        _opencomp_topbar_draw._printed = True
        print("[OpenComp] TOPBAR drawing with v0.2 menus: File, Edit, View, Nodes, Render, Window, Help")

    if region.alignment == 'RIGHT':
        # Right side: empty (no Blender scene/viewlayer selectors)
        pass
    else:
        # Left side: OpenComp branding + custom menus (no workspace tabs)
        layout.label(text="OpenComp", icon='NODE_COMPOSITING')
        layout.separator(type='LINE')
        layout.menu("OC_MT_file")
        layout.menu("OC_MT_edit")
        layout.menu("OC_MT_view")
        layout.menu("OC_MT_nodes")
        layout.menu("OC_MT_render")
        layout.menu("OC_MT_window")
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


# ── Node Editor Header Override ─────────────────────────────────────────

_original_node_header_draw = None


def _opencomp_node_header_draw(self, context):
    """Replace Node Editor header with clean OpenComp version."""
    layout = self.layout
    snode = context.space_data

    # Only override for OpenComp trees; fall back for others
    if snode.tree_type != "OC_NT_compositor":
        if _original_node_header_draw:
            _original_node_header_draw(self, context)
        return

    # Just the menus, nothing else
    layout.menu("OC_MT_file")
    layout.menu("OC_MT_edit")
    layout.menu("OC_MT_view")
    layout.menu("OC_MT_nodes")

    # Empty right side
    layout.separator_spacer()


def _override_node_header():
    """Replace NODE_HT_header draw with OpenComp version."""
    global _original_node_header_draw
    try:
        header_cls = bpy.types.NODE_HT_header
        _original_node_header_draw = header_cls.draw
        header_cls.draw = _opencomp_node_header_draw
    except Exception as e:
        print(f"[OpenComp] Node header override skipped: {e}")


def _restore_node_header():
    """Restore original NODE_HT_header draw function."""
    global _original_node_header_draw
    if _original_node_header_draw is not None:
        try:
            bpy.types.NODE_HT_header.draw = _original_node_header_draw
            _original_node_header_draw = None
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

    # Colorspace dropdown
    row = layout.row(align=True)
    row.label(text="CS:")
    row.prop(settings, "colorspace", text="")

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


# ── Timeline Header Override ───────────────────────────────────────────

_original_time_header_draw = None


def _opencomp_time_header_draw(self, context):
    """Custom timeline header with rearranged playback controls.

    Layout: [FPS] | [Playback Mode] [Start] [Controls] [End] | [Sync Mode]
    Only applies in TIMELINE mode - other modes use original header.
    """
    # Only use custom layout for TIMELINE mode
    space = context.space_data
    if space.mode != 'TIMELINE':
        if _original_time_header_draw:
            _original_time_header_draw(self, context)
        return

    layout = self.layout
    scene = context.scene
    screen = context.screen

    # Use scale_x to make buttons wider (scale_y causes truncation in headers)
    # We'll make individual elements larger instead

    # FPS dropdown (far left)
    row = layout.row(align=True)
    row.scale_x = 1.3
    row.prop(scene, "oc_fps_preset", text="")
    # Show manual input when Custom is selected
    if scene.oc_fps_preset == 'CUSTOM':
        sub = row.row(align=True)
        sub.scale_x = 0.6
        sub.prop(scene.render, "fps", text="")

    layout.separator_spacer()

    # Playback mode (loop/pingpong/etc) before start frame
    row = layout.row(align=True)
    row.scale_x = 1.3
    row.prop(scene, "oc_playback_mode", text="")

    # Start frame (left of playback controls)
    row = layout.row(align=True)
    row.scale_x = 1.0
    row.prop(scene, "frame_start", text="")

    # Left side: Jump to start, previous frame
    row = layout.row(align=True)
    row.scale_x = 1.5
    row.operator("screen.frame_jump", text="", icon='REW').end = False
    row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False

    # Play backwards button
    row = layout.row(align=True)
    row.scale_x = 1.5
    if screen.is_animation_playing and screen.is_scrubbing:
        row.operator("screen.animation_cancel", text="", icon='PAUSE')
    else:
        op = row.operator("screen.animation_play", text="", icon='PLAY_REVERSE')
        op.reverse = True

    # Current frame number (center)
    row = layout.row(align=True)
    row.scale_x = 1.2
    row.prop(scene, "frame_current", text="")

    # Play forwards button
    row = layout.row(align=True)
    row.scale_x = 1.5
    if screen.is_animation_playing and not screen.is_scrubbing:
        row.operator("screen.animation_cancel", text="", icon='PAUSE')
    else:
        op = row.operator("screen.animation_play", text="", icon='PLAY')
        op.reverse = False

    # Right side: Next frame, jump to end
    row = layout.row(align=True)
    row.scale_x = 1.5
    row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
    row.operator("screen.frame_jump", text="", icon='FF').end = True

    # End frame (right of playback controls)
    row = layout.row(align=True)
    row.scale_x = 1.0
    row.prop(scene, "frame_end", text="")

    layout.separator_spacer()

    # Sync mode (far right)
    row = layout.row(align=True)
    row.scale_x = 1.3
    row.prop(scene, "sync_mode", text="")


def _override_time_header():
    """Replace DOPESHEET_HT_header draw with OpenComp layout."""
    global _original_time_header_draw
    try:
        header_cls = bpy.types.DOPESHEET_HT_header
        _original_time_header_draw = header_cls.draw
        header_cls.draw = _opencomp_time_header_draw
        print("[OpenComp] Timeline header override installed")
    except Exception as e:
        print(f"[OpenComp] Timeline header override skipped: {e}")


def _restore_time_header():
    """Restore original DOPESHEET_HT_header draw function."""
    global _original_time_header_draw
    if _original_time_header_draw is not None:
        try:
            bpy.types.DOPESHEET_HT_header.draw = _original_time_header_draw
            _original_time_header_draw = None
        except Exception:
            pass


# ── Splash Screen Override ─────────────────────────────────────────────

class OC_OT_dismiss_splash(bpy.types.Operator):
    """Dismiss the splash screen."""
    bl_idname = "oc.dismiss_splash"
    bl_label = "Continue"

    def execute(self, context):
        return {'FINISHED'}


def _opencomp_splash_draw(self, context):
    """Replace Blender's splash menu - click anywhere to dismiss."""
    layout = self.layout
    layout.alignment = 'CENTER'

    layout.separator()

    # Title - centered
    row = layout.row()
    row.alignment = 'CENTER'
    row.scale_y = 2.0
    row.operator("oc.dismiss_splash", text="OPENCOMP", emboss=False)

    # Version - centered
    row = layout.row()
    row.alignment = 'CENTER'
    row.operator("oc.dismiss_splash", text=_OC_VERSION, emboss=False)

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
    """Replace Blender's splash about - nothing, we handle it in main splash."""
    # Empty - main splash draws everything
    pass


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
    """Replace Blender's Quick Setup with nothing."""
    # Completely empty - don't draw anything
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


# ── Native Canvas Auto-Launch ──────────────────────────────────────────

def _launch_native_canvas():
    """Start the native GPU canvas modal.

    The canvas modal handles all input in the Node Editor area while
    allowing other panels to work normally.
    """
    # The canvas modal auto-starts via a timer in operators.py register()
    print("[OpenComp] Native canvas will start via timer")


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
    # Hide UI elements in preferences
    try:
        prefs = bpy.context.preferences
        prefs.view.show_navigate_ui = False  # Hide navigation gizmo
        prefs.view.show_developer_ui = False
        prefs.view.show_gizmo = False  # Hide gizmos
        prefs.view.show_object_info = False  # Hide object info
        prefs.view.show_view_name = False  # Hide view name
    except Exception:
        pass

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        space.show_region_toolbar = False
                        space.show_region_ui = False
                        space.show_region_header = True
            elif area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.show_region_toolbar = False
                        space.show_region_ui = False
                        space.show_region_tool_header = False
                        space.show_region_header = True
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
                # Hide the navigation bar (left icon column)
                for region in area.regions:
                    if region.type == 'NAVIGATION_BAR' and region.width > 1:
                        try:
                            window = bpy.context.window
                            with bpy.context.temp_override(
                                window=window, area=area, region=region
                            ):
                                bpy.ops.screen.region_toggle(
                                    region_type='NAVIGATION_BAR'
                                )
                        except Exception:
                            pass
                        break
        screen.show_statusbar = False


def _configure_viewer_area(area):
    """Configure a VIEW_3D area as the compositor viewer - hide toolbar until we have node-specific tools."""
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            space.show_region_toolbar = False  # Hide until we have context-sensitive node tools
            space.show_region_ui = False  # Hide right sidebar
            space.show_region_tool_header = False
            space.show_gizmo = False
            space.overlay.show_overlays = False
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


def _create_debug_nodes(tree):
    """Create one of each node type for debugging (only if tree is empty)."""
    if len(tree.nodes) > 0:
        return  # Tree already has nodes

    # All node types to create
    node_types = [
        'OC_N_read', 'OC_N_constant', 'OC_N_write', 'OC_N_viewer',
        'OC_N_grade', 'OC_N_cdl', 'OC_N_over', 'OC_N_merge', 'OC_N_shuffle',
        'OC_N_blur', 'OC_N_sharpen', 'OC_N_transform', 'OC_N_crop',
        'OC_N_roto', 'OC_N_reroute'
    ]

    x, y = -400, 200
    created = []
    for node_type in node_types:
        try:
            node = tree.nodes.new(node_type)
            node.location = (x, y)
            created.append(node_type.replace('OC_N_', ''))
            y -= 100
            if y < -400:
                y = 200
                x += 200
        except Exception as e:
            print(f"[OpenComp] Could not create {node_type}: {e}")

    if created:
        print(f"[OpenComp] Created debug nodes: {', '.join(created)}")


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
            # Don't create debug nodes - they cause shader errors at startup
            # _create_debug_nodes(oc_tree)
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


def _configure_timeline_area(area, window=None, screen=None):
    """Configure a DOPESHEET_EDITOR area as a Nuke-style timeline strip."""
    for space in area.spaces:
        if space.type == 'DOPESHEET_EDITOR':
            space.mode = 'TIMELINE'
            space.show_region_ui = False
            # Hide channels/search region
            try:
                space.show_region_channels = False
            except AttributeError:
                pass

    # Flip header to bottom so playback controls sit under the frame ruler
    if window is not None:
        for region in area.regions:
            if region.type == 'HEADER':
                # Check if header is at top (y position > half the area height)
                header_at_top = region.y > (area.y + area.height // 2)
                if header_at_top:
                    try:
                        with bpy.context.temp_override(
                            window=window, area=area, region=region, screen=screen
                        ):
                            bpy.ops.screen.region_flip()
                            print("[OpenComp] Flipped timeline header to bottom")
                    except Exception as e:
                        print(f"[OpenComp] Timeline header flip failed: {e}")
                break

    # Zoom timeline to fit frame range (with padding)
    _zoom_timeline_to_frame_range(area, window, screen)


def _zoom_timeline_to_frame_range(area=None, window=None, screen=None):
    """Zoom the timeline to fit the current frame range (in/out points)."""
    try:
        scene = bpy.context.scene
        frame_start = scene.frame_start
        frame_end = scene.frame_end

        # Find timeline area if not provided
        if area is None:
            for a in bpy.context.screen.areas:
                if a.type == 'DOPESHEET_EDITOR':
                    area = a
                    break

        if area is None:
            return

        # Find the window region to get view2d
        for region in area.regions:
            if region.type == 'WINDOW':
                # Use view2d to set the visible range
                view2d = region.view2d

                # Add padding (10% on each side)
                frame_range = frame_end - frame_start
                padding = max(frame_range * 0.05, 5)  # At least 5 frames padding

                # Set view bounds
                view2d.view_to_region(frame_start - padding, 0)
                view2d.view_to_region(frame_end + padding, 0)

                # Alternative: use operator to view all
                if window is not None:
                    try:
                        with bpy.context.temp_override(
                            window=window, area=area, region=region, screen=screen
                        ):
                            bpy.ops.action.view_all()
                    except Exception:
                        pass
                break
    except Exception as e:
        print(f"[OpenComp] Timeline zoom failed: {e}")



def _create_node_editor_toolbar(window, screen, node_editor):
    """Fallback: Create a toolbar just for the NODE_EDITOR area.
    
    This is used when area_join fails (areas not adjacent).
    The toolbar will only span the NODE_EDITOR height, not full window height.
    """
    print("[OpenComp] Creating NODE_EDITOR-only toolbar (fallback)")
    
    try:
        with bpy.context.temp_override(window=window, area=node_editor, screen=screen):
            result = bpy.ops.screen.area_split(direction='VERTICAL', factor=0.025)
            print(f"[OpenComp] NODE_EDITOR toolbar split result: {result}")
    except Exception as e:
        print(f"[OpenComp] NODE_EDITOR toolbar split failed: {e}")
        return
    
    # Find the new narrow area
    for area in screen.areas:
        if area.type == 'NODE_EDITOR' and area.width < 100 and area.x < 10:
            print(f"[OpenComp] Found toolbar area: w={area.width}")
            area.type = 'IMAGE_EDITOR'
            _configure_toolbar_area(area, window=window)
            break

def _try_create_left_toolbar(window, screen):
    """Create a full-height left toolbar using a different approach.

    Instead of trying to join/split areas (which is unreliable),
    we enable the TOOLS region in NODE_EDITOR and VIEW_3D.
    This creates a native toolbar sidebar that Blender manages.
    
    For a true full-height toolbar like Nuke, we'd need to modify startup.blend
    or use a completely custom window layout.
    """
    print("[OpenComp] === CONFIGURING LEFT TOOLBAR ===")
    print("[OpenComp] Current layout:")
    for area in screen.areas:
        print(f"  {area.type}: x={area.x}, y={area.y}, w={area.width}, h={area.height}")

    # Enable TOOLS region in NODE_EDITOR and VIEW_3D
    for area in screen.areas:
        if area.type == 'NODE_EDITOR':
            for region in area.regions:
                if region.type == 'TOOLS':
                    # Region exists but may be hidden - we can't directly show it
                    # but we can toggle it via operator
                    print(f"[OpenComp] NODE_EDITOR TOOLS region: w={region.width}")
                    break
        elif area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'TOOLS':
                    print(f"[OpenComp] VIEW_3D TOOLS region: w={region.width}")
                    break

    # Alternative: Create a narrow IMAGE_EDITOR area on the left
    # by splitting the first available left-side area
    node_editor = None
    view3d = None
    for area in screen.areas:
        if area.type == 'NODE_EDITOR' and area.x < 100:
            node_editor = area
        elif area.type == 'VIEW_3D' and area.x < 100:
            view3d = area

    # Don't create if toolbar already exists
    for area in screen.areas:
        if area.width < 100 and area.x < 10:
            print(f"[OpenComp] Narrow left area already exists: {area.type}")
            if area.type != 'IMAGE_EDITOR':
                area.type = 'IMAGE_EDITOR'
                _configure_toolbar_area(area, window=window)
            return

    # Try to split VIEW_3D to create toolbar that spans its height
    # (partial solution - not full height but better than nothing)
    if view3d:
        print(f"[OpenComp] Splitting VIEW_3D for toolbar")
        try:
            with bpy.context.temp_override(window=window, area=view3d, screen=screen):
                result = bpy.ops.screen.area_split(direction='VERTICAL', factor=0.02)
                print(f"[OpenComp] VIEW_3D split result: {result}")
        except Exception as e:
            print(f"[OpenComp] VIEW_3D split failed: {e}")
            return

        # Find the new narrow area on the left
        for area in screen.areas:
            if area.type == 'VIEW_3D' and area.width < 100 and area.x < 10:
                print(f"[OpenComp] Converting narrow VIEW_3D to toolbar: w={area.width}")
                area.type = 'IMAGE_EDITOR'
                _configure_toolbar_area(area, window=window)
                
                # Now try to extend this toolbar down to cover NODE_EDITOR too
                # by joining with the equivalent strip on NODE_EDITOR
                if node_editor:
                    # Split NODE_EDITOR the same way
                    try:
                        with bpy.context.temp_override(window=window, area=node_editor, screen=screen):
                            result2 = bpy.ops.screen.area_split(direction='VERTICAL', factor=0.025)
                            print(f"[OpenComp] NODE_EDITOR split result: {result2}")
                    except Exception as e:
                        print(f"[OpenComp] NODE_EDITOR split failed: {e}")
                    
                    # Now join the two narrow strips
                    toolbar_area = area
                    node_toolbar = None
                    for a in screen.areas:
                        if a.type == 'NODE_EDITOR' and a.width < 100 and a.x < 10:
                            a.type = 'IMAGE_EDITOR'
                            node_toolbar = a
                            break
                    
                    if node_toolbar and toolbar_area:
                        # Try to join these two toolbar areas
                        print(f"[OpenComp] Joining toolbar strips...")
                        # They should share an edge now
                        if toolbar_area.y > node_toolbar.y:
                            top_tb = toolbar_area
                            bot_tb = node_toolbar
                        else:
                            top_tb = node_toolbar
                            bot_tb = toolbar_area
                        
                        try:
                            with bpy.context.temp_override(window=window, screen=screen):
                                result3 = bpy.ops.screen.area_join(
                                    source_xy=(bot_tb.x + bot_tb.width // 2, bot_tb.y + bot_tb.height // 2),
                                    target_xy=(top_tb.x + top_tb.width // 2, top_tb.y + top_tb.height // 2)
                                )
                                print(f"[OpenComp] Toolbar join result: {result3}")
                        except Exception as e:
                            print(f"[OpenComp] Toolbar join failed: {e}")
                            # Both toolbars still exist, just not joined - that's ok
                break

    print("[OpenComp] === LEFT TOOLBAR CONFIGURATION COMPLETE ===")
    print("[OpenComp] Final layout:")
    for area in screen.areas:
        print(f"  {area.type}: x={area.x}, y={area.y}, w={area.width}, h={area.height}")


def _configure_toolbar_area(area, window=None):
    """Configure an IMAGE_EDITOR area as the left toolbar — minimal, GPU-drawn only."""
    for space in area.spaces:
        if space.type == 'IMAGE_EDITOR':
            # Hide all regions - we'll draw our own UI
            space.show_region_toolbar = False
            space.show_region_ui = False
            space.show_region_tool_header = False
            space.show_region_header = False
            # Also hide any other UI elements
            space.show_gizmo = False
            space.show_annotation = False   # Hide header


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

    Creates the Nuke-style layout with left toolbar.
    """
    global _deferred_setup_done

    if _deferred_setup_done:
        return None

    print("[OpenComp] Running deferred UI setup...")

    try:
        window = bpy.context.window
        if window is None:
            print("[OpenComp] Window not ready, retrying...")
            return 0.1  # retry

        screen = window.screen

        # DISABLED: Left toolbar creates IMAGE_EDITOR areas we don't want
        # Using Blender's native tool flyout menus instead
        # _try_create_left_toolbar(window, screen)

        # Merge two PROPERTIES panels into one
        _try_join_properties(window, screen)

        # Configure areas by type
        for area in screen.areas:
            if area.type == 'IMAGE_EDITOR':
                # Check if this is the toolbar (very narrow)
                if area.width < 100:
                    _configure_toolbar_area(area, window=window)
            elif area.type == 'VIEW_3D':
                _configure_viewer_area(area)
            elif area.type == 'NODE_EDITOR':
                _configure_node_editor_area(area)
            elif area.type == 'PROPERTIES':
                _configure_properties_area(area, window=window)
            elif area.type == 'DOPESHEET_EDITOR':
                _configure_timeline_area(area, window=window, screen=screen)

        # Assign OpenComp node tree
        _ensure_opencomp_tree()

        # Hide status bar
        screen.show_statusbar = False

        # Replace OS window title (best-effort, X11 only)
        _set_window_title()

        # Auto-launch the native GPU canvas
        _launch_native_canvas()

        _deferred_setup_done = True
        print("[OpenComp] Deferred UI setup complete")

    except Exception as e:
        print(f"[OpenComp] Deferred UI setup error: {e}")
        import traceback
        traceback.print_exc()

    return None  # don't repeat


@persistent
def _configure_ui_on_load(dummy):
    """Configure UI after startup.blend loads."""
    # Enable the opencomp_core add-on (must happen here, not in register(),
    # because register() runs before userpref.blend resets the addon list)
    import addon_utils
    addon_utils.enable("opencomp_core", default_set=True, persistent=True)

    # Fix frame range - ensure current frame is within valid range
    scene = bpy.context.scene
    if scene.frame_current < scene.frame_start or scene.frame_current > scene.frame_end:
        scene.frame_current = scene.frame_start

    # Set default FPS to 24 (film standard)
    scene.render.fps = 24
    scene.render.fps_base = 1.0

    # Hide built-in scene panels so only OC panels show in Properties area
    _hide_builtin_scene_panels()

    # Hide chrome on all compositor areas (NODE_EDITOR, VIEW_3D)
    _configure_area_chrome()

    # Apply theme (must be done here after prefs load)
    _apply_dark_theme()

    # Create and assign OpenComp node tree
    _ensure_opencomp_tree()

    # Set window title (delayed to ensure window exists)
    bpy.app.timers.register(_set_window_title, first_interval=0.5)

    # Schedule deferred UI setup (creates left toolbar, etc.)
    bpy.app.timers.register(_deferred_ui_setup, first_interval=0.3)


def _apply_dark_theme():
    """Apply a dark theme matching Nuke's colour language."""
    prefs = bpy.context.preferences
    theme = prefs.themes[0]
    ui = theme.user_interface

    # Consistent UI scale and line width for clean look
    try:
        prefs.view.ui_scale = 1.0
        prefs.view.ui_line_width = 'THIN'
    except Exception:
        pass

    # Panel border - match background so it's not jarring
    ui.editor_border = (0.12, 0.12, 0.12)

    # CRITICAL: Restore icon/text visibility (startup.blend sets this to 0.0)
    ui.icon_alpha = 1.0

    # General UI widget colors - wrap in try/except for safety
    try:
        ui.wcol_regular.inner = (0.22, 0.22, 0.22, 1.0)
        ui.wcol_regular.inner_sel = (0.35, 0.35, 0.35, 1.0)
        ui.wcol_regular.outline = (0.15, 0.15, 0.15, 1.0)
        ui.wcol_regular.text = (0.85, 0.85, 0.85)  # RGB only
        ui.wcol_regular.text_sel = (1.0, 1.0, 1.0)  # RGB only

        ui.wcol_tool.inner = (0.25, 0.25, 0.25, 1.0)
        ui.wcol_tool.inner_sel = (0.4, 0.4, 0.4, 1.0)
        ui.wcol_tool.text = (0.85, 0.85, 0.85)

        ui.wcol_text.inner = (0.18, 0.18, 0.18, 1.0)
        ui.wcol_text.inner_sel = (0.3, 0.3, 0.3, 1.0)
        ui.wcol_text.text = (0.9, 0.9, 0.9)

        ui.wcol_num.inner = (0.2, 0.2, 0.2, 1.0)
        ui.wcol_num.text = (0.85, 0.85, 0.85)

        # Menu widget colors (for topbar menus)
        ui.wcol_menu.inner = (0.22, 0.22, 0.22, 1.0)
        ui.wcol_menu.inner_sel = (0.35, 0.35, 0.35, 1.0)
        ui.wcol_menu.text = (0.9, 0.9, 0.9)  # Light text
        ui.wcol_menu.text_sel = (1.0, 1.0, 1.0)

        # Menu item colors (dropdown items)
        ui.wcol_menu_item.inner = (0.20, 0.20, 0.20, 1.0)
        ui.wcol_menu_item.inner_sel = (0.3, 0.5, 0.3, 1.0)  # Green highlight
        ui.wcol_menu_item.text = (0.9, 0.9, 0.9)
        ui.wcol_menu_item.text_sel = (1.0, 1.0, 1.0)

        # Menu background
        ui.wcol_menu_back.inner = (0.18, 0.18, 0.18, 1.0)
        ui.wcol_menu_back.outline = (0.1, 0.1, 0.1, 1.0)

        # Pulldown menus (topbar menu buttons) - BRIGHT TEXT
        ui.wcol_pulldown.inner = (0.2, 0.2, 0.2, 1.0)
        ui.wcol_pulldown.inner_sel = (0.3, 0.3, 0.3, 1.0)
        ui.wcol_pulldown.outline = (0.15, 0.15, 0.15, 1.0)
        ui.wcol_pulldown.text = (1.0, 1.0, 1.0)  # Pure white
        ui.wcol_pulldown.text_sel = (1.0, 1.0, 0.0)  # Yellow when selected

        # Also set the "option" widget which might be used
        ui.wcol_option.inner = (0.2, 0.2, 0.2, 1.0)
        ui.wcol_option.text = (1.0, 1.0, 1.0)

        # Radio buttons (sometimes used in headers)
        ui.wcol_radio.inner = (0.2, 0.2, 0.2, 1.0)
        ui.wcol_radio.text = (1.0, 1.0, 1.0)

    except Exception as e:
        print(f"[OpenComp] Widget theme error: {e}")

    # Topbar (top menu bar) - dark background, light text
    # Note: text colors are RGB (3 values), backgrounds are RGBA (4 values)
    try:
        theme.topbar.space.back = (0.15, 0.15, 0.15)
        theme.topbar.space.header = (0.15, 0.15, 0.15, 1.0)
        theme.topbar.space.header_text = (0.95, 0.95, 0.95)  # RGB only
        theme.topbar.space.header_text_hi = (1.0, 1.0, 1.0)  # RGB only
        theme.topbar.space.text = (0.95, 0.95, 0.95)  # RGB only
        theme.topbar.space.text_hi = (1.0, 1.0, 1.0)  # RGB only
        theme.topbar.space.button = (0.2, 0.2, 0.2, 1.0)
        theme.topbar.space.button_text = (0.95, 0.95, 0.95)  # RGB only
        theme.topbar.space.button_text_hi = (1.0, 1.0, 1.0)  # RGB only
    except Exception as e:
        print(f"[OpenComp] Topbar theme error: {e}")

    # Node editor - dark background
    try:
        theme.node_editor.space.back = (0.16, 0.16, 0.16)
        theme.node_editor.wire = (0.5, 0.5, 0.5, 1.0)
        theme.node_editor.wire_select = (1.0, 1.0, 1.0, 1.0)
    except Exception:
        pass

    # View3D theme
    try:
        theme.view_3d.space.back = (0.12, 0.12, 0.12)
    except Exception:
        pass

    # Properties panel - dark background
    try:
        theme.properties.space.back = (0.18, 0.18, 0.18)
        theme.properties.space.header = (0.20, 0.20, 0.20, 1.0)
        # Panel header styling
        theme.properties.space.panelcolors.header = (0.22, 0.22, 0.22, 1.0)
    except Exception:
        pass

    # Panel colors - consistent across all editors
    try:
        ui.panel.header = (0.22, 0.22, 0.22, 1.0)
        ui.panel.back = (0.18, 0.18, 0.18, 1.0)
        ui.panel.sub_back = (0.16, 0.16, 0.16, 1.0)
    except Exception:
        pass

    # Widget emboss (subtle 3D effect on buttons)
    try:
        ui.emboss = (0.0, 0.0, 0.0, 0.3)
    except Exception:
        pass

    print("[OpenComp] Nuke theme applied")


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

    # Tab to open NodeGraphQt (if available) or add menu
    # Note: We register Tab for NodeGraphQt launch - operator checks if Qt is available
    if hasattr(bpy.types, 'OC_OT_launch_nodegraph'):
        km_nav.keymap_items.new('oc.launch_nodegraph', 'TAB', 'PRESS')
    else:
        # Fallback to add and link if NodeGraphQt not available
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

    # F5 — Force re-evaluate graph
    km_edit.keymap_items.new('oc.force_evaluate', 'F5', 'PRESS')

    # ── Window-level shortcuts ────────────────────────────────────────────
    # These work from any area, not just Node Editor
    km_window = kc.keymaps.new(name='Window', space_type='EMPTY')
    _oc_keymaps.append(km_window)

    # F5 from any area
    km_window.keymap_items.new('oc.force_evaluate', 'F5', 'PRESS')

    print("[OpenComp] Keymaps installed")


def _clear_default_node_keymaps():
    """Disable conflicting default Blender Node Editor keymaps.

    We disable rather than delete because the default keyconfig is read-only.
    Our addon keymaps take priority over disabled default ones.

    We keep essential keymaps enabled for proper node editor functionality.
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.default
    if kc is None:
        return

    # Keymaps to keep enabled for proper node editor functionality
    keep_enabled = {
        # Link operations
        'node.link',           # Link dragging + popup menu on release
        'node.link_make',      # Making links
        'node.link_viewer',    # Connect to viewer
        'node.links_cut',      # Cutting links
        'node.links_detach',   # Detaching links
        'node.links_mute',     # Muting links
        # Essential node operations
        'node.add_node',       # Adding nodes from menu
        'node.select',         # Clicking to select nodes
        'node.select_box',     # Box selection
        'node.select_all',     # Select all
        'node.translate_attach',  # Moving nodes
        'node.delete',         # Deleting nodes
        'node.delete_reconnect',  # Dissolve nodes
        'node.duplicate_move', # Duplicating nodes
        'node.clipboard_copy', # Copy
        'node.clipboard_paste',# Paste
        'node.mute_toggle',    # Mute toggle
        'node.view_all',       # Frame all
        'node.view_selected',  # Frame selected
        'node.find_node',      # Find node
        'node.join',           # Join into frame
        'node.detach',         # Remove from frame
        # View operations (pan/zoom)
        'view2d.pan',          # Panning
        'view2d.zoom',         # Zooming
        'view2d.zoom_in',      # Zoom in
        'view2d.zoom_out',     # Zoom out
        'view2d.scroll_left',  # Scroll
        'view2d.scroll_right',
        'view2d.scroll_up',
        'view2d.scroll_down',
        # Menu operations
        'wm.call_menu',        # Opening menus (Add menu, context menu)
        # Undo/redo
        'ed.undo',
        'ed.redo',
    }

    count = 0
    for km in kc.keymaps:
        if km.space_type == 'NODE_EDITOR':
            for kmi in km.keymap_items:
                if kmi.active and kmi.idname not in keep_enabled:
                    kmi.active = False
                    count += 1
    print(f"[OpenComp] Disabled {count} default Node Editor shortcuts (kept essential operators)")


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


# ── Compositor Viewer Tools ────────────────────────────────────────────

class OC_OT_viewer_fit(bpy.types.Operator):
    """Fit the viewer to show the entire image"""
    bl_idname = "oc.viewer_fit"
    bl_label = "Fit View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.view3d.view_all(center=True)
        return {'FINISHED'}


class OC_OT_viewer_zoom_1to1(bpy.types.Operator):
    """Zoom to 100% (1:1 pixel ratio)"""
    bl_idname = "oc.viewer_zoom_1to1"
    bl_label = "1:1 Zoom"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.region_3d.view_perspective = 'ORTHO'
                        space.region_3d.view_distance = 10.0
                        break
        return {'FINISHED'}


class OC_OT_viewer_zoom_in(bpy.types.Operator):
    """Zoom in on the viewer"""
    bl_idname = "oc.viewer_zoom_in"
    bl_label = "Zoom In"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.view3d.zoom(delta=1)
        return {'FINISHED'}


class OC_OT_viewer_zoom_out(bpy.types.Operator):
    """Zoom out on the viewer"""
    bl_idname = "oc.viewer_zoom_out"
    bl_label = "Zoom Out"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.view3d.zoom(delta=-1)
        return {'FINISHED'}


class OC_OT_viewer_pan(bpy.types.Operator):
    """Pan the viewer"""
    bl_idname = "oc.viewer_pan"
    bl_label = "Pan"
    bl_options = {'REGISTER'}

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        bpy.ops.view3d.move('INVOKE_DEFAULT')
        return {'FINISHED'}


class OC_OT_viewer_reset(bpy.types.Operator):
    """Reset the viewer to default position"""
    bl_idname = "oc.viewer_reset"
    bl_label = "Reset View"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.view3d.view_all(center=True)
        return {'FINISHED'}


# Custom WorkSpaceTools for the compositor viewer
class OC_TOOL_pan(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "oc.tool_pan"
    bl_label = "Pan"
    bl_description = "Pan the viewer"
    bl_icon = "ops.generic.cursor"
    bl_widget = None
    bl_keymap = (
        ("view3d.move", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
        ("view3d.move", {"type": 'MIDDLEMOUSE', "value": 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        pass


class OC_TOOL_zoom(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "oc.tool_zoom"
    bl_label = "Zoom"
    bl_description = "Zoom the viewer"
    bl_icon = "ops.generic.select"
    bl_widget = None
    bl_keymap = (
        ("view3d.zoom", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
        ("view3d.zoom", {"type": 'MIDDLEMOUSE', "value": 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        pass


# Panel for viewer tools in the left toolbar (T-panel)
class OC_PT_viewer_tools(bpy.types.Panel):
    """Compositor viewer tools panel"""
    bl_label = ""
    bl_idname = "OC_PT_viewer_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'TOOLS'
    bl_category = "Tools"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.5

        col = layout.column(align=True)
        col.operator("oc.viewer_pan", text="Pan", icon='VIEW_PAN')
        col.operator("oc.viewer_fit", text="Fit", icon='FULLSCREEN_ENTER')
        col.operator("oc.viewer_zoom_1to1", text="1:1", icon='ZOOM_PREVIOUS')
        col.operator("oc.viewer_zoom_in", text="Zoom +", icon='ZOOM_IN')
        col.operator("oc.viewer_zoom_out", text="Zoom -", icon='ZOOM_OUT')
        col.operator("oc.viewer_reset", text="Reset", icon='HOME')

        layout.separator()

        col = layout.column(align=True)
        col.label(text="Channels")
        row = col.row(align=True)
        row.scale_x = 1.0
        row.operator("oc.viewer_fit", text="RGB", depress=True)
        row = col.row(align=True)
        row.operator("oc.viewer_fit", text="R")
        row.operator("oc.viewer_fit", text="G")
        row.operator("oc.viewer_fit", text="B")
        row = col.row(align=True)
        row.operator("oc.viewer_fit", text="A")
        row.operator("oc.viewer_fit", text="L")

        layout.separator()

        col = layout.column(align=True)
        col.label(text="Background")
        space = context.space_data
        if space.type == 'VIEW_3D':
            col.prop(space.shading, "background_type", text="")
            if space.shading.background_type == 'VIEWPORT':
                col.prop(space.shading, "background_color", text="")


# List of viewer tool classes (operators and panels)
_viewer_tool_classes = [
    OC_OT_viewer_fit,
    OC_OT_viewer_zoom_1to1,
    OC_OT_viewer_zoom_in,
    OC_OT_viewer_zoom_out,
    OC_OT_viewer_pan,
    OC_OT_viewer_reset,
    OC_PT_viewer_tools,
]

# WorkSpaceTools to register separately
_viewer_workspace_tools = [
    OC_TOOL_pan,
    OC_TOOL_zoom,
]

# Default VIEW_3D tools to unregister
_default_view3d_tools = [
    "builtin.select_box",
    "builtin.select_circle",
    "builtin.select_lasso",
    "builtin.cursor",
    "builtin.move",
    "builtin.rotate",
    "builtin.scale",
    "builtin.transform",
    "builtin.annotate",
    "builtin.annotate_line",
    "builtin.annotate_polygon",
    "builtin.annotate_eraser",
    "builtin.measure",
    "builtin.add_cube",
]


def _unregister_default_view3d_tools():
    """Unregister default VIEW_3D tools to clean up the toolbar."""
    from bl_ui.space_toolsystem_common import ToolDef
    from bl_ui.space_toolsystem_toolbar import VIEW3D_PT_tools_active

    for tool_id in _default_view3d_tools:
        try:
            bpy.utils.unregister_tool(VIEW3D_PT_tools_active, tool_id)
            print(f"[OpenComp] Unregistered tool: {tool_id}")
        except Exception as e:
            pass  # Tool may not exist or already unregistered


def _register_compositor_tools():
    """Register our custom compositor tools for the VIEW_3D toolbar."""
    from bl_ui.space_toolsystem_toolbar import VIEW3D_PT_tools_active

    # Register our custom tools
    for tool_cls in _viewer_workspace_tools:
        try:
            bpy.utils.register_tool(VIEW3D_PT_tools_active, tool_cls, after=None, separator=False)
            print(f"[OpenComp] Registered tool: {tool_cls.bl_idname}")
        except Exception as e:
            print(f"[OpenComp] Failed to register tool {tool_cls.bl_idname}: {e}")


# ── Registration ───────────────────────────────────────────────────────

def _update_fps_preset(self, context):
    """Update scene FPS when preset changes."""
    preset = self.oc_fps_preset
    if preset != 'CUSTOM':
        self.render.fps = int(preset)
        self.render.fps_base = 1.0


def register():
    """Register app template — called by Blender on template activation."""
    # Register custom FPS preset property on Scene
    bpy.types.Scene.oc_fps_preset = bpy.props.EnumProperty(
        name="FPS Preset",
        description="Frame rate preset",
        items=[
            ('24', "24", "24 fps (Film)"),
            ('25', "25", "25 fps (PAL)"),
            ('30', "30", "30 fps (NTSC)"),
            ('48', "48", "48 fps (HFR Film)"),
            ('60', "60", "60 fps (Games/Web)"),
            ('120', "120", "120 fps (High Speed)"),
            ('240', "240", "240 fps (Slow Motion)"),
            ('CUSTOM', "Custom", "Custom frame rate"),
        ],
        default='24',
        update=_update_fps_preset,
    )

    # Register custom playback mode property on Scene
    bpy.types.Scene.oc_playback_mode = bpy.props.EnumProperty(
        name="Playback Mode",
        description="Playback loop behavior",
        items=[
            ('LOOP', "Loop", "Loop continuously within frame range"),
            ('ONCE', "Once", "Play once and stop at end"),
            ('PINGPONG', "Ping-Pong", "Bounce back and forth"),
        ],
        default='LOOP',
    )

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

    # Register viewer tool classes
    for cls in _viewer_tool_classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

    # Register panel classes (toolbar)
    for cls in _panel_classes:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass

    # Register splash dismiss operator
    try:
        bpy.utils.register_class(OC_OT_dismiss_splash)
    except RuntimeError:
        pass

    _override_topbar()
    _override_node_header()
    _override_view3d_header()
    _override_time_header()
    _override_splash()
    _override_splash_about()
    _override_quick_setup()
    _apply_dark_theme()
    _clear_default_node_keymaps()
    _setup_keymaps()

    # NOTE: Context-sensitive node tools (like Nuke) will be added later
    # For now, the VIEW_3D toolbar is hidden since 3D tools aren't useful

    # Zoom at mouse cursor (industry standard, not center of panel)
    bpy.context.preferences.inputs.use_zoom_to_mouse = True

    # Disable splash screen for now (dismissal not working properly)
    bpy.context.preferences.view.show_splash = False

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
    # Remove custom properties
    if hasattr(bpy.types.Scene, "oc_fps_preset"):
        del bpy.types.Scene.oc_fps_preset
    if hasattr(bpy.types.Scene, "oc_playback_mode"):
        del bpy.types.Scene.oc_playback_mode

    _teardown_keymaps()
    _restore_topbar()
    _restore_node_header()
    _restore_view3d_header()
    _restore_time_header()
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

    # Unregister viewer tool classes
    for cls in reversed(_viewer_tool_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

    # Unregister panel classes
    for cls in reversed(_panel_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

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

    # Unregister splash dismiss operator
    try:
        bpy.utils.unregister_class(OC_OT_dismiss_splash)
    except RuntimeError:
        pass

    print("[OpenComp] App template unregistered")
