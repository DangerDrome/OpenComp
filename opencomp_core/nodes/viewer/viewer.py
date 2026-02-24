"""OpenComp Viewer node — displays GPUTexture in the 3D viewport.

Inputs:  Image (RGBA32F)
Outputs: (none — display node)
Shader:  shaders/viewer_display.frag (gain, gamma, channel, false colour,
         clipping, zoom, pan, ROI)

The draw handler is registered once at addon startup. The ViewerNode
stores the current input texture in module-level state and the handler
picks it up every frame.

Display controls (gain, gamma, channel isolation, etc.) feed into the
display shader as uniforms — they do NOT re-evaluate the node graph.
"""

import bpy
from ..base import OpenCompNode

# ── Module-level viewer state ───────────────────────────────────────────

_viewer_state = {
    "texture": None,
    "shader": None,
    "batch": None,
    "handler": None,
    "zoom": 1.0,
    "pan": [0.0, 0.0],
    "roi_enabled": False,
    "roi": [0.25, 0.25, 0.75, 0.75],
    # Metadata for HUD display (Nuke-style)
    "source_file": None,       # Source filename from Read node
    "source_node": None,       # Name of the source node
    "colorspace": None,        # File's embedded color space
    "view_transform": None,    # Current OCIO view transform
    "bit_depth": "32-bit float",
    "format": None,            # File format (EXR, PNG, etc.)
    "compression": None,       # Compression type (zip, piz, etc.)
    "channels": None,          # Channel count
    "channel_names": None,     # Channel names (R, G, B, A, etc.)
    "software": None,          # Software that created the file
    "pixel_aspect": 1.0,       # Pixel aspect ratio
    "timecode": None,          # Timecode if available
    "image_type": None,        # scanlineimage, tiledimage, etc.
    "nuke_version": None,      # Nuke version if created by Nuke
    "original_width": None,    # Original resolution (before proxy)
    "original_height": None,
    "proxy_factor": 1,         # Current proxy factor
    # Frame cache
    "current_frame": None,     # Frame number of current texture
}

# ── Frame cache system (Nuke-style) ──────────────────────────────────────
# Stores GPU textures directly for real-time playback
# Falls back to pixel data if GPU texture becomes invalid

_frame_cache = {}          # {frame_number: {'texture': GPUTexture, 'pixels': numpy_array, 'width': int, 'height': int}}
_cached_frames = set()     # Set of cached frame numbers for quick lookup
_cache_memory_limit_gb = 8.0  # Max RAM to use for cache (in GB)
_cache_memory_used = 0     # Current RAM usage in bytes
_cache_enabled = True      # Whether caching is enabled


def get_cache_memory_info():
    """Get cache memory stats for display."""
    return {
        'used_gb': _cache_memory_used / (1024**3),
        'limit_gb': _cache_memory_limit_gb,
        'frame_count': len(_cached_frames),
    }


def get_cached_frames():
    """Get the set of cached frame numbers for cache bar display."""
    return _cached_frames.copy()


def clear_frame_cache():
    """Clear all cached frames."""
    global _frame_cache, _cached_frames, _cache_memory_used
    _frame_cache.clear()
    _cached_frames.clear()
    _cache_memory_used = 0


def set_cache_enabled(enabled):
    """Enable or disable frame caching."""
    global _cache_enabled
    _cache_enabled = enabled
    if not enabled:
        clear_frame_cache()


def set_cache_limit_gb(limit_gb):
    """Set the cache memory limit in GB."""
    global _cache_memory_limit_gb
    _cache_memory_limit_gb = max(0.5, limit_gb)  # Minimum 0.5 GB
    # Evict if over new limit
    while _cache_memory_used > _cache_memory_limit_gb * (1024**3) and _frame_cache:
        _evict_oldest_frame()


def _evict_oldest_frame():
    """Evict the oldest cached frame when cache is full."""
    global _cache_memory_used
    if _frame_cache:
        # Simple FIFO eviction - remove the smallest frame number
        oldest = min(_frame_cache.keys())
        entry = _frame_cache[oldest]
        if 'pixels' in entry and entry['pixels'] is not None:
            _cache_memory_used -= entry['pixels'].nbytes
        del _frame_cache[oldest]
        _cached_frames.discard(oldest)


def cache_frame_with_texture(frame, texture, pixels, width, height):
    """Cache a frame's GPU texture and pixel data. Called from Read node after upload."""
    global _frame_cache, _cached_frames, _cache_memory_used
    if not _cache_enabled or texture is None:
        return

    # Don't re-cache if already cached
    if frame in _cached_frames:
        return

    # Calculate memory for this frame
    frame_bytes = pixels.nbytes if pixels is not None else width * height * 4 * 4

    # Evict frames if we'd exceed memory limit
    while (_cache_memory_used + frame_bytes) > _cache_memory_limit_gb * (1024**3) and _frame_cache:
        _evict_oldest_frame()

    # Store both GPU texture and pixel data (for fallback if texture becomes invalid)
    _frame_cache[frame] = {
        'texture': texture,
        'pixels': pixels.copy() if pixels is not None else None,
        'width': width,
        'height': height,
    }
    _cached_frames.add(frame)
    _cache_memory_used += frame_bytes


# Keep old function name for compatibility
def cache_frame_pixels(frame, pixels, width, height):
    """Legacy function - caches pixels only. Use cache_frame_with_texture for GPU caching."""
    pass  # No-op, we'll cache with texture in ReadNode


def get_cached_frame_pixels(frame):
    """Get cached pixel data for a frame, returns (pixels, width, height) or None."""
    if frame in _frame_cache:
        entry = _frame_cache[frame]
        return entry['pixels'], entry['width'], entry['height']
    return None


def _fast_numpy_to_gpu_buffer(pixels):
    """Convert numpy array to GPU buffer efficiently.

    Tries memoryview first (zero-copy), falls back to array.array.
    """
    import numpy as np
    import gpu

    # Ensure contiguous C-order float32 array
    pixels = np.ascontiguousarray(pixels, dtype=np.float32)
    flat = pixels.ravel()

    try:
        # Attempt 1: Direct memoryview (zero-copy if supported)
        return gpu.types.Buffer('FLOAT', flat.size, memoryview(flat))
    except (TypeError, ValueError):
        # Attempt 2: array.array (still ~50x faster than tolist())
        import array
        arr = array.array('f')
        arr.frombytes(flat.tobytes())
        return gpu.types.Buffer('FLOAT', len(arr), arr)


def get_cached_texture(frame):
    """Get cached GPU texture for a frame. Returns GPUTexture or None.

    This is the fast path - returns the cached texture directly without re-upload.
    """
    if frame not in _frame_cache:
        return None

    entry = _frame_cache[frame]
    texture = entry.get('texture')

    # Check if texture is still valid
    if texture is not None:
        try:
            # Try to access texture properties to verify it's valid
            _ = texture.width
            return texture
        except Exception:
            # Texture became invalid, need to re-upload
            pass

    # Texture invalid, try to re-upload from pixel data
    pixels = entry.get('pixels')
    if pixels is None:
        return None

    try:
        import gpu
        width, height = entry['width'], entry['height']
        buf = _fast_numpy_to_gpu_buffer(pixels)
        tex = gpu.types.GPUTexture((width, height), format='RGBA32F', data=buf)
        entry['texture'] = tex  # Update cache with new texture
        return tex
    except Exception as e:
        print(f"[OpenComp] Failed to re-upload cached frame {frame} to GPU: {e}")
        return None


# Keep old function name for compatibility
def upload_cached_frame_to_gpu(frame):
    """Legacy function - use get_cached_texture instead."""
    return get_cached_texture(frame)


# ── Viewer settings PropertyGroup ──────────────────────────────────────

_CHANNEL_ITEMS = [
    ('ALL',  "All",  "Show all channels",     0),
    ('R',    "R",    "Red channel only",       1),
    ('G',    "G",    "Green channel only",     2),
    ('B',    "B",    "Blue channel only",      3),
    ('A',    "A",    "Alpha channel only",     4),
    ('LUMA', "Luma", "Rec.709 luminance only", 5),
]

_CHANNEL_MAP = {item[0]: float(item[3]) for item in _CHANNEL_ITEMS}

_BG_MODE_ITEMS = [
    ('BLACK',   "Black",       "Solid black background",           0),
    ('GREY',    "Grey",        "18% grey background",              1),
    ('CHECKER', "Checker",     "Checkerboard pattern",             2),
    ('CUSTOM',  "Custom",      "User-defined background colour",   3),
]

_BG_MODE_MAP = {item[0]: float(item[3]) for item in _BG_MODE_ITEMS}

_PROXY_ITEMS = [
    ('1', "Full",  "Full resolution",       0),
    ('2', "1/2",   "Half resolution",        1),
    ('4', "1/4",   "Quarter resolution",     2),
    ('8', "1/8",   "Eighth resolution",      3),
]

# ── Colorspace system ──────────────────────────────────────────────────
# Dynamically gets all colorspaces from Blender's OCIO config

_colorspace_items_cache = None

def _get_colorspace_items(self, context):
    """Dynamically get all colorspaces from Blender's OCIO config."""
    global _colorspace_items_cache

    # Return cached items if available (for performance)
    if _colorspace_items_cache is not None:
        return _colorspace_items_cache

    items = []

    # Method 1: Get from PyOpenColorIO directly
    try:
        bpy.utils.expose_bundled_modules()
        import PyOpenColorIO as ocio
        config = ocio.GetCurrentConfig()
        if config:
            for i in range(config.getNumColorSpaces()):
                cs_name = config.getColorSpaceNameByIndex(i)
                items.append((cs_name, cs_name, f"OCIO colorspace: {cs_name}", i))
    except Exception:
        pass

    # Method 2: Fallback to Blender's color management
    if not items:
        try:
            for i, cs in enumerate(bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items):
                items.append((cs.identifier, cs.name, cs.description or cs.name, i))
        except Exception:
            pass

    # Method 3: Hardcoded fallback with common colorspaces
    if not items:
        fallback = [
            ('Linear Rec.709', "Linear Rec.709", "Linear with Rec.709 primaries"),
            ('sRGB', "sRGB", "Standard sRGB colorspace"),
            ('ACEScg', "ACEScg", "ACES CG working space"),
            ('ACES2065-1', "ACES2065-1", "ACES 2065-1 archival"),
            ('ACEScc', "ACEScc", "ACES CC log colorspace"),
            ('ACEScct', "ACEScct", "ACES CCT log colorspace"),
            ('AgX Base sRGB', "AgX Base sRGB", "AgX base colorspace"),
            ('Display P3', "Display P3", "Display P3 colorspace"),
            ('Filmic sRGB', "Filmic sRGB", "Filmic sRGB colorspace"),
            ('Linear CIE-XYZ D65', "Linear CIE-XYZ D65", "CIE XYZ D65"),
            ('Linear DCI-P3 D65', "Linear DCI-P3 D65", "Linear DCI-P3"),
            ('Linear Rec.2020', "Linear Rec.2020", "Linear Rec.2020"),
            ('Non-Color', "Non-Color", "Non-color data (masks, normals)"),
            ('Rec.1886', "Rec.1886", "Rec.1886 gamma"),
            ('Rec.2020', "Rec.2020", "Rec.2020 colorspace"),
            ('Rec.2100-HLG', "Rec.2100-HLG", "HDR HLG"),
            ('Rec.2100-PQ', "Rec.2100-PQ", "HDR PQ (ST.2084)"),
        ]
        items = [(cs[0], cs[1], cs[2], i) for i, cs in enumerate(fallback)]

    _colorspace_items_cache = items
    return items


# Auto-detection: maps common file colorspace strings to Blender colorspace names
_COLORSPACE_ALIASES = {
    # OIIO/EXR colorspace strings
    'linear': 'Linear Rec.709',
    'scene_linear': 'Linear Rec.709',
    'scene-linear': 'Linear Rec.709',
    'lin_rec709': 'Linear Rec.709',
    'linear rec.709': 'Linear Rec.709',
    'acescg': 'ACEScg',
    'aces cg': 'ACEScg',
    'aces - acescg': 'ACEScg',
    'aces2065-1': 'ACES2065-1',
    'aces 2065-1': 'ACES2065-1',
    'srgb': 'sRGB',
    'srgb - texture': 'sRGB',
    'rec709': 'Rec.1886',
    'rec.709': 'Rec.1886',
    'rec2020': 'Rec.2020',
    'rec.2020': 'Rec.2020',
    'display p3': 'Display P3',
    'p3-d65': 'Display P3',
    'raw': 'Non-Color',
    'non-color': 'Non-Color',
    'data': 'Non-Color',
    'utility - raw': 'Non-Color',
}


def _detect_colorspace(metadata_colorspace):
    """Auto-detect Blender colorspace from file metadata."""
    if not metadata_colorspace:
        return None

    cs_lower = metadata_colorspace.lower().strip()

    # Direct match
    if cs_lower in _COLORSPACE_ALIASES:
        return _COLORSPACE_ALIASES[cs_lower]

    # Partial match
    for alias, blender_cs in _COLORSPACE_ALIASES.items():
        if alias in cs_lower or cs_lower in alias:
            return blender_cs

    # Return original if no match (might be valid Blender colorspace name)
    return metadata_colorspace


def _on_colorspace_update(self, context):
    """Apply selected colorspace. Updates are handled per-image in the pipeline."""
    # Clear caches to force re-evaluation with new colorspace
    from ..io.read import _read_cache
    _read_cache.clear()
    from ...node_graph.tree import request_evaluate
    request_evaluate()

    # Tag viewport for redraw to update HUD immediately
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _on_proxy_update(self, context):
    """Invalidate Read node caches and trigger re-evaluation when proxy changes."""
    from ..io.read import _read_cache
    _read_cache.clear()
    from ...node_graph.tree import request_evaluate
    request_evaluate()


class OpenCompViewerSettings(bpy.types.PropertyGroup):
    """Viewer display controls — stored on Scene, read by draw handler."""

    colorspace: bpy.props.EnumProperty(
        name="Colorspace",
        items=_get_colorspace_items,
        description="Input colorspace for the viewer",
        update=_on_colorspace_update,
    )

    # Store auto-detected colorspace from file metadata
    detected_colorspace: bpy.props.StringProperty(
        name="Detected",
        default="",
        description="Auto-detected colorspace from file metadata",
    )

    proxy: bpy.props.EnumProperty(
        name="Proxy", items=_PROXY_ITEMS, default='1',
        description="Pipeline resolution multiplier (lower = faster interaction)",
        update=_on_proxy_update,
    )

    gain: bpy.props.FloatProperty(
        name="Gain", default=1.0, min=0.01, max=64.0,
        description="Exposure gain multiplier (1.0 = no change)",
    )
    gamma: bpy.props.FloatProperty(
        name="Gamma", default=1.0, min=0.1, max=4.0,
        description="Display gamma (1.0 = linear)",
    )
    channel_mode: bpy.props.EnumProperty(
        name="Channel", items=_CHANNEL_ITEMS, default='ALL',
        description="Channel isolation mode",
    )
    false_color: bpy.props.BoolProperty(
        name="False Color", default=False,
        description="Show exposure zones as false colour overlay",
    )
    clipping: bpy.props.BoolProperty(
        name="Clipping", default=False,
        description="Highlight over-white (red) and under-black (blue) pixels",
    )
    bg_mode: bpy.props.EnumProperty(
        name="Background", items=_BG_MODE_ITEMS, default='BLACK',
        description="Viewer background for out-of-bounds pixels",
    )
    bg_custom_color: bpy.props.FloatVectorProperty(
        name="BG Color", default=(0.18, 0.18, 0.18), size=3,
        subtype='COLOR', min=0.0, max=1.0,
        description="Custom background colour (used when mode is Custom)",
    )


# ── Display shader compilation ─────────────────────────────────────────

def _strip_declarations(source):
    """Strip in/out/uniform declarations from GLSL — handled by GPUShaderCreateInfo."""
    lines = []
    for line in source.split('\n'):
        stripped = line.strip()
        if stripped.startswith(('in ', 'in\t', 'out ', 'out\t', 'uniform ')):
            continue
        lines.append(line)
    return '\n'.join(lines)


def _compile_viewer_shader():
    """Compile the viewer display shader via gpu.shader.create_from_info().

    Blender 5.0 removed direct GPUShader() instantiation.
    Falls back to the built-in IMAGE shader if compilation fails.
    """
    import gpu
    from gpu_extras.batch import batch_for_shader
    from pathlib import Path

    shader_dir = Path(__file__).resolve().parent.parent.parent / "shaders"

    # Try custom shader via create_from_info
    try:
        vert_src = (shader_dir / "fullscreen_quad.vert").read_text()
        frag_src = (shader_dir / "viewer_display.frag").read_text()
        vert_body = _strip_declarations(vert_src)
        frag_body = _strip_declarations(frag_src)

        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, 'VEC2', "position")

        iface = gpu.types.GPUStageInterfaceInfo("viewer_iface")
        iface.smooth('VEC2', "v_uv")
        info.vertex_out(iface)

        info.fragment_out(0, 'VEC4', "out_color")

        info.sampler(0, 'FLOAT_2D', "u_image")
        info.push_constant('FLOAT', "u_gain")
        info.push_constant('FLOAT', "u_gamma")
        info.push_constant('FLOAT', "u_channel")
        info.push_constant('FLOAT', "u_false_color")
        info.push_constant('FLOAT', "u_clipping")
        info.push_constant('FLOAT', "u_zoom")
        info.push_constant('VEC2', "u_pan")
        info.push_constant('FLOAT', "u_roi_enabled")
        info.push_constant('VEC4', "u_roi")
        info.push_constant('VEC2', "u_resolution")
        info.push_constant('VEC2', "u_image_resolution")
        info.push_constant('FLOAT', "u_bg_mode")
        info.push_constant('VEC3', "u_bg_color")
        info.push_constant('FLOAT', "u_lut_mode")

        info.vertex_source(vert_body)
        info.fragment_source(frag_body)

        shader = gpu.shader.create_from_info(info)
        batch = batch_for_shader(
            shader, 'TRIS',
            {"position": [(-1, -1), (1, -1), (1, 1), (-1, 1)]},
            indices=[(0, 1, 2), (0, 2, 3)],
        )
        _viewer_state["shader"] = shader
        _viewer_state["batch"] = batch
        _viewer_state["builtin"] = False
        print("[OpenComp] Viewer display shader compiled")
        return
    except Exception as e:
        print(f"[OpenComp] Custom shader failed ({type(e).__name__}: {e}), trying built-in")

    # Fallback: built-in IMAGE shader
    shader = gpu.shader.from_builtin('IMAGE')
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {
            "pos": [(-1, -1), (1, -1), (1, 1), (-1, 1)],
            "texCoord": [(0, 0), (1, 0), (1, 1), (0, 1)],
        },
    )
    _viewer_state["shader"] = shader
    _viewer_state["batch"] = batch
    _viewer_state["builtin"] = True
    print("[OpenComp] Viewer using built-in IMAGE shader (no display controls)")


def _draw_viewer_callback():
    """Draw handler — renders viewer texture with display controls + HUD."""
    # Only draw in VIEW_3D areas
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Check if evaluation is needed and perform it now (we have GPU context)
    try:
        from ...node_graph import tree as tree_module
        if getattr(tree_module, '_eval_needed', False):
            tree_module._eval_needed = False
            from ...node_graph.tree import _evaluate_tree
            for node_tree in bpy.data.node_groups:
                if node_tree.bl_idname == "OC_NT_compositor":
                    _evaluate_tree(node_tree)
    except Exception as e:
        # Only print once to avoid spam
        pass

    tex = _viewer_state.get("texture")
    if tex is None:
        return

    shader = _viewer_state.get("shader")
    batch = _viewer_state.get("batch")

    # Lazy compile on first draw
    if shader is None:
        try:
            _compile_viewer_shader()
            shader = _viewer_state["shader"]
            batch = _viewer_state["batch"]
        except Exception as e:
            print(f"[OpenComp] Viewer shader compile failed: {e}")
            return

    import gpu
    gpu.state.blend_set('ALPHA')

    shader.bind()

    if _viewer_state.get("builtin"):
        # Built-in IMAGE shader — just bind the texture
        shader.uniform_sampler("image", tex)
    else:
        # Custom shader — full display controls
        shader.uniform_sampler("u_image", tex)

        try:
            settings = bpy.context.scene.oc_viewer
            shader.uniform_float("u_gain", settings.gain)
            shader.uniform_float("u_gamma", settings.gamma)
            shader.uniform_float("u_channel", _CHANNEL_MAP.get(settings.channel_mode, 0.0))
            shader.uniform_float("u_false_color", 1.0 if settings.false_color else 0.0)
            shader.uniform_float("u_clipping", 1.0 if settings.clipping else 0.0)
            shader.uniform_float("u_bg_mode", _BG_MODE_MAP.get(settings.bg_mode, 0.0))
            bg = settings.bg_custom_color
            shader.uniform_float("u_bg_color", [bg[0], bg[1], bg[2]])
            # Colorspace/LUT mode for display: determine from colorspace setting
            # 0=sRGB, 1=Linear/Raw, 2=AgX-like tonemapping
            cs = settings.colorspace.lower() if settings.colorspace else 'linear'
            if 'linear' in cs or 'acescg' in cs or 'aces' in cs:
                lut_mode = 1.0  # Linear/Raw display
            elif 'srgb' in cs or 'rec.1886' in cs:
                lut_mode = 0.0  # sRGB curve
            else:
                lut_mode = 1.0  # Default to linear for unknown
            shader.uniform_float("u_lut_mode", lut_mode)
        except Exception:
            shader.uniform_float("u_gain", 1.0)
            shader.uniform_float("u_gamma", 1.0)
            shader.uniform_float("u_channel", 0.0)
            shader.uniform_float("u_false_color", 0.0)
            shader.uniform_float("u_clipping", 0.0)
            shader.uniform_float("u_bg_mode", 0.0)
            shader.uniform_float("u_bg_color", [0.0, 0.0, 0.0])
            shader.uniform_float("u_lut_mode", 2.0)  # Default to AgX

        shader.uniform_float("u_zoom", _viewer_state.get("zoom", 1.0))
        shader.uniform_float("u_pan", _viewer_state.get("pan", [0.0, 0.0]))
        shader.uniform_float(
            "u_roi_enabled",
            1.0 if _viewer_state.get("roi_enabled", False) else 0.0,
        )
        shader.uniform_float("u_roi", _viewer_state.get("roi", [0.25, 0.25, 0.75, 0.75]))

        try:
            area = bpy.context.area
            shader.uniform_float("u_resolution", [float(area.width), float(area.height)])
        except Exception:
            shader.uniform_float("u_resolution", [1920.0, 1080.0])

        # Image resolution for aspect ratio correction
        shader.uniform_float("u_image_resolution", [float(tex.width), float(tex.height)])

    batch.draw(shader)

    gpu.state.blend_set('NONE')

    # Draw HUD overlay
    _draw_hud(tex)


def _draw_hud(tex):
    """Draw Nuke-style HUD overlay with file metadata, resolution, and zoom.

    Layout (two lines):
        Line 1 (bottom-left): filename | format | compression | bit depth | image_type | resolution | channels
        Line 2 (above line 1): software/nuke | [channel mode] | gain | timecode
        Bottom-right: LUT | cache info | frame | zoom%
    """
    try:
        import blf
        area = bpy.context.area
        if area is None:
            return

        zoom = _viewer_state.get("zoom", 1.0)
        zoom_pct = int(zoom * 100)

        # Gather display info
        channel_str = ""
        gain_str = ""
        try:
            settings = bpy.context.scene.oc_viewer
            ch = settings.channel_mode
            if ch != 'ALL':
                channel_str = f"[{ch}]"
            # Show gain if not 1.0
            if abs(settings.gain - 1.0) > 0.01:
                gain_str = f"gain:{settings.gain:.2f}"
        except Exception:
            pass

        # Get frame number
        try:
            frame = bpy.context.scene.frame_current
        except Exception:
            frame = 1

        # Get metadata from viewer state
        source_file = _viewer_state.get("source_file") or "untitled"
        file_format = _viewer_state.get("format") or ""
        bit_depth = _viewer_state.get("bit_depth") or "32-bit float"
        compression = _viewer_state.get("compression") or ""
        channels = _viewer_state.get("channels")
        channel_names = _viewer_state.get("channel_names")
        timecode = _viewer_state.get("timecode")
        pixel_aspect = _viewer_state.get("pixel_aspect", 1.0)
        image_type = _viewer_state.get("image_type")
        nuke_version = _viewer_state.get("nuke_version")
        software = _viewer_state.get("software")
        proxy_factor = _viewer_state.get("proxy_factor", 1)
        original_width = _viewer_state.get("original_width")
        original_height = _viewer_state.get("original_height")

        # Get colorspace - auto-detect from file metadata or use setting
        file_colorspace = _viewer_state.get("colorspace")  # From file metadata
        detected_cs = _detect_colorspace(file_colorspace) if file_colorspace else None

        # Get colorspace from settings, or use detected/default
        try:
            settings = bpy.context.scene.oc_viewer
            colorspace = settings.colorspace or detected_cs or "Linear Rec.709"
            # Update detected colorspace in settings
            if detected_cs and not settings.detected_colorspace:
                settings.detected_colorspace = detected_cs
        except Exception:
            colorspace = detected_cs or "Linear Rec.709"

        # Font settings
        font_id = 0
        line_height = 16

        # ── Line 1: File info (bottom) ──
        blf.size(font_id, 11)
        blf.color(font_id, 0.7, 0.7, 0.7, 0.75)

        parts1 = [source_file]
        if file_format:
            parts1.append(file_format)
        if compression:
            parts1.append(compression)
        parts1.append(bit_depth)
        if image_type:
            parts1.append(image_type)

        line1 = "  |  ".join(parts1)
        blf.position(font_id, 12, 12, 0)
        blf.draw(font_id, line1)

        # Now draw resolution separately (with PROXY in green if needed)
        line1_w = blf.dimensions(font_id, line1 + "  |  ")[0]

        if proxy_factor > 1 and original_width and original_height:
            # Draw PROXY in green
            blf.color(font_id, 0.4, 0.9, 0.4, 0.9)  # Bright green
            blf.position(font_id, 12 + line1_w, 12, 0)
            proxy_text = f"PROXY 1/{proxy_factor} "
            blf.draw(font_id, proxy_text)
            proxy_w = blf.dimensions(font_id, proxy_text)[0]

            # Resolution in normal color
            blf.color(font_id, 0.7, 0.7, 0.7, 0.75)
            res_str = f"{tex.width}×{tex.height}"
            if pixel_aspect != 1.0 and abs(pixel_aspect - 1.0) > 0.01:
                res_str += f" ({pixel_aspect:.3f})"
            # Show original size in parentheses
            res_str += f" (full: {original_width}×{original_height})"
            blf.position(font_id, 12 + line1_w + proxy_w, 12, 0)
            blf.draw(font_id, res_str)
            res_w = blf.dimensions(font_id, res_str)[0]
            total_line1_w = line1_w + proxy_w + res_w
        else:
            # Normal resolution (no proxy)
            blf.color(font_id, 0.7, 0.7, 0.7, 0.75)
            res_str = f"{tex.width}×{tex.height}"
            if pixel_aspect != 1.0 and abs(pixel_aspect - 1.0) > 0.01:
                res_str += f" ({pixel_aspect:.3f})"
            blf.position(font_id, 12 + line1_w, 12, 0)
            blf.draw(font_id, res_str)
            res_w = blf.dimensions(font_id, res_str)[0]
            total_line1_w = line1_w + res_w

        # Channel info
        if channel_names and len(channel_names) > 0:
            ch_str = ",".join(channel_names[:6])  # Max 6 channels shown
            if len(channel_names) > 6:
                ch_str += f"...+{len(channel_names)-6}"
            blf.color(font_id, 0.7, 0.7, 0.7, 0.75)
            blf.position(font_id, 12 + total_line1_w + blf.dimensions(font_id, "  |  ")[0], 12, 0)
            blf.draw(font_id, ch_str)
        elif channels:
            blf.color(font_id, 0.7, 0.7, 0.7, 0.75)
            blf.position(font_id, 12 + total_line1_w + blf.dimensions(font_id, "  |  ")[0], 12, 0)
            blf.draw(font_id, f"{channels}ch")

        # ── Line 2: Software/view info (above line 1) ──
        parts2 = []
        # Show Nuke version if available, otherwise software
        if nuke_version:
            parts2.append(nuke_version)
        elif software:
            parts2.append(software)
        if channel_str:
            parts2.append(channel_str)
        if gain_str:
            parts2.append(gain_str)
        if timecode:
            parts2.append(f"TC:{timecode}")

        line2 = "  |  ".join(parts2) if parts2 else ""

        if line2:
            blf.color(font_id, 0.6, 0.7, 0.8, 0.75)  # Slightly blue tint
            blf.position(font_id, 12, 12 + line_height, 0)
            blf.draw(font_id, line2)

        # ── Bottom-right: Colorspace | cache info | frame | zoom (all on same line) ──
        cache_info = get_cache_memory_info()
        cache_str = f"Cache: {cache_info['used_gb']:.1f}/{cache_info['limit_gb']:.0f}GB ({cache_info['frame_count']}f)"

        # Build the right-side text with Colorspace
        right_text = f"{colorspace}   |   {cache_str}   |   Frame {frame}   {zoom_pct}%"
        text_w = blf.dimensions(font_id, right_text)[0]

        # Draw Colorspace in cyan
        blf.color(font_id, 0.4, 0.8, 0.9, 0.85)  # Cyan for colorspace
        blf.position(font_id, area.width - text_w - 12, 12, 0)
        blf.draw(font_id, colorspace)
        cs_w = blf.dimensions(font_id, colorspace + "   |   ")[0]

        # Draw cache part in green/gray
        if cache_info['frame_count'] > 0:
            blf.color(font_id, 0.4, 0.9, 0.4, 0.85)  # Green when cached
        else:
            blf.color(font_id, 0.5, 0.5, 0.5, 0.75)  # Gray when empty
        blf.position(font_id, area.width - text_w - 12 + cs_w, 12, 0)
        blf.draw(font_id, cache_str)
        cache_w = blf.dimensions(font_id, cache_str)[0]

        # Draw separator and frame/zoom in normal color
        blf.color(font_id, 0.7, 0.7, 0.7, 0.75)
        rest_text = f"   |   Frame {frame}   {zoom_pct}%"
        blf.position(font_id, area.width - text_w - 12 + cs_w + cache_w, 12, 0)
        blf.draw(font_id, rest_text)

    except Exception:
        pass


# ── OCIO display GLSL extraction ────────────────────────────────────────

def extract_ocio_display_glsl(view_transform=None):
    """Extract OCIO display transform GLSL for the given view transform.

    Args:
        view_transform: OCIO view transform name (e.g., 'AgX', 'Standard', 'Raw')
                       If None, uses scene's current view transform.

    Returns the GLSL function text, or None if extraction fails.
    Used by the viewer to inject colour management into the display shader.
    """
    try:
        bpy.utils.expose_bundled_modules()
        import PyOpenColorIO as ocio
        import pathlib

        config = ocio.GetCurrentConfig()
        if config is None:
            # Fallback: load from bundled Blender config
            repo_root = pathlib.Path(__file__).resolve().parents[3]
            config_path = (
                repo_root / "blender" / "5.0" / "datafiles"
                / "colormanagement" / "config.ocio"
            )
            if not config_path.exists():
                return None
            config = ocio.Config.CreateFromFile(str(config_path))
            ocio.SetCurrentConfig(config)

        # Get view transform from scene if not specified
        if view_transform is None:
            try:
                view_transform = bpy.context.scene.view_settings.view_transform
            except Exception:
                view_transform = 'Standard'

        # Get display device
        display = config.getDefaultDisplay()

        # Create processor: scene_linear -> display/view
        processor = config.getProcessor(
            ocio.ROLE_SCENE_LINEAR,
            display,
            view_transform,
            ocio.TRANSFORM_DIR_FORWARD
        )
        gpu_proc = processor.getDefaultGPUProcessor()
        desc = ocio.GpuShaderDesc.CreateShaderDesc()
        desc.setLanguage(ocio.GPU_LANGUAGE_GLSL_4_0)
        gpu_proc.extractGpuShaderInfo(desc)

        glsl_text = desc.getShaderText()
        if glsl_text:
            print(f"[OpenComp] OCIO GLSL extracted for {view_transform}")
        return glsl_text

    except Exception as e:
        print(f"[OpenComp] OCIO GLSL extraction failed: {e}")
        return None


# ── Viewer Node ─────────────────────────────────────────────────────────

class ViewerNode(OpenCompNode):
    """Display node — routes input texture to the viewport draw handler."""

    bl_idname = "OC_N_viewer"
    bl_label = "Viewer"
    bl_icon = "HIDE_OFF"

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")

    def _gather_upstream_metadata(self):
        """Trace upstream to find source Read node and gather metadata."""
        from ..io.read import _metadata_cache

        metadata = {
            "source_file": None,
            "source_node": None,
            "colorspace": None,
            "view_transform": None,
            "format": None,
            "bit_depth": "32-bit float",
            "compression": None,
            "channels": None,
            "channel_names": None,
            "software": None,
            "pixel_aspect": 1.0,
            "timecode": None,
            "image_type": None,
            "nuke_version": None,
            "original_width": None,
            "original_height": None,
            "proxy_factor": 1,
        }

        # Walk upstream through input connections to find Read node
        visited = set()
        to_visit = [self]

        while to_visit:
            node = to_visit.pop(0)
            if node.name in visited:
                continue
            visited.add(node.name)

            # Check if this is a Read node with cached metadata
            if node.bl_idname == "OC_N_read":
                cached = _metadata_cache.get(node.name)
                if cached:
                    metadata["source_file"] = cached.get("filename")
                    metadata["source_node"] = node.name
                    metadata["format"] = cached.get("format")
                    metadata["bit_depth"] = cached.get("bit_depth", "32-bit float")
                    metadata["compression"] = cached.get("compression")
                    metadata["channels"] = cached.get("channels")
                    metadata["channel_names"] = cached.get("channel_names")
                    metadata["colorspace"] = cached.get("colorspace")
                    metadata["software"] = cached.get("software")
                    metadata["pixel_aspect"] = cached.get("pixel_aspect", 1.0)
                    metadata["timecode"] = cached.get("timecode")
                    metadata["image_type"] = cached.get("image_type")
                    metadata["nuke_version"] = cached.get("nuke_version")
                    # Original dimensions from metadata
                    metadata["original_width"] = cached.get("width")
                    metadata["original_height"] = cached.get("height")

                # Get proxy factor from viewer settings
                try:
                    metadata["proxy_factor"] = int(bpy.context.scene.oc_viewer.proxy)
                except (AttributeError, ValueError):
                    metadata["proxy_factor"] = 1

                break  # Found source, stop searching

            # Add upstream nodes to visit
            for inp in node.inputs:
                if inp.is_linked:
                    for link in inp.links:
                        upstream = link.from_node
                        if upstream.name not in visited:
                            to_visit.append(upstream)

        # Get current OCIO view transform
        try:
            metadata["view_transform"] = bpy.context.scene.view_settings.view_transform
        except Exception:
            metadata["view_transform"] = "Standard"

        return metadata

    def evaluate(self, texture_pool):
        """Store input texture for the draw handler. Returns None (no output)."""
        try:
            current_frame = bpy.context.scene.frame_current

            # Get texture from upstream (Read node handles caching)
            input_tex = self.inputs["Image"].get_texture()
            _viewer_state["texture"] = input_tex
            _viewer_state["current_frame"] = current_frame

            # Gather and store upstream metadata for HUD
            if input_tex is not None:
                metadata = self._gather_upstream_metadata()
                _viewer_state["source_file"] = metadata["source_file"]
                _viewer_state["source_node"] = metadata["source_node"]
                _viewer_state["colorspace"] = metadata["colorspace"]
                _viewer_state["view_transform"] = metadata["view_transform"]
                _viewer_state["format"] = metadata["format"]
                _viewer_state["bit_depth"] = metadata["bit_depth"]
                _viewer_state["compression"] = metadata["compression"]
                _viewer_state["channels"] = metadata["channels"]
                _viewer_state["channel_names"] = metadata["channel_names"]
                _viewer_state["software"] = metadata["software"]
                _viewer_state["pixel_aspect"] = metadata["pixel_aspect"]
                _viewer_state["timecode"] = metadata["timecode"]
                _viewer_state["image_type"] = metadata["image_type"]
                _viewer_state["nuke_version"] = metadata["nuke_version"]
                _viewer_state["original_width"] = metadata["original_width"]
                _viewer_state["original_height"] = metadata["original_height"]
                _viewer_state["proxy_factor"] = metadata["proxy_factor"]
            else:
                # Clear all metadata
                for key in ["source_file", "source_node", "colorspace", "view_transform",
                            "format", "compression", "channels", "channel_names",
                            "software", "timecode", "image_type", "nuke_version",
                            "original_width", "original_height"]:
                    _viewer_state[key] = None
                _viewer_state["bit_depth"] = "32-bit float"
                _viewer_state["pixel_aspect"] = 1.0
                _viewer_state["proxy_factor"] = 1

            return None
        except Exception as e:
            print(f"[OpenComp] ViewerNode.evaluate error: {e}")
            _viewer_state["texture"] = None
            return None


# ── Timeline cache bar overlay ─────────────────────────────────────────

_timeline_handler = None

def _draw_timeline_cache_bar():
    """Draw cache bar overlay on Blender's native timeline."""
    import gpu
    from gpu_extras.batch import batch_for_shader

    context = bpy.context
    if context.area is None or context.area.type != 'DOPESHEET_EDITOR':
        return

    # Only draw in timeline mode
    space = context.space_data
    if space.mode != 'TIMELINE':
        return

    cached_frames = get_cached_frames()
    if not cached_frames:
        return

    region = context.region
    scene = context.scene
    frame_start = scene.frame_start
    frame_end = scene.frame_end

    if frame_end <= frame_start:
        return

    # Get view bounds (visible frame range)
    view2d = region.view2d
    view_left, view_bottom = view2d.region_to_view(0, 0)
    view_right, view_top = view2d.region_to_view(region.width, region.height)

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    # Draw cached frame indicators at top of timeline
    bar_height = 4
    bar_y = region.height - 8  # Near top of timeline

    for cached_frame in cached_frames:
        if view_left <= cached_frame <= view_right:
            # Convert frame to screen x position
            x, _ = view2d.view_to_region(cached_frame, 0, clip=False)
            x_next, _ = view2d.view_to_region(cached_frame + 1, 0, clip=False)
            width = max(3, x_next - x - 1)

            verts = [
                (x, bar_y),
                (x + width, bar_y),
                (x + width, bar_y + bar_height),
                (x, bar_y + bar_height),
            ]
            indices = [(0, 1, 2), (0, 2, 3)]
            batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
            shader.bind()
            shader.uniform_float("color", (0.2, 0.85, 0.2, 0.9))  # Bright green
            batch.draw(shader)

    gpu.state.blend_set('NONE')


# ── Registration ────────────────────────────────────────────────────────

def register():
    global _timeline_handler

    bpy.utils.register_class(OpenCompViewerSettings)
    bpy.types.Scene.oc_viewer = bpy.props.PointerProperty(
        type=OpenCompViewerSettings
    )
    bpy.utils.register_class(ViewerNode)

    # Register draw handler only when not in background mode
    if not bpy.app.background:
        _viewer_state["handler"] = bpy.types.SpaceView3D.draw_handler_add(
            _draw_viewer_callback, (), 'WINDOW', 'POST_PIXEL'
        )
        # Register timeline cache bar overlay
        _timeline_handler = bpy.types.SpaceDopeSheetEditor.draw_handler_add(
            _draw_timeline_cache_bar, (), 'WINDOW', 'POST_PIXEL'
        )
        print("[OpenComp] Viewer draw handler registered")
        print("[OpenComp] Timeline cache bar registered")


def unregister():
    global _timeline_handler

    if _viewer_state["handler"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(
            _viewer_state["handler"], 'WINDOW'
        )
        _viewer_state["handler"] = None

    if _timeline_handler is not None:
        bpy.types.SpaceDopeSheetEditor.draw_handler_remove(
            _timeline_handler, 'WINDOW'
        )
        _timeline_handler = None

    try:
        bpy.utils.unregister_class(ViewerNode)
    except RuntimeError:
        pass

    try:
        del bpy.types.Scene.oc_viewer
    except (AttributeError, RuntimeError):
        pass

    try:
        bpy.utils.unregister_class(OpenCompViewerSettings)
    except RuntimeError:
        pass
