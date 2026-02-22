# OpenComp — Claude Code Context

Read this file at the start of every session before writing any code.
Also read ARCHITECTURE.md, CONVENTIONS.md, and ROADMAP.md in full.

---

## What We Are Building

**OpenComp** — an open source, Nuke-like VFX compositor built as a Blender 5.x add-on.
Zero compilation. Python + GLSL only. GPL 3.0.

NOT using Blender's compositor. NOT forking Blender. NOT building from scratch.
Using Blender purely as infrastructure while building a custom GPU compositor on top.

Why this works:
- Blender 4.4+ exposes OCIO, OIIO, numpy via `bpy.utils.expose_bundled_modules()`
- Blender's `gpu` module supports RGBA32F textures + fragment shaders + framebuffers
- `bpy.types.NodeTree` subclassing gives a free node editor UI
- Blender 5.0+ has standalone reusable CompositorNodeTree objects

---

## Blender Binary Location

Blender is bundled inside this repo. The binary lives at:

    ./blender/blender          (Linux/macOS)
    ./blender/blender.exe      (Windows)

All Blender invocations use the repo-local binary:

    ./blender/blender --background --python tests/run_tests.py

The blender/ directory is gitignored. Users download Blender 5.0 stable
from blender.org and extract it to ./blender/ themselves before running anything.

Never assume a system Blender. Always use the repo-local binary.

---

## The Stack (locked — do not redesign)

```
OPENCOMP PRODUCT
├── Conform Tool     (OTIO + VSE + .nk exporter)
├── Compositor       (custom NodeTree + GPU shader pipeline)
└── OpenClaw AI      (sandboxed node builder — post-MVP)
         ↓
UI LAYER (App Template + Python header overrides)
         ↓
NODE LIBRARY (io / color / merge / filter / transform / viewer)
         ↓
GLSL SHADER BANK (one .frag per node + shared .vert)
         ↓
BLENDER 5.x INFRASTRUCTURE (OCIO, OIIO, GPU context, VSE, numpy)
         ↓
HOST OS (Rocky 9 / macOS / Windows)
```

---

## GPU Execution Model (do not change this)

Every node = one GLSL fragment shader + one fullscreen quad draw call.
Intermediate results = RGBA32F GPUTexture living on GPU.
CPU only touched at: Read (OIIO → GPU) and Write/Viewer (GPU → disk/screen).

```
[Read] → RGBA32F GPUTexture
              ↓
         [Grade] → frag shader → GPUFrameBuffer → RGBA32F
              ↓
         [Over]  → frag shader → GPUFrameBuffer → RGBA32F
              ↓
         [Viewer] → gpu draw handler → fullscreen quad → screen
                    (OCIO display GLSL injected here)
```

Ping-pong framebuffers between nodes.
Texture pool reuses RGBA32F allocations — never allocate GPUTexture directly in nodes.

---

## Project Structure

```
opencomp/
├── CLAUDE.md                        ← this file
├── ARCHITECTURE.md
├── CONVENTIONS.md
├── ROADMAP.md
├── BLOCKERS.md                      ← created by Claude Code if needed
├── LICENSE
├── README.md
├── install.py                       ← configures bundled Blender, run once
├── blender/                         ← gitignored, user extracts Blender here
│   └── blender                      ← the binary
│
├── app_template/                    ← Blender app template
│   ├── __init__.py
│   ├── userpref.blend
│   └── splash.png
│
├── opencomp_core/                   ← the add-on
│   ├── __init__.py
│   ├── node_graph/
│   │   ├── __init__.py
│   │   ├── tree.py                  ← OpenCompNodeTree
│   │   ├── evaluator.py             ← topological sort + dirty propagation
│   │   └── sockets.py               ← ImageSocket, FloatSocket, VectorSocket
│   ├── gpu_pipeline/
│   │   ├── __init__.py
│   │   ├── executor.py              ← evaluate_shader() core dispatch
│   │   ├── texture_pool.py          ← RGBA32F GPUTexture reuse
│   │   └── framebuffer.py           ← ping-pong GPUFrameBuffer system
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── base.py                  ← OpenCompNode base class
│   │   ├── io/        read.py  write.py
│   │   ├── color/     grade.py  cdl.py
│   │   ├── merge/     over.py  merge.py
│   │   ├── filter/    blur.py  sharpen.py
│   │   ├── transform/ transform.py  crop.py
│   │   └── viewer/    viewer.py
│   ├── shaders/
│   │   ├── fullscreen_quad.vert     ← shared, never modify
│   │   ├── passthrough.frag
│   │   ├── grade.frag
│   │   ├── over.frag
│   │   ├── merge.frag
│   │   ├── blur_h.frag
│   │   ├── blur_v.frag
│   │   └── transform.frag
│   ├── conform/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   ├── matcher.py
│   │   ├── handles.py
│   │   ├── structure.py
│   │   ├── nk_export.py
│   │   └── vse_bridge.py
│   ├── openclaw_integration/
│   │   ├── __init__.py
│   │   ├── agent_server.py
│   │   ├── node_builder.py
│   │   ├── hot_reload.py
│   │   ├── validator.py
│   │   └── memory/
│   │       ├── codebase.md
│   │       ├── conventions.md
│   │       └── node_registry.json
│   └── compat/
│       ├── __init__.py
│       ├── blender_5x.py
│       └── blender_51.py
│
└── tests/
    ├── __init__.py
    ├── run_tests.py                 ← master runner, exit 0=pass 1=fail
    ├── test_phase0.py
    ├── test_phase1.py
    └── test_phase2.py
```

---

## Key APIs

### Repo-local Blender path

```python
import pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parent
BLENDER   = REPO_ROOT / "blender" / "blender"
# Windows: REPO_ROOT / "blender" / "blender.exe"
```

### expose_bundled_modules

```python
import bpy
bpy.utils.expose_bundled_modules()
import OpenImageIO as oiio     # OIIO 3.1
import PyOpenColorIO as ocio   # OCIO 2.5
import numpy as np
```

### GPU pipeline

```python
import gpu
from gpu_extras.batch import batch_for_shader

# RGBA32F texture
tex = gpu.types.GPUTexture((width, height), format='RGBA32F')

# Framebuffer
fb = gpu.types.GPUFrameBuffer(color_slots=[tex])

# Shader (compile once, cache)
shader = gpu.types.GPUShader(vert_src, frag_src)

# Fullscreen quad draw
with fb.bind():
    shader.bind()
    shader.uniform_sampler("u_image", input_tex)
    batch.draw(shader)

# Viewport draw handler
handle = bpy.types.SpaceView3D.draw_handler_add(
    draw_cb, (self, context), 'WINDOW', 'POST_PIXEL'
)
```

### OIIO read → GPUTexture

```python
bpy.utils.expose_bundled_modules()
import OpenImageIO as oiio, numpy as np, gpu

inp    = oiio.ImageInput.open(filepath)
spec   = inp.spec()
pixels = inp.read_image(oiio.FLOAT).reshape(spec.height, spec.width, spec.nchannels)
if spec.nchannels == 3:
    pixels = np.concatenate(
        [pixels, np.ones((spec.height, spec.width, 1), dtype=np.float32)], axis=2
    )
inp.close()
tex = gpu.types.GPUTexture(
    (spec.width, spec.height), format='RGBA32F',
    data=gpu.types.Buffer('FLOAT', pixels.size, pixels.flatten().tolist())
)
```

### OCIO display GLSL

```python
bpy.utils.expose_bundled_modules()
import PyOpenColorIO as ocio

config    = ocio.GetCurrentConfig()
processor = config.getProcessor("scene_linear", "sRGB")
gpu_proc  = processor.getDefaultGPUProcessor()
desc      = ocio.GpuShaderDesc.CreateShaderDesc()
desc.setLanguage(ocio.GPU_LANGUAGE_GLSL_1_3)
gpu_proc.extractGpuShaderInfo(desc)
ocio_glsl = desc.getShaderText()   # inject into display frag shader
```

### NodeTree skeleton

```python
class OpenCompNodeTree(bpy.types.NodeTree):
    bl_idname = "OC_NT_compositor"
    bl_label  = "OpenComp Compositor"
    bl_icon   = "NODE_COMPOSITING"

class OpenCompNode(bpy.types.Node):
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "OC_NT_compositor"

    def evaluate(self, texture_pool):
        raise NotImplementedError
```

---

## Known Gotchas — Read Before Writing Any GPU or Blender Code

These will cost hours if hit blind. Fix them proactively.

### GPU / Shader

**1. Draw handler mode must be POST_PIXEL not POST_VIEW**
```python
# CORRECT
bpy.types.SpaceView3D.draw_handler_add(
    callback, (self, context), 'WINDOW', 'POST_PIXEL'
)
# WRONG — POST_VIEW fires before compositing, image won't show correctly
```

**2. Compile shaders once on registration, never inside the draw callback**
```python
# CORRECT — compile at registration time, store on class or module
_shader_cache = {}
def get_shader(name):
    if name not in _shader_cache:
        _shader_cache[name] = gpu.types.GPUShader(vert, frag)
    return _shader_cache[name]

# WRONG — recompiling every frame is catastrophically slow
def draw_callback():
    shader = gpu.types.GPUShader(vert_src, frag_src)  # never do this
```

**3. Context not ready on first launch — use a timer for initial evaluation**
```python
# If viewport shows nothing on first launch:
bpy.app.timers.register(lambda: trigger_redraw(), first_interval=0.1)
```

**4. GPUTexture data must be gpu.types.Buffer, not a list or numpy array**
```python
# CORRECT
flat = pixels.flatten().tolist()
buf  = gpu.types.Buffer('FLOAT', len(flat), flat)
tex  = gpu.types.GPUTexture((w, h), format='RGBA32F', data=buf)

# WRONG — passing numpy array or plain list directly will fail silently
tex = gpu.types.GPUTexture((w, h), format='RGBA32F', data=pixels)
```

**5. Use GPUFrameBuffer not GPUOffScreen for the ping-pong pipeline**
```python
# CORRECT — you control the RGBA32F texture
tex = gpu.types.GPUTexture((w, h), format='RGBA32F')
fb  = gpu.types.GPUFrameBuffer(color_slots=[tex])

# WRONG for pipeline — GPUOffScreen hides its texture from you
offscreen = gpu.types.GPUOffScreen(w, h)  # can't access internal texture
```

**6. Image appears upside down — flip Y in the vertex shader**
```glsl
/* If your image renders flipped, use this in fullscreen_quad.vert: */
v_uv = vec2(position.x * 0.5 + 0.5, 1.0 - (position.y * 0.5 + 0.5));
```

**7. Shader uniform types must match exactly — mismatch fails silently**
```python
# uniform vec3 u_lift needs exactly 3 floats
shader.uniform_float("u_lift", [r, g, b])       # CORRECT
shader.uniform_float("u_lift", [r, g, b, 1.0])  # WRONG — silent failure
```

**8. Always use GPUFrameBuffer as a context manager**
```python
# CORRECT
with fb.bind():
    shader.bind()
    batch.draw(shader)

# WRONG — manual bind/unbind leaks framebuffer state
fb.bind()
batch.draw(shader)
fb.unbind()
```

**9. Shader cache must be per-window, not global**
```python
# GPU resources are tied to the GL context of the window they were created in.
# Key your cache by window: _cache[(window_id, shader_name)]
# A global shader dict will crash on second window open.
```

### Blender API

**10. Node properties must use annotation syntax (colon, not equals)**
```python
# CORRECT — annotation syntax
class GradeNode(OpenCompNode):
    lift: bpy.props.FloatVectorProperty(name="Lift", default=(0,0,0), size=3)

# WRONG — assignment syntax, silently does nothing in Blender 5.x
class GradeNode(OpenCompNode):
    lift = bpy.props.FloatVectorProperty(name="Lift", default=(0,0,0), size=3)
```

**11. ImageSocket.get_texture() must be implemented by you**
```python
# The socket must store and return the upstream node's output texture
class ImageSocket(bpy.types.NodeSocket):
    def get_texture(self):
        if self.is_output:
            return self.node._output_texture
        if self.is_linked:
            return self.links[0].from_socket.get_texture()
        return None
```

**12. Node.update() fires constantly — do not evaluate there**
```python
# update() fires on every graph edit — use only to mark dirty
def update(self):
    self._dirty = True   # CORRECT — just flag

# WRONG — heavy evaluation in update() makes UI lag badly
def update(self):
    self.evaluate(texture_pool)  # never do this
```

**13. App template __init__.py runs before the add-on registers**
```python
# Anything that needs OpenCompNodeTree to exist must go in load_post handler
@bpy.app.handlers.persistent
def on_load_post(scene):
    setup_workspace()   # safe here — add-on is registered by now

bpy.app.handlers.load_post.append(on_load_post)
```

**14. Always wrap unregister_class in try/except**
```python
# RuntimeError if class not registered — always guard it
try:
    bpy.utils.unregister_class(GradeNode)
except RuntimeError:
    pass
bpy.utils.register_class(GradeNode)
```

### OIIO

**15. Always close ImageInput explicitly**
```python
inp = oiio.ImageInput.open(path)
pixels = inp.read_image(oiio.FLOAT)
inp.close()   # REQUIRED — skipping this holds file locks
```

**16. read_image() returns flat array — always reshape**
```python
pixels = inp.read_image(oiio.FLOAT)
pixels = pixels.reshape(spec.height, spec.width, spec.nchannels)
# height BEFORE width — numpy convention, not width x height
```

**17. Multi-layer EXR channels have layer prefix**
```python
# Channels are named e.g. "diffuse.R", "diffuse.G" not just "R", "G"
# Always inspect: spec.channelnames
# Don't assume RGBA order in multi-layer EXRs
```

### OCIO

**18. OCIO config may be None in --background mode**
```python
# Explicitly load Blender's bundled config in background mode
config_path = REPO_ROOT / "blender" / "5.0" / "datafiles" / "colormanagement" / "config.ocio"
config = ocio.Config.CreateFromFile(str(config_path))
ocio.SetCurrentConfig(config)
```

**19. OCIO GPU shader extraction must happen on the main thread**
```python
# Never call extractGpuShaderInfo() from a background thread or timer.
# Do it during add-on registration or inside a draw handler.
```

### Testing

**20. --background mode has no GPU context on headless Linux**
```python
# GPU tests (GPUTexture creation, shader compilation) may fail on
# headless servers without a display (e.g. CI without Xvfb).
# Guard GPU tests:
import bpy
if not bpy.app.background:
    test("GPU texture creation", check_gpu_texture)
else:
    print("  (skipped — background mode, no GPU context)")
# On a local machine with a display this is not an issue.
```

---

## Rules For This Project

1. **KISS always** — simpler is always better
2. **No premature abstraction** — build what is needed now
3. **Follow CONVENTIONS.md exactly** — naming, structure, patterns
4. **One .frag file per node** — no shader logic in Python
5. **Never clamp in pipeline** — only at display
6. **Always use texture pool** — never allocate GPUTexture directly in nodes
7. **Return None gracefully** — never let a node crash the graph
8. **No features outside the MVP plan** — see ROADMAP.md
9. **All tests must pass before moving to the next phase**
10. **Always use repo-local Blender** — never assume system install

---

## Session Rules — Unassisted Run

- Do not stop to ask questions
- Do not ask for confirmation before creating files
- On ambiguity: make the simplest reasonable choice, comment it
- On failure: debug and fix yourself, do not stop
- Do not move to next phase until ALL tests pass (exit code 0)
- On genuine hard blocker: write to BLOCKERS.md, continue with rest
- Tick checkboxes in ROADMAP.md as items complete
- Commit after each phase: `git commit -m "Phase N complete — all tests passing"`

## Process Per Phase

1. Build the code
2. Write the tests in tests/test_phaseN.py
3. Run: `./blender/blender --background --python tests/run_tests.py`
4. Fix failures, re-run until exit code 0
5. Tick ROADMAP.md checkboxes
6. `git commit -m "Phase N complete — all tests passing"`
7. Move to next phase immediately

## Current Session Target

Complete Phases 0, 1, and 2 with all tests passing. Do not stop until done.
