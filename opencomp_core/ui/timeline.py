"""OpenComp Timeline — Nuke-style timeline.

Replaces Blender's Dopesheet/Timeline with clean playback controls.
All UI is GPU-drawn to completely replace Blender's look.
"""

import bpy
from bpy.types import Header
import gpu
from gpu_extras.batch import batch_for_shader
import blf


_timeline_draw_handler = None
_timeline_header_handler = None


def _draw_background(width, height, color):
    """Draw solid background."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    verts = [(0, 0), (width, 0), (width, height), (0, height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_timeline_header():
    """Draw custom GPU header for timeline."""
    context = bpy.context
    if context.area is None or context.area.type != 'DOPESHEET_EDITOR':
        return

    # Find header region
    region = None
    for r in context.area.regions:
        if r.type == 'HEADER':
            region = r
            break

    if region is None or region.height < 5:
        return

    scene = context.scene
    gpu.state.blend_set('ALPHA')

    # Draw dark header background
    _draw_background(region.width, region.height, (0.20, 0.20, 0.20, 1.0))

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    x = 10
    y = (region.height - 12) // 2 + 2

    # Timeline label
    blf.size(0, 13)
    blf.color(0, 0.9, 0.55, 0.2, 1.0)  # Orange
    blf.position(0, x, y, 0)
    blf.draw(0, "Timeline")
    x += 80

    # Separator
    sep_verts = [(x, 5), (x, region.height - 5)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 15

    # Playback button indicators (simplified)
    blf.size(0, 11)
    playback_symbols = ["⏮", "⏪", "⏵", "⏩", "⏭"]
    blf.color(0, 0.7, 0.7, 0.7, 1.0)

    for symbol in playback_symbols:
        blf.position(0, x, y, 0)
        blf.draw(0, symbol)
        x += 25

    x += 10

    # Separator
    sep_verts = [(x, 5), (x, region.height - 5)]
    batch = batch_for_shader(shader, 'LINES', {"pos": sep_verts})
    shader.bind()
    shader.uniform_float("color", (0.35, 0.35, 0.35, 1.0))
    batch.draw(shader)
    x += 15

    # Frame counter
    blf.color(0, 0.9, 0.9, 0.9, 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, f"Frame: {scene.frame_current}")
    x += 100

    # Frame range
    blf.color(0, 0.6, 0.6, 0.6, 1.0)
    blf.position(0, x, y, 0)
    blf.draw(0, f"[{scene.frame_start} - {scene.frame_end}]")

    # FPS on the right
    fps_text = f"{scene.render.fps} fps"
    text_width, _ = blf.dimensions(0, fps_text)
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    blf.position(0, region.width - text_width - 15, y, 0)
    blf.draw(0, fps_text)

    gpu.state.blend_set('NONE')


def _draw_timeline_overlay():
    """Draw Nuke-style timeline overlay."""
    context = bpy.context
    if context.area is None or context.area.type != 'DOPESHEET_EDITOR':
        return

    region = context.region
    scene = context.scene

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    # Draw background
    _draw_background(region.width, region.height, (0.14, 0.14, 0.14, 1.0))

    # Draw frame markers
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    frame_current = scene.frame_current

    if frame_end > frame_start:
        # Calculate timeline area
        margin = 50
        timeline_width = region.width - (margin * 2)
        timeline_y = region.height / 2

        # Draw timeline bar
        bar_height = 4
        bar_verts = [
            (margin, timeline_y - bar_height/2),
            (margin + timeline_width, timeline_y - bar_height/2),
            (margin + timeline_width, timeline_y + bar_height/2),
            (margin, timeline_y + bar_height/2),
        ]
        indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": bar_verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
        batch.draw(shader)

        # Draw tick marks
        num_ticks = min(20, frame_end - frame_start + 1)
        tick_step = (frame_end - frame_start) / num_ticks
        for i in range(num_ticks + 1):
            tick_frame = frame_start + i * tick_step
            tick_x = margin + (tick_frame - frame_start) / (frame_end - frame_start) * timeline_width
            tick_height = 6 if i % 5 == 0 else 3
            tick_verts = [(tick_x, timeline_y - tick_height), (tick_x, timeline_y + tick_height)]
            batch = batch_for_shader(shader, 'LINES', {"pos": tick_verts})
            shader.bind()
            shader.uniform_float("color", (0.4, 0.4, 0.4, 1.0))
            batch.draw(shader)

        # Draw current frame indicator (playhead)
        frame_pos = margin + (frame_current - frame_start) / (frame_end - frame_start) * timeline_width

        # Playhead line
        playhead_verts = [(frame_pos, 10), (frame_pos, region.height - 10)]
        batch = batch_for_shader(shader, 'LINES', {"pos": playhead_verts})
        shader.bind()
        shader.uniform_float("color", (0.9, 0.5, 0.1, 0.8))
        batch.draw(shader)

        # Playhead diamond
        indicator_size = 8
        indicator_verts = [
            (frame_pos, timeline_y - indicator_size),
            (frame_pos + indicator_size, timeline_y),
            (frame_pos, timeline_y + indicator_size),
            (frame_pos - indicator_size, timeline_y),
        ]
        indicator_indices = [(0, 1, 2), (0, 2, 3)]
        batch = batch_for_shader(shader, 'TRIS', {"pos": indicator_verts}, indices=indicator_indices)
        shader.bind()
        shader.uniform_float("color", (0.9, 0.5, 0.1, 1.0))  # Orange
        batch.draw(shader)

        # Draw frame number above playhead
        blf.size(0, 14)
        blf.color(0, 0.9, 0.9, 0.9, 1.0)
        frame_text = str(frame_current)
        text_width, text_height = blf.dimensions(0, frame_text)
        blf.position(0, frame_pos - text_width/2, timeline_y + indicator_size + 8, 0)
        blf.draw(0, frame_text)

        # Draw start/end labels
        blf.size(0, 11)
        blf.color(0, 0.5, 0.5, 0.5, 1.0)
        blf.position(0, margin, timeline_y - 25, 0)
        blf.draw(0, str(frame_start))

        end_text = str(frame_end)
        end_width, _ = blf.dimensions(0, end_text)
        blf.position(0, margin + timeline_width - end_width, timeline_y - 25, 0)
        blf.draw(0, end_text)

    gpu.state.blend_set('NONE')


class OC_HT_timeline_header(Header):
    """Empty header - we draw our own via GPU."""
    bl_space_type = 'DOPESHEET_EDITOR'

    def draw(self, context):
        # Empty - GPU handler draws our header
        pass


classes = [
    OC_HT_timeline_header,
]


def _hide_timeline_regions():
    """Hide the channels and UI regions in the timeline."""
    for area in bpy.context.screen.areas:
        if area.type == 'DOPESHEET_EDITOR':
            space = area.spaces.active
            # Hide the channels region (left panel)
            if hasattr(space, 'show_region_channels'):
                space.show_region_channels = False
            # Hide the UI region (right sidebar)
            if hasattr(space, 'show_region_ui'):
                space.show_region_ui = False
    return None  # Don't repeat timer


def register():
    global _timeline_draw_handler, _timeline_header_handler

    for cls in classes:
        bpy.utils.register_class(cls)

    # Register draw handlers
    _timeline_draw_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
        _draw_timeline_overlay, (), 'WINDOW', 'POST_PIXEL'
    )

    _timeline_header_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
        _draw_timeline_header, (), 'HEADER', 'POST_PIXEL'
    )

    # Hide the channels/UI regions after a short delay
    bpy.app.timers.register(_hide_timeline_regions, first_interval=0.3)

    # Unregister default header
    try:
        bpy.utils.unregister_class(bpy.types.DOPESHEET_HT_header)
    except:
        pass


def unregister():
    global _timeline_draw_handler, _timeline_header_handler

    if _timeline_draw_handler:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_timeline_draw_handler, 'WINDOW')
        _timeline_draw_handler = None

    if _timeline_header_handler:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_timeline_header_handler, 'HEADER')
        _timeline_header_handler = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
