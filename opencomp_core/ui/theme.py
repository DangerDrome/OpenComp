"""OpenComp UI Theme — Nuke-style dark theme.

Sets Blender's theme to match Nuke's look and feel.
"""

import bpy


# Nuke color palette
NUKE_BG_DARK = (0.16, 0.16, 0.16)       # Main background
NUKE_BG_MID = (0.22, 0.22, 0.22)        # Panel background
NUKE_BG_LIGHT = (0.28, 0.28, 0.28)      # Button background
NUKE_ACCENT = (0.2, 0.7, 0.4)           # Green accent (OpenComp's signature)
NUKE_ACCENT_LIGHT = (0.3, 0.85, 0.5)    # Bright green for selection
NUKE_TEXT = (0.85, 0.85, 0.85)          # Main text
NUKE_TEXT_DIM = (0.5, 0.5, 0.5)         # Dimmed text
NUKE_BORDER = (0.1, 0.1, 0.1)           # Border color
NUKE_NODE_BACKDROP = (0.18, 0.18, 0.18) # Node graph background
NUKE_TEXT_WHITE = (1.0, 1.0, 1.0)       # White text for selection


def _set_color(obj, attr, color_rgb, alpha=1.0):
    """Set a color property, trying RGBA first then RGB.

    Some Blender properties expect RGB (3 values), others expect RGBA (4 values).
    This helper tries both formats.

    If alpha is None, only RGB is used (for text properties).
    """
    if alpha is None:
        # Text properties only accept RGB
        try:
            setattr(obj, attr, color_rgb)
        except Exception:
            pass
    else:
        try:
            # Try RGBA first (4 values)
            setattr(obj, attr, (*color_rgb, alpha))
        except Exception:
            try:
                # Fall back to RGB (3 values)
                setattr(obj, attr, color_rgb)
            except Exception:
                pass  # Silently ignore if both fail


def apply_nuke_theme():
    """Apply Nuke-style theme to Blender."""
    try:
        prefs = bpy.context.preferences
        theme = prefs.themes[0]

        # User Interface
        ui = theme.user_interface

        # Widget colors - text properties take RGB (3), others take RGBA (4)
        wcol_regular = ui.wcol_regular
        _set_color(wcol_regular, 'inner', NUKE_BG_LIGHT)
        _set_color(wcol_regular, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_regular, 'item', NUKE_BG_MID)
        _set_color(wcol_regular, 'text', NUKE_TEXT, alpha=None)  # RGB only
        _set_color(wcol_regular, 'text_sel', NUKE_TEXT_WHITE, alpha=None)
        _set_color(wcol_regular, 'outline', NUKE_BORDER)

        # Tool widgets
        wcol_tool = ui.wcol_tool
        _set_color(wcol_tool, 'inner', NUKE_BG_LIGHT)
        _set_color(wcol_tool, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_tool, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_tool, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Radio buttons
        wcol_radio = ui.wcol_radio
        _set_color(wcol_radio, 'inner', NUKE_BG_MID)
        _set_color(wcol_radio, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_radio, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_radio, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Text fields
        wcol_text = ui.wcol_text
        _set_color(wcol_text, 'inner', NUKE_BG_DARK)
        _set_color(wcol_text, 'inner_sel', NUKE_ACCENT, alpha=0.5)
        _set_color(wcol_text, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_text, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Option widgets
        wcol_option = ui.wcol_option
        _set_color(wcol_option, 'inner', NUKE_BG_MID)
        _set_color(wcol_option, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_option, 'text', NUKE_TEXT, alpha=None)

        # Number fields
        wcol_num = ui.wcol_num
        _set_color(wcol_num, 'inner', NUKE_BG_DARK)
        _set_color(wcol_num, 'inner_sel', NUKE_ACCENT, alpha=0.5)
        _set_color(wcol_num, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_num, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Number slider
        wcol_numslider = ui.wcol_numslider
        _set_color(wcol_numslider, 'inner', NUKE_BG_DARK)
        _set_color(wcol_numslider, 'inner_sel', NUKE_ACCENT, alpha=0.5)
        _set_color(wcol_numslider, 'item', NUKE_ACCENT)
        _set_color(wcol_numslider, 'text', NUKE_TEXT, alpha=None)

        # Box
        wcol_box = ui.wcol_box
        _set_color(wcol_box, 'inner', NUKE_BG_MID, alpha=0.8)
        _set_color(wcol_box, 'outline', NUKE_BORDER)

        # Menu
        wcol_menu = ui.wcol_menu
        _set_color(wcol_menu, 'inner', NUKE_BG_MID)
        _set_color(wcol_menu, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_menu, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_menu, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Pulldown menu
        wcol_pulldown = ui.wcol_pulldown
        _set_color(wcol_pulldown, 'inner', NUKE_BG_MID)
        _set_color(wcol_pulldown, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_pulldown, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_pulldown, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Menu back
        wcol_menu_back = ui.wcol_menu_back
        _set_color(wcol_menu_back, 'inner', NUKE_BG_DARK, alpha=0.95)
        _set_color(wcol_menu_back, 'outline', NUKE_BORDER)

        # Menu item
        wcol_menu_item = ui.wcol_menu_item
        _set_color(wcol_menu_item, 'inner', (0, 0, 0), alpha=0)
        _set_color(wcol_menu_item, 'inner_sel', NUKE_ACCENT)
        _set_color(wcol_menu_item, 'text', NUKE_TEXT, alpha=None)
        _set_color(wcol_menu_item, 'text_sel', NUKE_TEXT_WHITE, alpha=None)

        # Tooltip
        wcol_tooltip = ui.wcol_tooltip
        _set_color(wcol_tooltip, 'inner', NUKE_BG_DARK, alpha=0.95)
        _set_color(wcol_tooltip, 'text', NUKE_TEXT, alpha=None)

        # Icon colors
        ui.icon_alpha = 1.0

        # 3D View / Viewer
        view3d = theme.view_3d
        _set_color(view3d.space.gradients, 'high_gradient', NUKE_BG_DARK)
        _set_color(view3d.space.gradients, 'gradient', NUKE_BG_DARK)

        # Node Editor
        node_editor = theme.node_editor
        _set_color(node_editor.space, 'back', NUKE_NODE_BACKDROP)
        _set_color(node_editor, 'grid', NUKE_BG_MID, alpha=0.5)
        _set_color(node_editor, 'node_selected', NUKE_ACCENT_LIGHT)
        _set_color(node_editor, 'node_active', NUKE_ACCENT)
        _set_color(node_editor, 'wire', NUKE_TEXT_DIM)
        _set_color(node_editor, 'wire_select', NUKE_ACCENT_LIGHT)

        # Properties
        props = theme.properties
        _set_color(props.space, 'back', NUKE_BG_MID)

        # Timeline / Dopesheet
        dopesheet = theme.dopesheet_editor
        _set_color(dopesheet.space, 'back', NUKE_BG_DARK)
        _set_color(dopesheet, 'grid', NUKE_BG_LIGHT, alpha=0.5)

        # Text Editor (for any script panels)
        text_editor = theme.text_editor
        _set_color(text_editor.space, 'back', NUKE_BG_DARK)
        _set_color(text_editor, 'line_numbers', NUKE_TEXT_DIM)

        # Header
        _set_color(theme.view_3d.space, 'header', NUKE_BG_MID)
        _set_color(theme.node_editor.space, 'header', NUKE_BG_MID)
        _set_color(theme.properties.space, 'header', NUKE_BG_MID)
        _set_color(theme.dopesheet_editor.space, 'header', NUKE_BG_MID)

        print("[OpenComp] Nuke theme applied")
    except Exception as e:
        print(f"[OpenComp] Theme setup error: {e}")


def register():
    """Apply the Nuke theme on registration."""
    # Delay theme application to ensure Blender is fully loaded
    bpy.app.timers.register(apply_nuke_theme, first_interval=0.1)


def unregister():
    """Nothing to unregister - theme persists."""
    pass
