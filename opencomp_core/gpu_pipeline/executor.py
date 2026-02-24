"""OpenComp shader executor — core dispatch for the GPU pipeline.

evaluate_shader() is called by every processing node. It:
  1. Loads and caches the compiled shader
  2. Allocates an output texture from the pool
  3. Renders a fullscreen quad with the shader into a framebuffer
  4. Returns the output texture
"""

import re
from pathlib import Path

SHADER_DIR = Path(__file__).resolve().parent.parent / "shaders"

# Shader cache: frag_name → (GPUShader, batch, uniforms_info)
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


def _parse_uniforms(shader_src):
    """Parse uniform declarations from shader source.

    Returns:
        samplers: list of sampler names for sampler2D uniforms
        push_constants: list of (glsl_type, name) for other uniforms
    """
    samplers = []
    push_constants = []

    # Match: uniform sampler2D name;
    sampler_pattern = re.compile(r'uniform\s+sampler2D\s+(\w+)\s*;')
    for match in sampler_pattern.finditer(shader_src):
        samplers.append(match.group(1))

    # Match: uniform type name; (vec2, vec3, vec4, float, int, mat3, mat4)
    uniform_pattern = re.compile(r'uniform\s+(float|int|vec2|vec3|vec4|mat3|mat4)\s+(\w+)\s*;')
    for match in uniform_pattern.finditer(shader_src):
        glsl_type = match.group(1)
        name = match.group(2)
        push_constants.append((glsl_type, name))

    return samplers, push_constants


def _strip_declarations(shader_src):
    """Strip in/out/uniform declarations from shader, keep only main()."""
    # Remove uniform declarations
    shader_src = re.sub(r'uniform\s+\w+\s+\w+\s*;', '', shader_src)
    # Remove in declarations
    shader_src = re.sub(r'\bin\s+\w+\s+\w+\s*;', '', shader_src)
    # Remove out declarations
    shader_src = re.sub(r'\bout\s+\w+\s+\w+\s*;', '', shader_src)
    return shader_src


def _glsl_to_gpu_type(glsl_type):
    """Convert GLSL type name to GPU module type string."""
    mapping = {
        'float': 'FLOAT',
        'int': 'INT',
        'vec2': 'VEC2',
        'vec3': 'VEC3',
        'vec4': 'VEC4',
        'mat3': 'MAT3',
        'mat4': 'MAT4',
    }
    return mapping.get(glsl_type, 'FLOAT')


def _get_cached_shader(frag_name):
    """Get or compile+cache a shader. Requires GPU context."""
    if frag_name in _shader_cache:
        return _shader_cache[frag_name]

    import gpu
    from gpu_extras.batch import batch_for_shader

    vert_src, frag_src = get_shader_source(frag_name)

    # Parse uniforms from fragment shader
    samplers, push_constants = _parse_uniforms(frag_src)

    # Strip declarations for GPUShaderCreateInfo compatibility
    vert_clean = _strip_declarations(vert_src)
    frag_clean = _strip_declarations(frag_src)

    try:
        # Blender 4.x+ requires GPUShaderCreateInfo API
        shader_info = gpu.types.GPUShaderCreateInfo()

        # Vertex input: position attribute
        shader_info.vertex_in(0, 'VEC2', "position")

        # Interface between vertex and fragment shader
        interface_info = gpu.types.GPUStageInterfaceInfo("oc_interface")
        interface_info.smooth('VEC2', "v_uv")
        shader_info.vertex_out(interface_info)

        # Fragment output
        shader_info.fragment_out(0, 'VEC4', "out_color")

        # Add sampler uniforms
        for idx, sampler_name in enumerate(samplers):
            shader_info.sampler(idx, 'FLOAT_2D', sampler_name)

        # Add push constant uniforms
        for glsl_type, name in push_constants:
            gpu_type = _glsl_to_gpu_type(glsl_type)
            shader_info.push_constant(gpu_type, name)

        # Set shader sources (stripped of declarations)
        shader_info.vertex_source(vert_clean)
        shader_info.fragment_source(frag_clean)

        # Create shader from info
        shader = gpu.shader.create_from_info(shader_info)
        del shader_info
        del interface_info

    except Exception as e:
        print(f"[OpenComp] Shader compilation failed for {frag_name}: {e}")
        print(f"[OpenComp] Samplers: {samplers}")
        print(f"[OpenComp] Push constants: {push_constants}")
        raise

    batch = batch_for_shader(
        shader, 'TRIS',
        {"position": [(-1, -1), (1, -1), (1, 1), (-1, 1)]},
        indices=[(0, 1, 2), (0, 2, 3)],
    )

    # Store uniform info for binding
    uniforms_info = {'samplers': samplers, 'push_constants': push_constants}
    _shader_cache[frag_name] = (shader, batch, uniforms_info)
    print(f"[OpenComp] Shader compiled: {frag_name}")
    return shader, batch, uniforms_info


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

    shader, batch, uniforms_info = _get_cached_shader(frag_name)

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
