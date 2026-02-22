"""OpenComp Viewer keymaps — Ctrl+1..5 routing, zoom, pan, ROI, channels, fit.

Registered in the 3D View keymap. Safe to call in --background mode
(keyconfigs.addon may be None — handled gracefully).

Blender's default 3D View navigation (orbit, zoom, dolly, move) uses the
same keys we need (MIDDLEMOUSE, WHEELUP/DOWN). Since we draw on a screen-
space quad via POST_PIXEL, Blender's 3D navigation has no visible effect
but still eats our events. We deactivate the conflicting default items on
register and restore them on unregister.
"""

import bpy

_keymaps = []
_disabled_default_items = []


def _disable_default_3d_navigation():
    """Deactivate default 3D View navigation keymaps that conflict with viewer."""
    wm = bpy.context.window_manager

    # Try active keyconfig first (what Blender actually processes)
    for kc in (wm.keyconfigs.active, wm.keyconfigs.default):
        if kc is None:
            continue
        km = kc.keymaps.get('3D View')
        if km is None:
            continue
        _conflicting = {
            'view3d.rotate', 'view3d.zoom', 'view3d.move', 'view3d.dolly',
        }
        for kmi in km.keymap_items:
            if kmi.idname in _conflicting and kmi.active:
                kmi.active = False
                _disabled_default_items.append(kmi)
        break  # only need to hit one keyconfig


def _restore_default_3d_navigation():
    """Re-activate default 3D View navigation keymaps."""
    for kmi in _disabled_default_items:
        try:
            kmi.active = True
        except Exception:
            pass
    _disabled_default_items.clear()


def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return

    # Disable conflicting Blender defaults so our events aren't swallowed
    _disable_default_3d_navigation()

    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

    # Ctrl+1..5 route to viewer (regular number row)
    _key_names = ['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE']
    for i, key in enumerate(_key_names, start=1):
        kmi = km.keymap_items.new("oc.viewer_route", key, 'PRESS', ctrl=True)
        kmi.properties.index = i
        _keymaps.append((km, kmi))

    # Zoom — mouse wheel
    kmi = km.keymap_items.new("oc.viewer_zoom_in", 'WHEELUPMOUSE', 'PRESS')
    _keymaps.append((km, kmi))
    kmi = km.keymap_items.new("oc.viewer_zoom_out", 'WHEELDOWNMOUSE', 'PRESS')
    _keymaps.append((km, kmi))

    # Pan — middle mouse drag
    kmi = km.keymap_items.new("oc.viewer_pan", 'MIDDLEMOUSE', 'PRESS')
    _keymaps.append((km, kmi))

    # ROI — Ctrl+left mouse drag
    kmi = km.keymap_items.new("oc.viewer_roi", 'LEFTMOUSE', 'PRESS', ctrl=True)
    _keymaps.append((km, kmi))

    # Channel isolation hotkeys
    _channel_keys = [
        ('R', 'R'),
        ('G', 'G'),
        ('B', 'B'),
        ('A', 'A'),
        ('Y', 'LUMA'),
    ]
    for key, channel in _channel_keys:
        kmi = km.keymap_items.new("oc.viewer_set_channel", key, 'PRESS')
        kmi.properties.channel = channel
        _keymaps.append((km, kmi))

    # Fit to window
    kmi = km.keymap_items.new("oc.viewer_fit", 'HOME', 'PRESS')
    _keymaps.append((km, kmi))
    kmi = km.keymap_items.new("oc.viewer_fit", 'F', 'PRESS')
    _keymaps.append((km, kmi))


def unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()

    # Restore Blender's default 3D navigation
    _restore_default_3d_navigation()
