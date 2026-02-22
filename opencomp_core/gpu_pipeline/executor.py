"""OpenComp shader executor — core dispatch for the GPU pipeline.

evaluate_shader() is called by every processing node. It:
  1. Loads and caches the compiled shader
  2. Allocates an output texture from the pool
  3. Renders a fullscreen quad with the shader into a framebuffer
  4. Returns the output texture
"""

from pathlib import Path

SHADER_DIR = Path(__file__).resolve().parent.parent / "shaders"

# Shader cache: frag_name → (GPUShader, batch)
_shader_cache = {}


def get_shader_source(frag_name):
    """Read vertex + fragment shader source files. Works without GPU."""
    vert_path = SHADER_DIR / "fullscreen_quad.vert"
    frag_path = SHADER_DIR / frag_name

    if not vert_path.exists():
        raise FileNotFoundError(f"Vertex shader not found: {vert_path}")
    if not frag_path.exists():
        raise FileNotFoundError(f"Fragment shader not found: {frag_path}")

    return vert_path.read_text(), frag_path.read_text()


def _get_cached_shader(frag_name):
    """Get or compile+cache a shader. Requires GPU context."""
    if frag_name in _shader_cache:
        return _shader_cache[frag_name]

    import gpu
    from gpu_extras.batch import batch_for_shader

    vert_src, frag_src = get_shader_source(frag_name)
    shader = gpu.types.GPUShader(vert_src, frag_src)

    batch = batch_for_shader(
        shader, 'TRIS',
        {"position": [(-1, -1), (1, -1), (1, 1), (-1, 1)]},
        indices=[(0, 1, 2), (0, 2, 3)],
    )

    _shader_cache[frag_name] = (shader, batch)
    print(f"[OpenComp] Shader compiled: {frag_name}")
    return shader, batch


def evaluate_shader(frag_name, input_tex, uniforms, texture_pool,
                    extra_textures=None, output_size=None):
    """Core shader dispatch. Requires GPU context.

    Args:
        frag_name:      fragment shader filename (e.g. "grade.frag")
        input_tex:      input GPUTexture (bound as u_image), or None for generators
        uniforms:       dict of uniform name → value (float, list, or int)
        texture_pool:   TexturePool for output allocation
        extra_textures: optional dict of sampler name → GPUTexture (for merge nodes)
        output_size:    optional (w, h) tuple — used when input_tex is None

    Returns:
        GPUTexture with the rendered result
    """
    import gpu

    shader, batch = _get_cached_shader(frag_name)

    if output_size:
        w, h = output_size
    elif input_tex is not None:
        w, h = input_tex.width, input_tex.height
    else:
        raise ValueError("Either input_tex or output_size must be provided")

    output_tex = texture_pool.get(w, h)
    fb = gpu.types.GPUFrameBuffer(color_slots=[output_tex])

    with fb.bind():
        shader.bind()
        if input_tex is not None:
            shader.uniform_sampler("u_image", input_tex)
        if extra_textures:
            for name, tex in extra_textures.items():
                shader.uniform_sampler(name, tex)
        for name, value in uniforms.items():
            if isinstance(value, (int, float)):
                shader.uniform_float(name, value)
            elif isinstance(value, (list, tuple)):
                shader.uniform_float(name, value)
        batch.draw(shader)

    return output_tex


def clear_cache():
    """Clear the shader cache (e.g. on addon unregister)."""
    _shader_cache.clear()
