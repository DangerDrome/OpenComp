"""OpenComp Viewer — Nuke-style image viewer with integrated timeline.

Replaces Blender's 3D View with a clean image viewer.
Timeline is drawn as a fixed-height strip at the bottom.
All UI is GPU-drawn to completely replace Blender's look.
"""

import bpy
from bpy.types import Header, Operator
import gpu
from gpu_extras.batch import batch_for_shader
import blf


_viewer_draw_handler = None
_viewer_header_handler = None
_viewer_tool_header_handler = None
_viewer_sidebar_handler = None

# Timeline height in pixels
TIMELINE_HEIGHT = 70

# Viewer background options
VIEWER_BG_MODES = ['Black', 'Grey', 'Checker', 'Custom']
_viewer_bg_mode = 'Black'  # Current background mode
_viewer_bg_custom_color = (0.2, 0.2, 0.2)  # Custom color RGB

# Background colors for each mode
VIEWER_BG_COLORS = {
    'Black': (0.0, 0.0, 0.0, 1.0),
    'Grey': (0.18, 0.18, 0.18, 1.0),
    'Custom': None,  # Uses _viewer_bg_custom_color
}


def get_viewer_bg_color():
    """Get current viewer background color based on mode."""
    global _viewer_bg_mode, _viewer_bg_custom_color
    if _viewer_bg_mode == 'Custom':
        return (*_viewer_bg_custom_color, 1.0)
    return VIEWER_BG_COLORS.get(_viewer_bg_mode, (0.0, 0.0, 0.0, 1.0))


def _draw_background(width, height, color):
    """Draw solid background."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    verts = [(0, 0), (width, 0), (width, height), (0, height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_checker_background(x, y, width, height, check_size=16):
    """Draw checkerboard pattern background."""
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    color1 = (0.2, 0.2, 0.2, 1.0)
    color2 = (0.3, 0.3, 0.3, 1.0)

    # Draw base color
    verts = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color1)
    batch.draw(shader)

    # Draw checker squares
    for cx in range(int(x), int(x + width), check_size * 2):
        for cy in range(int(y), int(y + height), check_size * 2):
            # Draw two squares per iteration (diagonal pattern)
            for sq in [(cx, cy + check_size), (cx + check_size, cy)]:
                sx, sy = sq
                if sx < x + width and sy < y + height:
                    sw = min(check_size, x + width - sx)
                    sh = min(check_size, y + height - sy)
                    sq_verts = [(sx, sy), (sx + sw, sy), (sx + sw, sy + sh), (sx, sy + sh)]
                    batch = batch_for_shader(shader, 'TRIS', {"pos": sq_verts}, indices=indices)
                    shader.bind()
                    shader.uniform_float("color", color2)
                    batch.draw(shader)


def _draw_viewer_header():
    """No GPU overlay for header - let Blender header show through."""
    # Header is handled by OC_HT_viewer_header class using native Blender UI
    pass


def _draw_viewer_tool_header():
    """Draw custom tool header (hide it)."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Find tool header region
    region = None
    for r in context.area.regions:
        if r.type == 'TOOL_HEADER':
            region = r
            break

    if region is None or region.height < 5:
        return

    gpu.state.blend_set('ALPHA')
    # Just draw background to hide any Blender content
    _draw_background(region.width, region.height, (0.18, 0.18, 0.18, 1.0))
    gpu.state.blend_set('NONE')


def _draw_viewer_sidebar():
    """Draw over the sidebar to hide it but prevent chevron from appearing."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Find UI region (sidebar)
    region = None
    for r in context.area.regions:
        if r.type == 'UI':
            region = r
            break

    if region is None or region.width < 2:
        return

    gpu.state.blend_set('ALPHA')
    # Match viewer background mode
    global _viewer_bg_mode
    if _viewer_bg_mode == 'Checker':
        _draw_checker_background(0, 0, region.width, region.height)
    else:
        _draw_background(region.width, region.height, get_viewer_bg_color())
    gpu.state.blend_set('NONE')


# Timeline button regions for hit testing (populated during draw)
_timeline_buttons = {}

def _draw_timeline_button(shader, x, y, w, h, icon_text, color, hover=False):
    """Draw a timeline control button."""
    # Button background
    bg_color = (0.25, 0.25, 0.25, 1.0) if hover else (0.2, 0.2, 0.2, 1.0)
    verts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", bg_color)
    batch.draw(shader)

    # Icon/text
    blf.size(0, 12)
    blf.color(0, *color)
    text_w, text_h = blf.dimensions(0, icon_text)
    blf.position(0, x + (w - text_w) / 2, y + (h - text_h) / 2, 0)
    blf.draw(0, icon_text)


def _draw_timeline_strip(region_width, timeline_height):
    """Draw the timeline strip at the bottom of the viewer with full controls.

    Layout (top to bottom):
    - Scrub bar with playhead (top section)
    - Buttons and controls (bottom section)
    """
    global _timeline_buttons
    _timeline_buttons = {}

    context = bpy.context
    scene = context.scene
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    # Timeline background
    _draw_background(region_width, timeline_height, (0.14, 0.14, 0.14, 1.0))

    # Top border line
    border_verts = [(0, timeline_height), (region_width, timeline_height)]
    batch = batch_for_shader(shader, 'LINES', {"pos": border_verts})
    shader.bind()
    shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
    batch.draw(shader)

    # Frame range
    frame_start = scene.frame_start
    frame_end = scene.frame_end
    frame_current = scene.frame_current


    # Use preview range if set
    use_preview = scene.use_preview_range
    if use_preview:
        in_point = scene.frame_preview_start
        out_point = scene.frame_preview_end
    else:
        in_point = frame_start
        out_point = frame_end

    if frame_end <= frame_start:
        return

    # Layout dimensions
    scrub_bar_y = timeline_height - 18  # Scrub bar near top
    btn_row_y = 5  # Buttons at bottom
    btn_size = 22
    btn_spacing = 2
    timeline_margin = 10
    timeline_left = timeline_margin
    timeline_right = region_width - timeline_margin
    timeline_width = timeline_right - timeline_left

    # ═══════════════════════════════════════════════════════════════════════
    # SCRUB BAR (top section) - Made highly visible
    # ═══════════════════════════════════════════════════════════════════════
    bar_height = 12
    bar_top = scrub_bar_y + bar_height/2
    bar_bottom = scrub_bar_y - bar_height/2

    # Scrub bar background - brighter gray so it's clearly visible
    bar_verts = [
        (timeline_left, bar_bottom),
        (timeline_right, bar_bottom),
        (timeline_right, bar_top),
        (timeline_left, bar_top),
    ]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": bar_verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", (0.28, 0.28, 0.30, 1.0))
    batch.draw(shader)

    # Scrub bar outline for visibility
    outline_verts = [
        (timeline_left, bar_bottom),
        (timeline_right, bar_bottom),
        (timeline_right, bar_top),
        (timeline_left, bar_top),
        (timeline_left, bar_bottom),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": outline_verts})
    shader.bind()
    shader.uniform_float("color", (0.45, 0.45, 0.45, 1.0))
    batch.draw(shader)

    # Active range highlight (in to out) - slightly brighter than bar
    if use_preview or (in_point != frame_start or out_point != frame_end):
        in_x = timeline_left + (in_point - frame_start) / (frame_end - frame_start) * timeline_width
        out_x = timeline_left + (out_point - frame_start) / (frame_end - frame_start) * timeline_width
        active_verts = [
            (in_x, bar_bottom),
            (out_x, bar_bottom),
            (out_x, bar_top),
            (in_x, bar_top),
        ]
        batch = batch_for_shader(shader, 'TRIS', {"pos": active_verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", (0.35, 0.35, 0.40, 1.0))
        batch.draw(shader)

    # In point marker (green bracket) - extends beyond bar
    in_x = timeline_left + (in_point - frame_start) / (frame_end - frame_start) * timeline_width
    gpu.state.line_width_set(2.0)
    in_bracket = [
        (in_x, bar_bottom - 4), (in_x, bar_top + 8),
    ]
    batch = batch_for_shader(shader, 'LINES', {"pos": in_bracket})
    shader.bind()
    shader.uniform_float("color", (0.2, 0.55, 0.35, 1.0))
    batch.draw(shader)
    _timeline_buttons["in_point"] = (in_x - 5, bar_bottom - 6, 10, bar_height + 16)

    # Out point marker (orange bracket) - extends beyond bar
    out_x = timeline_left + (out_point - frame_start) / (frame_end - frame_start) * timeline_width
    out_bracket = [
        (out_x, bar_bottom - 4), (out_x, bar_top + 8),
    ]
    batch = batch_for_shader(shader, 'LINES', {"pos": out_bracket})
    shader.bind()
    shader.uniform_float("color", (1.0, 0.6, 0.2, 1.0))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    _timeline_buttons["out_point"] = (out_x - 5, bar_bottom - 6, 10, bar_height + 16)

    # Tick marks - brighter for visibility
    num_ticks = min(25, frame_end - frame_start + 1)
    if num_ticks > 0:
        tick_step = (frame_end - frame_start) / num_ticks
        for i in range(num_ticks + 1):
            tick_frame = frame_start + i * tick_step
            tick_x = timeline_left + (tick_frame - frame_start) / (frame_end - frame_start) * timeline_width
            tick_h = 6 if i % 5 == 0 else 3
            tick_verts = [(tick_x, scrub_bar_y - tick_h), (tick_x, scrub_bar_y + tick_h)]
            batch = batch_for_shader(shader, 'LINES', {"pos": tick_verts})
            shader.bind()
            shader.uniform_float("color", (0.55, 0.55, 0.55, 1.0))
            batch.draw(shader)

    # Store scrub area for click detection (slightly larger than visual bar)
    scrub_padding = 4
    _timeline_buttons["scrub_area"] = (timeline_left, bar_bottom - scrub_padding, timeline_width, bar_height + scrub_padding * 2)

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE BAR - Shows which frames are cached (Nuke-style green bar)
    # ═══════════════════════════════════════════════════════════════════════
    try:
        from ..nodes.viewer.viewer import get_cached_frames
        cached_frames = get_cached_frames()
        if cached_frames:
            cache_bar_height = 5  # Taller for visibility
            cache_bar_y = bar_bottom - 8  # Just below the scrub bar

            # Draw cached frame indicators
            for cached_frame in cached_frames:
                if frame_start <= cached_frame <= frame_end:
                    # Calculate position for this frame
                    cache_x = timeline_left + (cached_frame - frame_start) / (frame_end - frame_start) * timeline_width
                    # Draw a green rectangle for each cached frame
                    pixel_width = max(3, timeline_width / (frame_end - frame_start + 1))
                    cache_verts = [
                        (cache_x, cache_bar_y),
                        (cache_x + pixel_width, cache_bar_y),
                        (cache_x + pixel_width, cache_bar_y + cache_bar_height),
                        (cache_x, cache_bar_y + cache_bar_height),
                    ]
                    batch = batch_for_shader(shader, 'TRIS', {"pos": cache_verts}, indices=indices)
                    shader.bind()
                    shader.uniform_float("color", (0.2, 0.55, 0.35, 1.0))  # OpenComp accent
                    batch.draw(shader)
    except Exception as e:
        print(f"[OpenComp] Cache bar error: {e}")

    # PLAYHEAD - bright RED line with triangle (highly visible)
    # Clamp current frame to valid range for display
    display_frame = max(frame_start, min(frame_end, frame_current))
    frame_pos = timeline_left + (display_frame - frame_start) / (frame_end - frame_start) * timeline_width
    # Clamp position to timeline bounds
    frame_pos = max(timeline_left, min(timeline_right, frame_pos))

    # Playhead glow/shadow (wider, darker line behind)
    gpu.state.line_width_set(7.0)
    playhead_verts = [(frame_pos, bar_bottom - 8), (frame_pos, bar_top + 14)]
    batch = batch_for_shader(shader, 'LINES', {"pos": playhead_verts})
    shader.bind()
    shader.uniform_float("color", (0.0, 0.0, 0.0, 0.5))
    batch.draw(shader)

    # Playhead main line - BRIGHT RED for maximum visibility
    gpu.state.line_width_set(4.0)
    batch = batch_for_shader(shader, 'LINES', {"pos": playhead_verts})
    shader.bind()
    shader.uniform_float("color", (1.0, 0.2, 0.2, 1.0))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)

    # Playhead triangle handle (at top) - also red
    tri_size = 10
    tri_verts = [
        (frame_pos - tri_size, bar_top + 14),
        (frame_pos + tri_size, bar_top + 14),
        (frame_pos, bar_top),
    ]
    batch = batch_for_shader(shader, 'TRIS', {"pos": tri_verts})
    shader.bind()
    shader.uniform_float("color", (1.0, 0.2, 0.2, 1.0))
    batch.draw(shader)

    # ═══════════════════════════════════════════════════════════════════════
    # CONTROLS ROW (bottom section)
    # ═══════════════════════════════════════════════════════════════════════
    btn_x = 8

    # Go to start |<
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, "|<", (0.7, 0.7, 0.7, 1.0))
    _timeline_buttons["goto_start"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing

    # Step back <
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, "<", (0.7, 0.7, 0.7, 1.0))
    _timeline_buttons["step_back"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing

    # Play/Pause
    is_playing = bpy.context.screen.is_animation_playing if hasattr(bpy.context.screen, 'is_animation_playing') else False
    play_icon = "||" if is_playing else ">"
    play_color = (0.2, 0.55, 0.35, 1.0) if is_playing else (0.7, 0.7, 0.7, 1.0)
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, play_icon, play_color)
    _timeline_buttons["play_pause"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing

    # Step forward >
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, ">", (0.7, 0.7, 0.7, 1.0))
    _timeline_buttons["step_forward"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing

    # Go to end >|
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, ">|", (0.7, 0.7, 0.7, 1.0))
    _timeline_buttons["goto_end"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing + 10

    # Set In point [
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, "[", (0.2, 0.55, 0.35, 1.0))
    _timeline_buttons["set_in"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing

    # Set Out point ]
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, "]", (0.9, 0.5, 0.2, 1.0))
    _timeline_buttons["set_out"] = (btn_x, btn_row_y, btn_size, btn_size)
    btn_x += btn_size + btn_spacing + 10

    # Loop toggle
    loop_color = (0.2, 0.55, 0.35, 1.0) if use_preview else (0.5, 0.5, 0.5, 1.0)
    _draw_timeline_button(shader, btn_x, btn_row_y, btn_size, btn_size, "L", loop_color)
    _timeline_buttons["loop"] = (btn_x, btn_row_y, btn_size, btn_size)

    # Cache memory display (center area, between buttons and frame counter)
    try:
        from ..nodes.viewer.viewer import get_cache_memory_info
        cache_info = get_cache_memory_info()
        blf.size(0, 11)
        # Color based on cache usage - bright green when has cache, dim gray when empty
        if cache_info['frame_count'] > 0:
            blf.color(0, 0.2, 0.55, 0.35, 1.0)  # OpenComp accent
        else:
            blf.color(0, 0.4, 0.4, 0.4, 1.0)  # Gray when empty
        cache_text = f"Cache: {cache_info['used_gb']:.1f}/{cache_info['limit_gb']:.0f}GB ({cache_info['frame_count']}f)"
        # Position in center of timeline
        cache_x = region_width // 2 - 60
        blf.position(0, cache_x, btn_row_y + 5, 0)
        blf.draw(0, cache_text)
    except Exception as e:
        print(f"[OpenComp] Cache memory display error: {e}")

    # Frame counter (right side)
    blf.size(0, 14)
    blf.color(0, 0.9, 0.9, 0.9, 1.0)
    frame_text = f"{frame_current}"
    blf.position(0, region_width - 60, btn_row_y + 5, 0)
    blf.draw(0, frame_text)

    # Range display
    blf.size(0, 10)
    blf.color(0, 0.5, 0.5, 0.5, 1.0)
    range_text = f"/ {frame_end}"
    blf.position(0, region_width - 35, btn_row_y + 5, 0)
    blf.draw(0, range_text)


def handle_timeline_click(x, y, region_height):
    """Handle mouse click on timeline. Returns True if handled."""
    global _timeline_buttons

    # y is from bottom of region, timeline is at bottom
    if y > TIMELINE_HEIGHT:
        return False

    scene = bpy.context.scene
    frame_start = scene.frame_start
    frame_end = scene.frame_end

    # Check each button
    for btn_name, (bx, by, bw, bh) in _timeline_buttons.items():
        if bx <= x <= bx + bw and by <= y <= by + bh:
            if btn_name == "goto_start":
                scene.frame_set(scene.frame_preview_start if scene.use_preview_range else frame_start)
                return True
            elif btn_name == "goto_end":
                scene.frame_set(scene.frame_preview_end if scene.use_preview_range else frame_end)
                return True
            elif btn_name == "step_back":
                scene.frame_set(max(frame_start, scene.frame_current - 1))
                return True
            elif btn_name == "step_forward":
                scene.frame_set(min(frame_end, scene.frame_current + 1))
                return True
            elif btn_name == "play_pause":
                bpy.ops.screen.animation_play()
                return True
            elif btn_name == "loop":
                scene.use_preview_range = not scene.use_preview_range
                return True
            elif btn_name == "set_in":
                # "[" button - set in point to current frame
                scene.use_preview_range = True
                scene.frame_preview_start = scene.frame_current
                return True
            elif btn_name == "set_out":
                # "]" button - set out point to current frame
                scene.use_preview_range = True
                scene.frame_preview_end = scene.frame_current
                return True
            elif btn_name == "in_point":
                # Clicking on the in-point marker - go to in point
                scene.frame_set(scene.frame_preview_start if scene.use_preview_range else frame_start)
                return True
            elif btn_name == "out_point":
                # Clicking on the out-point marker - go to out point
                scene.frame_set(scene.frame_preview_end if scene.use_preview_range else frame_end)
                return True
            elif btn_name == "scrub_area":
                # Scrub to frame
                scrub_x, scrub_y, scrub_w, scrub_h = _timeline_buttons["scrub_area"]
                rel_x = (x - scrub_x) / scrub_w
                new_frame = int(frame_start + rel_x * (frame_end - frame_start))
                scene.frame_set(max(frame_start, min(frame_end, new_frame)))
                return True

    return False


def get_timeline_scrub_frame(x, y, region_width, check_y=True):
    """Convert x,y position to frame number for scrubbing. 
    
    Args:
        x, y: Mouse position
        region_width: Width of the region
        check_y: If True, requires y to be within scrub bar. Set False during drag.
    
    Returns None if not in scrub area (when check_y=True) or if x is outside.
    """
    scene = bpy.context.scene
    frame_start = scene.frame_start
    frame_end = scene.frame_end

    if "scrub_area" not in _timeline_buttons:
        return None

    scrub_x, scrub_y, scrub_w, scrub_h = _timeline_buttons["scrub_area"]
    
    # Check x bounds (always required)
    if x < scrub_x or x > scrub_x + scrub_w:
        return None
    
    # Check y bounds only if requested (not during drag)
    if check_y and (y < scrub_y or y > scrub_y + scrub_h):
        return None

    rel_x = (x - scrub_x) / scrub_w
    new_frame = int(frame_start + rel_x * (frame_end - frame_start))
    return max(frame_start, min(frame_end, new_frame))


def _draw_viewer_overlay():
    """Draw Nuke-style viewer overlay with integrated timeline."""
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    region = context.region
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')

    # Calculate viewer area (above timeline)
    viewer_height = region.height - TIMELINE_HEIGHT
    viewer_bottom = TIMELINE_HEIGHT

    # Check if viewer node has a texture to display
    # If so, the viewer node's draw handler will render it - we just draw the frame
    has_texture = False
    try:
        from ..nodes.viewer.viewer import _viewer_state
        has_texture = _viewer_state.get("texture") is not None
    except Exception:
        pass

    # Draw background for viewer area based on mode (only if no texture)
    global _viewer_bg_mode
    if not has_texture:
        if _viewer_bg_mode == 'Checker':
            _draw_checker_background(0, viewer_bottom, region.width, viewer_height)
        else:
            bg_color = get_viewer_bg_color()
            verts = [
                (0, viewer_bottom), (region.width, viewer_bottom),
                (region.width, region.height), (0, region.height)
            ]
            indices = [(0, 1, 2), (0, 2, 3)]
            batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
            shader.bind()
            shader.uniform_float("color", bg_color)
            batch.draw(shader)

    # Disable scissor test to draw OUTSIDE region bounds and cover the chevrons
    gpu.state.scissor_test_set(False)

    # Edge color matches background
    if _viewer_bg_mode == 'Checker':
        edge_color = (0.2, 0.2, 0.2, 1.0)  # Use darker checker color
    else:
        edge_color = get_viewer_bg_color()
    # Cover the right edge chevron (extends beyond region width)
    chevron_cover = [
        (region.width, 0), (region.width + 30, 0),
        (region.width + 30, region.height), (region.width, region.height)
    ]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": chevron_cover}, indices=indices)
    shader.bind()
    shader.uniform_float("color", edge_color)
    batch.draw(shader)

    # Re-enable scissor test
    gpu.state.scissor_test_set(True)

    cx = region.width / 2
    cy = viewer_bottom + viewer_height / 2

    # Only draw placeholder UI when no texture is connected
    if not has_texture:
        # Draw center crosshair (in viewer area)
        cross_size = 20
        cross_vertices = [
            (cx - cross_size, cy), (cx + cross_size, cy),
            (cx, cy - cross_size), (cx, cy + cross_size),
        ]
        batch = batch_for_shader(shader, 'LINES', {"pos": cross_vertices})
        shader.bind()
        shader.uniform_float("color", (0.3, 0.3, 0.3, 1.0))
        batch.draw(shader)

        # Draw frame border indicator (in viewer area)
        border_color = (0.2, 0.5, 0.3, 1.0)  # Green tint
        margin = 50
        border_verts = [
            (margin, viewer_bottom + margin),
            (region.width - margin, viewer_bottom + margin),
            (region.width - margin, region.height - margin),
            (margin, region.height - margin),
            (margin, viewer_bottom + margin)
        ]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": border_verts})
        shader.bind()
        shader.uniform_float("color", border_color)
        batch.draw(shader)

        # Draw "No Image" text (centered in viewer area)
        blf.size(0, 24)
        blf.color(0, 0.4, 0.4, 0.4, 1.0)
        text = "Connect Viewer Node"
        text_width, text_height = blf.dimensions(0, text)
        blf.position(0, cx - text_width / 2, cy - text_height / 2, 0)
        blf.draw(0, text)

    # Draw the timeline strip at the bottom
    _draw_timeline_strip(region.width, TIMELINE_HEIGHT)

    gpu.state.blend_set('NONE')


def _hide_default_view3d_ui():
    """Hide default Blender 3D View overlays and gizmos."""
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            # Hide overlays
            space.overlay.show_overlays = False
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_axis_z = False
            space.overlay.show_cursor = False
            space.overlay.show_object_origins = False
            # Hide gizmos
            space.show_gizmo = False
            # Set shading
            space.shading.type = 'SOLID'
            space.shading.background_type = 'VIEWPORT'
            space.shading.background_color = (0.0, 0.0, 0.0)
    return None  # Don't repeat timer


class OC_MT_viewer_bg(bpy.types.Menu):
    """Background mode dropdown menu."""
    bl_idname = "OC_MT_viewer_bg"
    bl_label = "Background"

    def draw(self, context):
        layout = self.layout
        for mode in VIEWER_BG_MODES:
            op = layout.operator("oc.viewer_bg", text=mode, icon='RADIOBUT_ON' if mode == _viewer_bg_mode else 'RADIOBUT_OFF')
            op.mode = mode


class OC_HT_viewer_header(Header):
    """Viewer header with all controls."""
    bl_space_type = 'VIEW_3D'

    def draw(self, context):
        layout = self.layout

        # Get current channel mode
        try:
            settings = context.scene.oc_viewer
            current_channel = settings.channel_mode
        except AttributeError:
            current_channel = 'ALL'

        # Viewer label
        row = layout.row()
        row.label(text="Viewer")

        layout.separator_spacer()

        # Channel buttons - use correct operator from nodes/viewer/operators.py
        row = layout.row(align=True)
        row.operator("oc.viewer_set_channel", text="RGB", depress=(current_channel == 'ALL')).channel = "ALL"
        row.operator("oc.viewer_set_channel", text="R", depress=(current_channel == 'R')).channel = "R"
        row.operator("oc.viewer_set_channel", text="G", depress=(current_channel == 'G')).channel = "G"
        row.operator("oc.viewer_set_channel", text="B", depress=(current_channel == 'B')).channel = "B"
        row.operator("oc.viewer_set_channel", text="A", depress=(current_channel == 'A')).channel = "A"

        layout.separator()

        # Zoom
        layout.label(text="100%")

        layout.separator()

        # Background mode dropdown
        layout.menu("OC_MT_viewer_bg", text=f"BG: {_viewer_bg_mode}")

        layout.separator_spacer()

        # Clear Cache button (right side)
        layout.operator("oc.clear_cache", text="Clear Cache", icon='TRASH')

        layout.separator()

        # Frame info
        layout.label(text=f"Frame {context.scene.frame_current}")


class OC_OT_viewer_bg(Operator):
    """Set viewer background mode"""
    bl_idname = "oc.viewer_bg"
    bl_label = "Set Background"

    mode: bpy.props.StringProperty(default='Black')

    def execute(self, context):
        global _viewer_bg_mode
        if self.mode in VIEWER_BG_MODES:
            _viewer_bg_mode = self.mode
            # Update the 3D viewport background color
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    if _viewer_bg_mode != 'Checker':
                        color = get_viewer_bg_color()
                        space.shading.background_color = color[:3]
                    area.tag_redraw()
        return {'FINISHED'}


class OC_OT_clear_cache(Operator):
    """Clear all cached frames"""
    bl_idname = "oc.clear_cache"
    bl_label = "Clear Cache"
    bl_description = "Clear all cached frames from memory"

    def execute(self, context):
        from ..nodes.viewer.viewer import clear_frame_cache
        clear_frame_cache()
        # Redraw viewports
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        self.report({'INFO'}, "Cache cleared")
        return {'FINISHED'}


class OC_OT_timeline_interact(Operator):
    """Timeline interaction handler - scrubbing, buttons, in/out points"""
    bl_idname = "oc.timeline_interact"
    bl_label = "Timeline Interact"

    _is_scrubbing = False
    _is_running = False

    def modal(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}

        region = context.region
        mx = event.mouse_region_x
        my = event.mouse_region_y

        # Only handle events in the timeline area (bottom of viewer)
        if my > TIMELINE_HEIGHT and not OC_OT_timeline_interact._is_scrubbing:
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                # Check if clicking in scrub area
                new_frame = get_timeline_scrub_frame(mx, my, region.width, check_y=True)
                if new_frame is not None:
                    context.scene.frame_set(new_frame)
                    OC_OT_timeline_interact._is_scrubbing = True
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}
                # Handle button clicks
                if handle_timeline_click(mx, my, region.height):
                    context.area.tag_redraw()
                    return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                if OC_OT_timeline_interact._is_scrubbing:
                    OC_OT_timeline_interact._is_scrubbing = False
                    return {'RUNNING_MODAL'}

        elif event.type == 'MOUSEMOVE':
            if OC_OT_timeline_interact._is_scrubbing:
                # During drag, don't check y bounds - user can drag freely
                new_frame = get_timeline_scrub_frame(mx, my, region.width, check_y=False)
                if new_frame is not None:
                    context.scene.frame_set(new_frame)
                    context.area.tag_redraw()
                return {'RUNNING_MODAL'}

        elif event.type == 'ESC':
            OC_OT_timeline_interact._is_running = False
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if OC_OT_timeline_interact._is_running:
            return {'CANCELLED'}

        OC_OT_timeline_interact._is_running = True
        context.window_manager.modal_handler_add(self)
        print("[OpenComp] Timeline interaction modal started")
        return {'RUNNING_MODAL'}


classes = [
    OC_MT_viewer_bg,  # Menu must be registered before header that uses it
    OC_HT_viewer_header,
    OC_OT_viewer_bg,
    OC_OT_clear_cache,
    OC_OT_timeline_interact,
]


def register():
    global _viewer_draw_handler, _viewer_header_handler, _viewer_tool_header_handler

    for cls in classes:
        bpy.utils.register_class(cls)

    # Register draw handlers for all regions
    _viewer_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_overlay, (), 'WINDOW', 'POST_PIXEL'
    )

    _viewer_header_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_header, (), 'HEADER', 'POST_PIXEL'
    )

    _viewer_tool_header_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_tool_header, (), 'TOOL_HEADER', 'POST_PIXEL'
    )

    _viewer_sidebar_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_viewer_sidebar, (), 'UI', 'POST_PIXEL'
    )

    # Hide default UI after a delay
    bpy.app.timers.register(_hide_default_view3d_ui, first_interval=0.2)

    # Unregister default headers
    try:
        bpy.utils.unregister_class(bpy.types.VIEW3D_HT_header)
    except:
        pass
    try:
        bpy.utils.unregister_class(bpy.types.VIEW3D_HT_tool_header)
    except:
        pass

    # Auto-start timeline interaction modal
    def _start_timeline_interact():
        try:
            bpy.ops.oc.timeline_interact('INVOKE_DEFAULT')
        except Exception as e:
            print(f"[OpenComp] Timeline interact start failed: {e}")
        return None

    bpy.app.timers.register(_start_timeline_interact, first_interval=0.7)

    print("[OpenComp] Viewer draw handler registered")


def unregister():
    global _viewer_draw_handler, _viewer_header_handler, _viewer_tool_header_handler, _viewer_sidebar_handler

    if _viewer_draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_draw_handler, 'WINDOW')
        _viewer_draw_handler = None

    if _viewer_header_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_header_handler, 'HEADER')
        _viewer_header_handler = None

    if _viewer_tool_header_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_tool_header_handler, 'TOOL_HEADER')
        _viewer_tool_header_handler = None

    if _viewer_sidebar_handler:
        bpy.types.SpaceView3D.draw_handler_remove(_viewer_sidebar_handler, 'UI')
        _viewer_sidebar_handler = None

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass
