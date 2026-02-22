# OpenComp Architecture

## What is OpenComp

OpenComp is an open source, Nuke-like VFX compositor built as a Blender add-on.
Blender is used purely as an infrastructure layer — GPU context, color management,
file I/O, windowing, timeline — while the compositor node graph and GPU image
processing pipeline are entirely custom.

No source compilation. Python + GLSL only. GPL 3.0.

---

## The Core Insight

Three approaches exist for building a compositor on Blender:

1. **Extend Blender's compositor** — hits architectural walls. No custom GPU nodes
   from Python, no per-node caching, wrong multi-channel data model.

2. **Build from scratch** — drowns in scope. Natron tried this and died.

3. **Blender as infrastructure, custom pipeline on top** ← this is OpenComp.

Path 3 is viable now because of Blender 4.4+ `expose_bundled_modules()` giving
direct Python access to OCIO, OIIO, and numpy without compilation.

---

## Full Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         OPENCOMP                                │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CONFORM    │    │   COMPOSITOR     │    │  OPENCLAW AI    │
│    TOOL      │    │   (core product) │    │  INTEGRATION    │
│              │    │                  │    │                 │
│ OTIO ingest  │    │ Custom NodeTree  │    │ Agent server    │
│ EDL/AAF/XML  │    │ GPU shader pipe  │    │ Node builder    │
│ Media match  │    │ RGBA32F textures │    │ Shader builder  │
│ Handle mgmt  │    │ Ping-pong FBOs   │    │ Hot reload      │
│ Shot struct  │    │ Viewer routing   │    │ Sandboxed       │
│ .nk export   │    │ OCIO display     │    │ Persistent mem  │
│ VSE timeline │    │                  │    │                 │
└──────────────┘    └──────────────────┘    └─────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        UI LAYER                                 │
│  App Template — custom theme + keymaps + generated startup      │
│  Python overrides — headers, menus, panels, regions hidden      │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OPENCOMP NODE LIBRARY                        │
│  io/        Read (OIIO)  Write (OIIO)                          │
│  color/     Grade  CDL                                         │
│  merge/     Over  Merge                                        │
│  filter/    Blur  Sharpen                                      │
│  transform/ Transform  Crop                                    │
│  viewer/    Viewer → GPU draw handler → 3D viewport            │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GLSL SHADER BANK                           │
│  fullscreen_quad.vert  (shared vertex shader)                  │
│  passthrough.frag  grade.frag  over.frag  blur_h/v.frag        │
│  ocio_display.frag  — OCIO GLSL injected at runtime            │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BLENDER 5.x (INFRASTRUCTURE)                  │
│  GPU context   — OpenGL / Vulkan / Metal (cross-platform)       │
│  OCIO 2.5      — via expose_bundled_modules()                   │
│  OIIO 3.1      — via expose_bundled_modules()                   │
│  numpy         — always available                               │
│  VSE           — conform timeline backbone                      │
│  CompositorNodeTree — reusable standalone (5.0+)               │
│  GHOST         — cross-platform windowing                       │
└─────────────────────────────────────────────────────────────────┘
                              ▼
                    ./blender/blender  (repo-local binary)
```

---

## GPU Execution Model

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

- Ping-pong framebuffers between nodes
- Texture pool reuses RGBA32F allocations (no GPU alloc thrash)
- Shader cache: compile once per session, reuse every evaluate

---

## Key Technical Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Blender version | 5.0 stable | expose_bundled_modules stable, reusable NodeTree |
| Blender location | ./blender/ inside repo | Known path, no system dependency |
| Node graph | Custom bpy.types.NodeTree subclass | Full control, free Blender node editor UI |
| GPU pipeline | Fragment shaders via gpu module | Compute shaders not exposed to Python |
| Color mgmt | PyOpenColorIO via expose_bundled_modules | OCIO 2.5, GPU GLSL generation |
| File I/O | OpenImageIO via expose_bundled_modules | EXR multi-layer, DPX, all VFX formats |
| EDL parsing | OpenTimelineIO + pycmx | ASWF-backed, production proven |
| Compilation | None for MVP | Pure Python + GLSL |
| License | GPL 3.0 | Matches Blender, marketplace model compatible |

---

## What Blender Provides (Never Rebuild These)

- OpenColorIO 2.5 color management
- OpenImageIO 3.1 file I/O (EXR, DPX, TIFF, PNG, Cineon)
- Multi-layer EXR with Cryptomatte and AOVs
- GPU context management (OpenGL/Vulkan/Metal)
- Timeline, frame ranges, audio sync
- Python scripting environment + numpy
- Cross-platform windowing (GHOST)

---

## Node Graph Architecture

Reference: Sverchok (github.com/nortikin/sverchok) — study tree.py and evaluator.py.

Evaluation flow:
1. Mark all downstream nodes dirty when any input changes
2. Topological sort via Kahn's algorithm
3. Walk sorted list — skip clean nodes, evaluate dirty ones
4. Each node: bind input textures → dispatch frag shader → cache output texture

---

## Conform Tool

Reference: OTIO examples/conform.py as starting point (copy and adapt).
.nk exporter is pure string templating — Nuke's format is plain text key-value blocks.
No Nuke installation or dependency required to generate .nk files.

---

## OpenClaw Integration

OpenClaw VPS connects via WebSocket. Agent sandboxed — can only write to:
- `opencomp_core/nodes/`
- `opencomp_core/shaders/`

Validator runs before any hot-reload.
Banned in agent code: `import os`, `subprocess`, `bpy.ops.wm`.
Hot reload: `importlib.reload(module)` then `node_registry.refresh()`

---

## UI Customization Strategy (No Fork)

1. `blender --app-template OpenComp` on launch
2. `__init__.py` overrides header draw functions
3. Non-compositor regions hidden via `show_region_* = False`
4. Custom dark theme + Nuke-ish keymaps in userpref.blend
5. startup.blend generated programmatically on first run

Hard limits without forking (deferred post-MVP):
- Window title always shows Blender version
- Cannot create new editor types from Python
- Widget shapes hardcoded in C

---

## Blender Version Compatibility

```
opencomp_core/compat/
├── __init__.py    # BLENDER_VERSION tuple, imports correct shim
├── blender_5x.py  # 5.0 APIs
└── blender_51.py  # 5.1 additions (March 2026 release)
```

---

## Reference Codebases

| Project | URL | Purpose |
|---------|-----|---------|
| Sverchok | github.com/nortikin/sverchok | Node tree + evaluator patterns |
| Cascade | github.com/ttddee/Cascade | GLSL compositor shaders (archived goldmine) |
| BQT | github.com/techartorg/bqt | Qt + Blender coexistence (post-MVP) |
| Natron | github.com/NatronGitHub/Natron | .nk format reference |
| Gaffer | github.com/GafferHQ/gaffer | Production node framework patterns |
| OpenMfx | github.com/eliemichel/OpenMfx | OFX in Blender (Phase 2) |
| openfx-misc | github.com/NatronGitHub/openfx-misc | Free OFX plugins (Phase 2) |

---

## Not Building in MVP

- OFX plugin hosting (Phase 2)
- 3D compositing / scanline render (Phase 2)
- Camera tracking (Phase 2)
- Deep compositing (Phase 3)
- Qt UI shell (post-MVP if needed)
- Keyer / OIDN denoise (stretch goals)
- Marketplace (much later)
