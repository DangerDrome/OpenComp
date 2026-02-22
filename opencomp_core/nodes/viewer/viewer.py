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
}


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


def _on_proxy_update(self, context):
    """Invalidate Read node caches and trigger re-evaluation when proxy changes."""
    from ..io.read import _read_cache
    _read_cache.clear()
    from ...node_graph.tree import request_evaluate
    request_evaluate()


class OpenCompViewerSettings(bpy.types.PropertyGroup):
    """Viewer display controls — stored on Scene, read by draw handler."""

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
            print(f"[OpenComp] Viewer shader compile failed entirely: {e}")
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
        except Exception:
            shader.uniform_float("u_gain", 1.0)
            shader.uniform_float("u_gamma", 1.0)
            shader.uniform_float("u_channel", 0.0)
            shader.uniform_float("u_false_color", 0.0)
            shader.uniform_float("u_clipping", 0.0)
            shader.uniform_float("u_bg_mode", 0.0)
            shader.uniform_float("u_bg_color", [0.0, 0.0, 0.0])

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
    """Draw a small HUD overlay with resolution, channel mode, and zoom %."""
    try:
        import blf
        area = bpy.context.area
        if area is None:
            return

        zoom = _viewer_state.get("zoom", 1.0)
        zoom_pct = int(zoom * 100)

        # Get channel mode
        channel_str = ""
        try:
            settings = bpy.context.scene.oc_viewer
            ch = settings.channel_mode
            if ch != 'ALL':
                channel_str = f"  [{ch}]"
        except Exception:
            pass

        # Font settings — font_id 0 is Blender's default
        font_id = 0
        blf.size(font_id, 13)
        blf.color(font_id, 0.7, 0.7, 0.7, 0.6)

        # Bottom-left: resolution + channel
        res_text = f"{tex.width}x{tex.height}{channel_str}"
        blf.position(font_id, 10, 10, 0)
        blf.draw(font_id, res_text)

        # Bottom-right: zoom percentage
        zoom_text = f"{zoom_pct}%"
        # Measure text width for right-alignment
        text_w = blf.dimensions(font_id, zoom_text)[0]
        blf.position(font_id, area.width - text_w - 10, 10, 0)
        blf.draw(font_id, zoom_text)

    except Exception:
        pass


# ── OCIO display GLSL extraction ────────────────────────────────────────

def extract_ocio_display_glsl():
    """Extract OCIO display transform GLSL for scene_linear -> sRGB.

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

        processor = config.getProcessor(
            ocio.ROLE_SCENE_LINEAR, "sRGB"
        )
        gpu_proc = processor.getDefaultGPUProcessor()
        desc = ocio.GpuShaderDesc.CreateShaderDesc()
        desc.setLanguage(ocio.GPU_LANGUAGE_GLSL_1_3)
        gpu_proc.extractGpuShaderInfo(desc)

        glsl_text = desc.getShaderText()
        if glsl_text:
            print("[OpenComp] OCIO display GLSL extracted")
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
        self.inputs.new("OC_NS_image", "Image")

    def evaluate(self, texture_pool):
        """Store input texture for the draw handler. Returns None (no output)."""
        try:
            input_tex = self.inputs["Image"].get_texture()
            _viewer_state["texture"] = input_tex
            return None
        except Exception as e:
            print(f"[OpenComp] ViewerNode.evaluate error: {e}")
            _viewer_state["texture"] = None
            return None


# ── Registration ────────────────────────────────────────────────────────

def register():
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
        print("[OpenComp] Viewer draw handler registered")


def unregister():
    if _viewer_state["handler"] is not None:
        bpy.types.SpaceView3D.draw_handler_remove(
            _viewer_state["handler"], 'WINDOW'
        )
        _viewer_state["handler"] = None

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
