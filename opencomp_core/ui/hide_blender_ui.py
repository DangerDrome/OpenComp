"""Hide ALL default Blender UI elements.

This module aggressively removes/hides all default Blender panels,
headers, and menus to make room for our Nuke-style UI.
"""

import bpy

_hidden_classes = []
_draw_handlers = []


def hide_all_default_ui():
    """Hide all default Blender UI classes."""
    global _hidden_classes
    _hidden_classes.clear()

    # Panels to hide (by prefix) - be very comprehensive
    # NOTE: NODE_PT_ is NOT hidden - we need node editor panels to work
    panel_prefixes = [
        # Properties panels
        'OBJECT_PT_', 'MESH_PT_', 'CURVE_PT_', 'SURFACE_PT_',
        'MATERIAL_PT_', 'WORLD_PT_', 'DATA_PT_', 'PHYSICS_PT_',
        'PARTICLE_PT_', 'CONSTRAINT_PT_', 'MODIFIER_PT_', 'BONE_PT_',
        'ARMATURE_PT_', 'RENDER_PT_', 'OUTPUT_PT_', 'SCENE_PT_',
        'LAYER_PT_', 'VIEW_LAYER_PT_', 'VIEWLAYER_PT_', 'CYCLES_PT_',
        'EEVEE_PT_', 'COLLECTION_PT_', 'CAMERA_PT_', 'LIGHT_PT_',
        'TEXTURE_PT_', 'GPENCIL_PT_', 'SHADERFX_PT_',
        # View3D panels
        'VIEW3D_PT_',
        # Dopesheet panels
        'DOPESHEET_PT_', 'ACTION_PT_',
        # Sequencer panels
        'SEQUENCER_PT_',
        # Other editors
        # NOTE: FILEBROWSER_PT_ is NOT hidden - we need the file browser to work
        'TOPBAR_PT_', 'CLIP_PT_', 'NLA_PT_',
        'GRAPH_PT_', 'IMAGE_PT_', 'TEXT_PT_', 'CONSOLE_PT_',
        'INFO_PT_', 'OUTLINER_PT_', 'SPREADSHEET_PT_', 'USERPREF_PT_',
        'PREFERENCES_PT_', 'STATUSBAR_PT_',
    ]

    # Headers to hide - all editor types
    # NOTE: NODE_HT_header is NOT hidden - we need it for the Add menu
    # NOTE: FILEBROWSER_HT_header is NOT hidden - we need the file browser to work
    header_classes = [
        'VIEW3D_HT_header', 'VIEW3D_HT_tool_header',
        'PROPERTIES_HT_header', 'DOPESHEET_HT_header',
        'TOPBAR_HT_upper_bar',
        'OUTLINER_HT_header',
        'INFO_HT_header', 'GRAPH_HT_header', 'NLA_HT_header',
        'IMAGE_HT_header', 'IMAGE_HT_tool_header',
        'SEQUENCER_HT_header', 'SEQUENCER_HT_tool_header',
        'CLIP_HT_header', 'TEXT_HT_header', 'TEXT_HT_footer',
        'CONSOLE_HT_header', 'SPREADSHEET_HT_header',
        'STATUSBAR_HT_header', 'USERPREF_HT_header',
    ]

    # Menus to hide
    # NOTE: NODE_MT_editor_menus is NOT hidden - we need node editor menus
    menu_classes = [
        'TOPBAR_MT_file', 'TOPBAR_MT_file_new', 'TOPBAR_MT_file_recover',
        'TOPBAR_MT_file_defaults', 'TOPBAR_MT_edit', 'TOPBAR_MT_render',
        'TOPBAR_MT_window', 'TOPBAR_MT_help', 'TOPBAR_MT_editor_menus',
        'VIEW3D_MT_editor_menus',
        'DOPESHEET_MT_editor_menus', 'GRAPH_MT_editor_menus',
        'NLA_MT_editor_menus', 'IMAGE_MT_editor_menus',
        'SEQUENCER_MT_editor_menus', 'CLIP_MT_editor_menus',
        'TEXT_MT_editor_menus', 'OUTLINER_MT_editor_menus',
    ]

    count = 0

    # Hide panels by prefix
    for name in dir(bpy.types):
        for prefix in panel_prefixes:
            if name.startswith(prefix):
                try:
                    cls = getattr(bpy.types, name)
                    if hasattr(cls, 'bl_rna'):
                        bpy.utils.unregister_class(cls)
                        _hidden_classes.append(cls)
                        count += 1
                except Exception:
                    pass
                break  # Found match, no need to check other prefixes

    # Hide headers
    for name in header_classes:
        try:
            cls = getattr(bpy.types, name)
            bpy.utils.unregister_class(cls)
            _hidden_classes.append(cls)
            count += 1
        except Exception:
            pass

    # Hide menus
    for name in menu_classes:
        try:
            cls = getattr(bpy.types, name)
            bpy.utils.unregister_class(cls)
            _hidden_classes.append(cls)
            count += 1
        except Exception:
            pass

    print(f"[OpenComp] Hidden {count} default Blender UI classes")
    return None  # Don't repeat timer


def restore_default_ui():
    """Restore all hidden default UI classes."""
    global _hidden_classes
    count = 0
    for cls in reversed(_hidden_classes):
        try:
            bpy.utils.register_class(cls)
            count += 1
        except Exception:
            pass
    _hidden_classes.clear()
    if count > 0:
        print(f"[OpenComp] Restored {count} default Blender UI classes")


def register():
    # DISABLED: Don't hide Blender UI - use native Blender interface for v0.2
    # hide_all_default_ui()
    print("[OpenComp] UI hiding disabled - using native Blender interface")


def unregister():
    restore_default_ui()
