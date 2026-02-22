# OpenComp Conventions

Applies to all Python and GLSL in this project.
OpenClaw agents must read this file before writing any code.

---

## Python Conventions

### General Rules

- Python 3.11+ (Blender 5.x bundled interpreter)
- No external dependencies beyond Blender-bundled libs
- pip install only for: opentimelineio, pycmx, pyaaf2, timecode (conform tool only)
- KISS — if it can be done simply, do it simply
- No classes where a function will do
- No abstraction layers without immediate purpose

### Naming

```python
# Modules — snake_case
opencomp_core/nodes/color/grade.py

# Classes — PascalCase
class GradeNode(OpenCompNode): ...
class ImageSocket(bpy.types.NodeSocket): ...

# Functions and variables — snake_case
def evaluate_node(node, context): ...
input_texture = node.inputs["Image"].get_texture()

# Constants — UPPER_SNAKE_CASE
MAX_TEXTURE_SIZE = 8192
DEFAULT_HANDLES  = 8

# Blender idnames — always prefixed OC_
bl_idname = "OC_NT_compositor"   # NodeTree
bl_idname = "OC_N_grade"         # Node
bl_idname = "OC_NS_image"        # NodeSocket
bl_idname = "OC_OT_load_edl"     # Operator
bl_idname = "OC_PT_viewer"       # Panel
bl_idname = "OC_MT_add"          # Menu
```

### Node Structure Template

Every node follows this pattern exactly:

```python
import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class GradeNode(OpenCompNode):
    """Lift / Gamma / Gain colour grade.

    Inputs:  Image (RGBA32F, linear scene-referred)
    Outputs: Image (RGBA32F, linear scene-referred)
    Shader:  shaders/grade.frag
    """

    bl_idname = "OC_N_grade"
    bl_label  = "Grade"
    bl_icon   = "COLORSET_09_VEC"

    lift:  bpy.props.FloatVectorProperty(name="Lift",  default=(0.0, 0.0, 0.0), size=3)
    gamma: bpy.props.FloatVectorProperty(name="Gamma", default=(1.0, 1.0, 1.0), size=3)
    gain:  bpy.props.FloatVectorProperty(name="Gain",  default=(1.0, 1.0, 1.0), size=3)
    mix:   bpy.props.FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0)

    def init(self, context):
        self.inputs.new("OC_NS_image",  "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "lift")
        layout.prop(self, "gamma")
        layout.prop(self, "gain")
        layout.prop(self, "mix")

    def evaluate(self, texture_pool):
        """Called by evaluator. Returns GPUTexture or None."""
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None
            uniforms = {
                "u_lift":  list(self.lift),
                "u_gamma": list(self.gamma),
                "u_gain":  list(self.gain),
                "u_mix":   self.mix,
            }
            return evaluate_shader("grade.frag", input_tex, uniforms, texture_pool)
        except Exception as e:
            print(f"[OpenComp] GradeNode.evaluate error: {e}")
            return None
```

### GPU Pipeline Rules

```python
# Always use the texture pool — never allocate GPUTexture directly in nodes
output_tex = texture_pool.get(width, height)
texture_pool.release(old_tex)

# Resolve shader paths relative to opencomp_core/shaders/
from pathlib import Path
SHADER_DIR = Path(__file__).resolve().parent.parent.parent / "shaders"

# Uniforms are plain Python types — executor handles GPU upload
uniforms = {
    "u_lift":       [0.0, 0.0, 0.0],   # vec3
    "u_resolution": [1920.0, 1080.0],  # vec2
    "u_mix":        1.0,               # float
}
```

### Error Handling

```python
# Never crash the graph — always return None on failure
def evaluate(self, texture_pool):
    try:
        ...
    except Exception as e:
        print(f"[OpenComp] {self.__class__.__name__}.evaluate error: {e}")
        return None

# Prefix all log output
print(f"[OpenComp] Loading EXR: {filepath}")
print(f"[OpenComp] Shader compiled: {name}")
```

### Blender API Rules

```python
# Version check before using version-specific APIs
from ..compat import BLENDER_VERSION
if BLENDER_VERSION >= (5, 1, 0):
    ...  # 5.1+ API
else:
    ...  # 5.0 fallback

# Never use bpy.ops in GPU pipeline — use only inside Operators

# Safe class registration
def register_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        pass
    bpy.utils.register_class(cls)
```

---

## GLSL Conventions

### File Naming

```
shaders/
├── fullscreen_quad.vert    # Shared vertex shader — never modify
├── passthrough.frag        # Identity — debugging only
├── grade.frag
├── over.frag
├── merge.frag
├── blur_h.frag             # Horizontal gaussian
├── blur_v.frag             # Vertical gaussian
├── transform.frag
├── crop.frag
├── sharpen.frag
└── ocio_display.frag       # Generated at runtime — not in repo
```

One .frag file per node. No shader logic in Python ever.

### Fragment Shader Template

```glsl
/* OpenComp — grade.frag
   Lift / Gamma / Gain colour grade.
   In:  u_image  RGBA32F linear scene-referred
   Out: RGBA32F  linear scene-referred
*/

uniform sampler2D u_image;
uniform vec3      u_lift;
uniform vec3      u_gamma;
uniform vec3      u_gain;
uniform float     u_mix;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec4 src = texture(u_image, v_uv);
    vec3 col = src.rgb;

    col = col + u_lift;
    col = pow(max(col, vec3(0.0)), 1.0 / max(u_gamma, vec3(0.0001)));
    col = col * u_gain;
    col = mix(src.rgb, col, u_mix);

    out_color = vec4(col, src.a);
}
```

### The Shared Vertex Shader (never modify)

```glsl
/* OpenComp — fullscreen_quad.vert */
in  vec2 position;
out vec2 v_uv;

void main() {
    v_uv        = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
```

### GLSL Rules

```glsl
// GLSL 3.30 core profile only — Blender's gpu module target

// Prefix all uniforms with u_
uniform sampler2D u_image;
uniform float     u_opacity;

// Always explicit in/out
in  vec2 v_uv;
out vec4 out_color;    // always named out_color

// Safe math
col    = pow(max(col, vec3(0.0)), vec3(gamma));
result = value / max(denominator, 0.0001);

// NEVER clamp intermediate pipeline values — VFX data lives outside 0-1
// Only clamp at final display output

// Preserve alpha unless node specifically processes it
out_color = vec4(processed_rgb, src.a);

// Premult: all pipeline images are premultiplied
// Unpremult before colour ops, repremult after if needed
vec3 unpremult = (src.a > 0.0001) ? src.rgb / src.a : vec3(0.0);
```

---

## File I/O Conventions

```python
bpy.utils.expose_bundled_modules()
import OpenImageIO as oiio
import numpy as np

# Read — always RGBA float32, shape (H, W, 4)
inp    = oiio.ImageInput.open(filepath)
spec   = inp.spec()
pixels = inp.read_image(oiio.FLOAT).reshape(spec.height, spec.width, spec.nchannels)
if spec.nchannels == 3:
    pixels = np.concatenate(
        [pixels, np.ones((spec.height, spec.width, 1), dtype=np.float32)], axis=2
    )
inp.close()

# Write — float32 EXR by default
out  = oiio.ImageOutput.create(filepath)
spec = oiio.ImageSpec(width, height, 4, oiio.FLOAT)
out.open(filepath, spec)
out.write_image(pixel_array)
out.close()
```

---

## Conform Tool Conventions

```python
DEFAULT_HANDLES = 8   # frames

# Shot names always from OTIO clip.name — never auto-generated
shot_name = clip.name   # e.g. "SH010"

# Path tokens (exact strings)
# {sequence} {shot} {version} {fps} {resolution} {ext}
template      = "{sequence}/{shot}/plates/{shot}_src.%04d.{ext}"
nk_path       = f"{shot_dir}/{shot_name}_v001.nk"
frame_pattern = f"{shot_name}.%04d.exr"
```

---

## OpenClaw Agent Rules

**Allowed:**
- Write to `opencomp_core/nodes/`
- Write to `opencomp_core/shaders/`
- Read any repo file
- Call `opencomp.node_registry.refresh()`

**Forbidden:**
- `import os` (use `pathlib.Path` only)
- `import subprocess`
- `bpy.ops.wm.*`
- Writing outside nodes/ or shaders/
- Modifying `gpu_pipeline/executor.py`
- Any network calls from node code

**Every agent-written node must:**
- Follow Node Structure Template exactly
- Docstring listing inputs, outputs, shader file
- Handle None input gracefully
- Use texture pool — never raw GPUTexture allocation
- Have matching .frag file
- Entry in node_registry.json

---

## What Good Looks Like

A new node = 1 Python file (~60 lines) + 1 GLSL file (~30 lines) + 1 registry entry.
If it takes significantly more, it is over-engineered.
