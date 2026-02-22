"""OpenComp UI Theme — Nuke-style dark theme.

Sets Blender's theme to match Nuke's look and feel.
"""

import bpy


# Nuke color palette
NUKE_BG_DARK = (0.16, 0.16, 0.16)       # Main background
NUKE_BG_MID = (0.22, 0.22, 0.22)        # Panel background
NUKE_BG_LIGHT = (0.28, 0.28, 0.28)      # Button background
NUKE_ACCENT = (0.8, 0.45, 0.1)          # Orange accent (Nuke's signature)
NUKE_ACCENT_LIGHT = (1.0, 0.6, 0.2)     # Bright orange for selection
NUKE_TEXT = (0.85, 0.85, 0.85)          # Main text
NUKE_TEXT_DIM = (0.5, 0.5, 0.5)         # Dimmed text
NUKE_BORDER = (0.1, 0.1, 0.1)           # Border color
NUKE_NODE_BACKDROP = (0.18, 0.18, 0.18) # Node graph background


def apply_nuke_theme():
    """Apply Nuke-style theme to Blender."""
    prefs = bpy.context.preferences
    theme = prefs.themes[0]

    # User Interface
    ui = theme.user_interface

    # Widget colors
    wcol_regular = ui.wcol_regular
    wcol_regular.inner = (*NUKE_BG_LIGHT, 1.0)
    wcol_regular.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_regular.item = (*NUKE_BG_MID, 1.0)
    wcol_regular.text = (*NUKE_TEXT, 1.0)
    wcol_regular.text_sel = (1.0, 1.0, 1.0, 1.0)
    wcol_regular.outline = (*NUKE_BORDER, 1.0)

    # Tool widgets
    wcol_tool = ui.wcol_tool
    wcol_tool.inner = (*NUKE_BG_LIGHT, 1.0)
    wcol_tool.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_tool.text = (*NUKE_TEXT, 1.0)
    wcol_tool.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Radio buttons
    wcol_radio = ui.wcol_radio
    wcol_radio.inner = (*NUKE_BG_MID, 1.0)
    wcol_radio.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_radio.text = (*NUKE_TEXT, 1.0)
    wcol_radio.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Text fields
    wcol_text = ui.wcol_text
    wcol_text.inner = (*NUKE_BG_DARK, 1.0)
    wcol_text.inner_sel = (*NUKE_ACCENT, 0.5)
    wcol_text.text = (*NUKE_TEXT, 1.0)
    wcol_text.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Option widgets
    wcol_option = ui.wcol_option
    wcol_option.inner = (*NUKE_BG_MID, 1.0)
    wcol_option.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_option.text = (*NUKE_TEXT, 1.0)

    # Number fields
    wcol_num = ui.wcol_num
    wcol_num.inner = (*NUKE_BG_DARK, 1.0)
    wcol_num.inner_sel = (*NUKE_ACCENT, 0.5)
    wcol_num.text = (*NUKE_TEXT, 1.0)
    wcol_num.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Number slider
    wcol_numslider = ui.wcol_numslider
    wcol_numslider.inner = (*NUKE_BG_DARK, 1.0)
    wcol_numslider.inner_sel = (*NUKE_ACCENT, 0.5)
    wcol_numslider.item = (*NUKE_ACCENT, 1.0)
    wcol_numslider.text = (*NUKE_TEXT, 1.0)

    # Box
    wcol_box = ui.wcol_box
    wcol_box.inner = (*NUKE_BG_MID, 0.8)
    wcol_box.outline = (*NUKE_BORDER, 1.0)

    # Menu
    wcol_menu = ui.wcol_menu
    wcol_menu.inner = (*NUKE_BG_MID, 1.0)
    wcol_menu.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_menu.text = (*NUKE_TEXT, 1.0)
    wcol_menu.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Pulldown menu
    wcol_pulldown = ui.wcol_pulldown
    wcol_pulldown.inner = (*NUKE_BG_MID, 1.0)
    wcol_pulldown.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_pulldown.text = (*NUKE_TEXT, 1.0)
    wcol_pulldown.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Menu back
    wcol_menu_back = ui.wcol_menu_back
    wcol_menu_back.inner = (*NUKE_BG_DARK, 0.95)
    wcol_menu_back.outline = (*NUKE_BORDER, 1.0)

    # Menu item
    wcol_menu_item = ui.wcol_menu_item
    wcol_menu_item.inner = (0, 0, 0, 0)
    wcol_menu_item.inner_sel = (*NUKE_ACCENT, 1.0)
    wcol_menu_item.text = (*NUKE_TEXT, 1.0)
    wcol_menu_item.text_sel = (1.0, 1.0, 1.0, 1.0)

    # Tooltip
    wcol_tooltip = ui.wcol_tooltip
    wcol_tooltip.inner = (*NUKE_BG_DARK, 0.95)
    wcol_tooltip.text = (*NUKE_TEXT, 1.0)

    # Icon colors
    ui.icon_alpha = 1.0

    # 3D View / Viewer
    view3d = theme.view_3d
    view3d.space.gradients.high_gradient = (*NUKE_BG_DARK, 1.0)
    view3d.space.gradients.gradient = (*NUKE_BG_DARK, 1.0)

    # Node Editor
    node_editor = theme.node_editor
    node_editor.space.back = (*NUKE_NODE_BACKDROP, 1.0)
    node_editor.grid = (*NUKE_BG_MID, 0.5)
    node_editor.node_selected = (*NUKE_ACCENT_LIGHT, 1.0)
    node_editor.node_active = (*NUKE_ACCENT, 1.0)
    node_editor.wire = (*NUKE_TEXT_DIM, 1.0)
    node_editor.wire_select = (*NUKE_ACCENT_LIGHT, 1.0)

    # Properties
    props = theme.properties
    props.space.back = (*NUKE_BG_MID, 1.0)

    # Timeline / Dopesheet
    dopesheet = theme.dopesheet_editor
    dopesheet.space.back = (*NUKE_BG_DARK, 1.0)
    dopesheet.grid = (*NUKE_BG_LIGHT, 0.5)

    # Text Editor (for any script panels)
    text = theme.text_editor
    text.space.back = (*NUKE_BG_DARK, 1.0)
    text.line_numbers = (*NUKE_TEXT_DIM, 1.0)

    # Header
    theme.view_3d.space.header = (*NUKE_BG_MID, 1.0)
    theme.node_editor.space.header = (*NUKE_BG_MID, 1.0)
    theme.properties.space.header = (*NUKE_BG_MID, 1.0)
    theme.dopesheet_editor.space.header = (*NUKE_BG_MID, 1.0)

    print("[OpenComp] Nuke theme applied")


def register():
    """Apply the Nuke theme on registration."""
    # Delay theme application to ensure Blender is fully loaded
    bpy.app.timers.register(apply_nuke_theme, first_interval=0.1)


def unregister():
    """Nothing to unregister - theme persists."""
    pass
