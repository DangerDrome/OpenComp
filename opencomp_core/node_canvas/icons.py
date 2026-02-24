"""OpenComp Node Canvas — Custom icon drawing.

Simple geometric icons drawn with GPU primitives.
"""

import gpu
from gpu_extras.batch import batch_for_shader
import math
from typing import Tuple


def _get_shader():
    """Get the uniform color shader."""
    return gpu.shader.from_builtin('UNIFORM_COLOR')


def draw_icon(icon_name: str, x: float, y: float, size: float, color: Tuple[float, float, float, float], line_width: float = 1.5):
    """Draw an icon at the given position.

    Args:
        icon_name: Name of the icon to draw
        x, y: Center position of the icon
        size: Size of the icon (width/height)
        color: RGBA color tuple
        line_width: Thickness of icon lines
    """
    shader = _get_shader()
    half = size / 2

    # Set line width for icon drawing
    gpu.state.line_width_set(line_width)

    icon_funcs = {
        'image': _draw_image_icon,
        'color': _draw_color_icon,
        'layers': _draw_layers_icon,
        'blur': _draw_blur_icon,
        'transform': _draw_transform_icon,
        'view': _draw_view_icon,
        'eye': _draw_view_icon,  # alias
        'export': _draw_export_icon,
        'constant': _draw_constant_icon,
        'shuffle': _draw_shuffle_icon,
        'crop': _draw_crop_icon,
        'sharpen': _draw_sharpen_icon,
        'reroute': _draw_reroute_icon,
        'cursor': _draw_cursor_icon,
        'folder': _draw_folder_icon,
    }

    func = icon_funcs.get(icon_name, _draw_default_icon)
    func(shader, x, y, half, color)

    # Reset line width
    gpu.state.line_width_set(1.0)


def _draw_image_icon(shader, x: float, y: float, half: float, color):
    """Image/photo icon - rectangle with mountain and sun."""
    gpu.state.blend_set('ALPHA')

    # Outer frame
    frame = [
        (x - half, y - half * 0.7),
        (x + half, y - half * 0.7),
        (x + half, y + half * 0.7),
        (x - half, y + half * 0.7),
        (x - half, y - half * 0.7),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": frame})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Mountain (triangle)
    mountain = [
        (x - half * 0.6, y - half * 0.4),
        (x, y + half * 0.2),
        (x + half * 0.6, y - half * 0.4),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": mountain})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Sun (small circle)
    _draw_small_circle(shader, x + half * 0.4, y + half * 0.3, half * 0.2, color)

    gpu.state.blend_set('NONE')


def _draw_color_icon(shader, x: float, y: float, half: float, color):
    """Color/palette icon - three overlapping circles."""
    gpu.state.blend_set('ALPHA')

    r = half * 0.4
    offset = half * 0.3

    # Three overlapping circles
    _draw_small_circle(shader, x - offset, y + offset * 0.5, r, color)
    _draw_small_circle(shader, x + offset, y + offset * 0.5, r, color)
    _draw_small_circle(shader, x, y - offset * 0.5, r, color)

    gpu.state.blend_set('NONE')


def _draw_layers_icon(shader, x: float, y: float, half: float, color):
    """Layers/merge icon - stacked rectangles."""
    gpu.state.blend_set('ALPHA')

    # Three stacked layers
    for i, offset in enumerate([-half * 0.4, 0, half * 0.4]):
        w = half * (0.9 - i * 0.15)
        layer = [
            (x - w, y + offset - half * 0.15),
            (x + w, y + offset - half * 0.15),
            (x + w, y + offset + half * 0.15),
            (x - w, y + offset + half * 0.15),
            (x - w, y + offset - half * 0.15),
        ]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": layer})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_blur_icon(shader, x: float, y: float, half: float, color):
    """Blur icon - concentric circles with fade."""
    gpu.state.blend_set('ALPHA')

    # Multiple circles suggesting blur/softness
    for i, r in enumerate([half * 0.3, half * 0.6, half * 0.9]):
        alpha = 1.0 - i * 0.3
        c = (color[0], color[1], color[2], color[3] * alpha)
        _draw_small_circle(shader, x, y, r, c)

    gpu.state.blend_set('NONE')


def _draw_transform_icon(shader, x: float, y: float, half: float, color):
    """Transform icon - arrows pointing outward."""
    gpu.state.blend_set('ALPHA')

    # Four arrows pointing out from center
    arrow_len = half * 0.7
    arrow_head = half * 0.25

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    for dx, dy in directions:
        # Arrow line
        line = [
            (x, y),
            (x + dx * arrow_len, y + dy * arrow_len),
        ]
        batch = batch_for_shader(shader, 'LINES', {"pos": line})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Arrow head
        end_x, end_y = x + dx * arrow_len, y + dy * arrow_len
        if dx != 0:
            head = [
                (end_x - dx * arrow_head, end_y - arrow_head * 0.5),
                (end_x, end_y),
                (end_x - dx * arrow_head, end_y + arrow_head * 0.5),
            ]
        else:
            head = [
                (end_x - arrow_head * 0.5, end_y - dy * arrow_head),
                (end_x, end_y),
                (end_x + arrow_head * 0.5, end_y - dy * arrow_head),
            ]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": head})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_view_icon(shader, x: float, y: float, half: float, color):
    """View/eye icon."""
    gpu.state.blend_set('ALPHA')

    # Eye outline (two arcs)
    points_top = []
    points_bottom = []
    segments = 12
    for i in range(segments + 1):
        t = i / segments
        px = x - half + t * half * 2
        py_top = y + half * 0.4 * math.sin(t * math.pi)
        py_bottom = y - half * 0.4 * math.sin(t * math.pi)
        points_top.append((px, py_top))
        points_bottom.append((px, py_bottom))

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points_top})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points_bottom})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Pupil
    _draw_small_circle(shader, x, y, half * 0.25, color)

    gpu.state.blend_set('NONE')


def _draw_export_icon(shader, x: float, y: float, half: float, color):
    """Export/write icon - arrow pointing into box."""
    gpu.state.blend_set('ALPHA')

    # Box (open top)
    box = [
        (x - half * 0.7, y + half * 0.2),
        (x - half * 0.7, y - half * 0.7),
        (x + half * 0.7, y - half * 0.7),
        (x + half * 0.7, y + half * 0.2),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": box})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Arrow pointing down into box
    arrow = [
        (x, y + half * 0.8),
        (x, y - half * 0.3),
    ]
    batch = batch_for_shader(shader, 'LINES', {"pos": arrow})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Arrow head
    head = [
        (x - half * 0.25, y - half * 0.05),
        (x, y - half * 0.3),
        (x + half * 0.25, y - half * 0.05),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": head})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_constant_icon(shader, x: float, y: float, half: float, color):
    """Constant icon - filled square."""
    gpu.state.blend_set('ALPHA')

    # Filled square
    verts = [
        (x - half * 0.6, y - half * 0.6),
        (x + half * 0.6, y - half * 0.6),
        (x + half * 0.6, y + half * 0.6),
        (x - half * 0.6, y + half * 0.6),
    ]
    indices = [(0, 1, 2), (0, 2, 3)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_shuffle_icon(shader, x: float, y: float, half: float, color):
    """Shuffle icon - crossing arrows."""
    gpu.state.blend_set('ALPHA')

    # Two crossing lines
    line1 = [
        (x - half * 0.7, y - half * 0.5),
        (x + half * 0.7, y + half * 0.5),
    ]
    line2 = [
        (x - half * 0.7, y + half * 0.5),
        (x + half * 0.7, y - half * 0.5),
    ]

    for line in [line1, line2]:
        batch = batch_for_shader(shader, 'LINES', {"pos": line})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_crop_icon(shader, x: float, y: float, half: float, color):
    """Crop icon - L-shaped corners."""
    gpu.state.blend_set('ALPHA')

    corner_len = half * 0.4

    # Top-left corner
    tl = [
        (x - half * 0.7, y + half * 0.3),
        (x - half * 0.7, y + half * 0.7),
        (x - half * 0.3, y + half * 0.7),
    ]
    # Top-right corner
    tr = [
        (x + half * 0.3, y + half * 0.7),
        (x + half * 0.7, y + half * 0.7),
        (x + half * 0.7, y + half * 0.3),
    ]
    # Bottom-left corner
    bl = [
        (x - half * 0.7, y - half * 0.3),
        (x - half * 0.7, y - half * 0.7),
        (x - half * 0.3, y - half * 0.7),
    ]
    # Bottom-right corner
    br = [
        (x + half * 0.3, y - half * 0.7),
        (x + half * 0.7, y - half * 0.7),
        (x + half * 0.7, y - half * 0.3),
    ]

    for corner in [tl, tr, bl, br]:
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": corner})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_sharpen_icon(shader, x: float, y: float, half: float, color):
    """Sharpen icon - starburst/pointed shape."""
    gpu.state.blend_set('ALPHA')

    # Diamond/star shape
    points = [
        (x, y + half * 0.8),
        (x + half * 0.3, y),
        (x + half * 0.8, y),
        (x + half * 0.3, y),
        (x, y - half * 0.8),
        (x - half * 0.3, y),
        (x - half * 0.8, y),
        (x - half * 0.3, y),
        (x, y + half * 0.8),
    ]

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_reroute_icon(shader, x: float, y: float, half: float, color):
    """Reroute icon - filled dot with connecting lines."""
    gpu.state.blend_set('ALPHA')

    # Center dot (filled)
    r = half * 0.35
    segments = 12
    verts = [(x, y)]  # Center point
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        verts.append((x + r * math.cos(angle), y + r * math.sin(angle)))

    indices = [(0, i, i + 1) for i in range(1, segments + 1)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Lines going in and out (showing flow)
    line_in = [(x - half * 0.8, y), (x - half * 0.4, y)]
    line_out = [(x + half * 0.4, y), (x + half * 0.8, y)]

    for line in [line_in, line_out]:
        batch = batch_for_shader(shader, 'LINES', {"pos": line})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_cursor_icon(shader, x: float, y: float, half: float, color):
    """Cursor/select icon - arrow pointer."""
    gpu.state.blend_set('ALPHA')

    # Arrow pointer shape
    points = [
        (x - half * 0.3, y + half * 0.8),   # Top
        (x - half * 0.3, y - half * 0.4),   # Bottom of main line
        (x - half * 0.6, y - half * 0.1),   # Left branch
        (x - half * 0.3, y - half * 0.4),   # Back to center
        (x + half * 0.1, y - half * 0.8),   # Right branch (arrow tail)
        (x + half * 0.3, y - half * 0.5),   # Back
        (x + half * 0.5, y - half * 0.3),   # Right point
    ]

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_folder_icon(shader, x: float, y: float, half: float, color):
    """Folder icon."""
    gpu.state.blend_set('ALPHA')

    # Folder body
    body = [
        (x - half * 0.8, y - half * 0.5),
        (x + half * 0.8, y - half * 0.5),
        (x + half * 0.8, y + half * 0.3),
        (x - half * 0.8, y + half * 0.3),
        (x - half * 0.8, y - half * 0.5),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": body})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    # Folder tab
    tab = [
        (x - half * 0.8, y + half * 0.3),
        (x - half * 0.8, y + half * 0.5),
        (x - half * 0.2, y + half * 0.5),
        (x, y + half * 0.3),
    ]
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": tab})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def _draw_default_icon(shader, x: float, y: float, half: float, color):
    """Default icon - simple circle."""
    gpu.state.blend_set('ALPHA')
    _draw_small_circle(shader, x, y, half * 0.6, color)
    gpu.state.blend_set('NONE')


def _draw_small_circle(shader, cx: float, cy: float, radius: float, color, segments: int = 16):
    """Draw a circle outline."""
    points = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


# Map node types to icon names
NODE_TYPE_ICONS = {
    'OC_N_read': 'image',
    'OC_N_constant': 'constant',
    'OC_N_grade': 'color',
    'OC_N_cdl': 'color',
    'OC_N_over': 'layers',
    'OC_N_shuffle': 'shuffle',
    'OC_N_blur': 'blur',
    'OC_N_sharpen': 'sharpen',
    'OC_N_transform': 'transform',
    'OC_N_crop': 'crop',
    'OC_N_write': 'export',
    'OC_N_viewer': 'view',
    'OC_N_reroute': 'reroute',
}


def get_icon_for_node_type(bl_idname: str) -> str:
    """Get the icon name for a node type."""
    return NODE_TYPE_ICONS.get(bl_idname, 'default')
