# OpenComp Roadmap

Check items as complete. Claude Code updates this file as phases complete.

---

## MVP Target — 4 Weeks

A working GPU node compositor inside Blender that looks like its own product,
loads EXRs, grades and composites them, writes output, includes a conform tool
that ingests EDLs and exports .nk files, and has OpenClaw wired in for live
node generation.

---

## Phase 0 — Repo Setup
**Target: Day 1, ~2 hours**
**Test: `./blender/blender --background --python tests/run_tests.py`**

- [x] .gitignore correct (blender/, __pycache__, *.blend1, *.blend2, *.tx, .DS_Store, venv/)
- [x] LICENSE — GPL 3.0
- [x] README.md — setup instructions including blender download step
- [x] install.py — installs add-on + app template into ./blender/
- [x] Full folder structure with __init__.py stubs in every module
- [x] `./blender/blender --app-template OpenComp` launches without Python errors
- [x] All Phase 0 tests pass

**Milestone: Blender launches as OpenComp with no errors.**

---

## Phase 1 — Prove the Architecture
**Target: Day 1, ~4 hours**
**Make-or-break milestone. Everything else iterates on this.**

- [x] app_template/__init__.py
  - [x] Overrides TOPBAR_HT_upper_bar draw (no Blender menus)
  - [x] Hides N-panel, T-panel, header in Node Editor
  - [x] Generates startup.blend programmatically (single Node Editor, maximized)
- [x] Dark theme applied
- [x] splash.png placeholder in place
- [x] shaders/fullscreen_quad.vert written
- [x] shaders/passthrough.frag written
- [x] GPUTexture (RGBA32F) created from numpy test pattern
- [x] gpu draw handler renders texture fullscreen to 3D viewport
- [x] expose_bundled_modules() confirmed — OCIO + OIIO + numpy import cleanly
- [x] All Phase 1 tests pass

**Milestone: Launch OpenComp, see a test pattern on screen. Does not look like Blender.**

---

## Phase 2 — Custom Node Graph
**Target: Day 2, ~4 hours**

- [x] node_graph/sockets.py — ImageSocket, FloatSocket, VectorSocket
- [x] node_graph/tree.py — OpenCompNodeTree (OC_NT_compositor) registered
- [x] node_graph/tree.py — appears in Node Editor dropdown
- [x] nodes/base.py — OpenCompNode base class with evaluate()
- [x] node_graph/evaluator.py — topological sort (Kahn's)
- [x] node_graph/evaluator.py — dirty flag propagation
- [x] node_graph/evaluator.py — cycle detection (raises cleanly)
- [x] Two test nodes connect and evaluate without crash
- [x] All Phase 2 tests pass

**Milestone: Custom OpenComp node graph exists and evaluates correctly.**

---

## Phase 3 — First Real Pipeline
**Target: Day 2–3, ~4 hours**

- [x] gpu_pipeline/texture_pool.py — get() / release()
- [x] gpu_pipeline/framebuffer.py — ping-pong system
- [x] gpu_pipeline/executor.py — evaluate_shader() with shader cache
- [x] nodes/io/read.py — OIIO EXR → RGBA32F GPUTexture
- [x] nodes/viewer/viewer.py — GPUTexture → viewport
- [x] OCIO display GLSL extracted and injected into display shader
- [x] Read → Viewer wired, EXR visible, correct colour management
- [x] All Phase 3 tests pass

**Milestone: Load an EXR, see it correctly colour-managed in viewer.**

---

## Phase 4 — Core Node Library
**Target: Week 2**

- [x] nodes/color/grade.py + shaders/grade.frag
- [x] nodes/color/cdl.py + shaders/cdl.frag
- [x] nodes/merge/over.py + shaders/over.frag
- [x] nodes/merge/merge.py + shaders/merge.frag
- [x] nodes/filter/blur.py + shaders/blur_h.frag + shaders/blur_v.frag
- [x] nodes/filter/sharpen.py + shaders/sharpen.frag
- [x] nodes/transform/transform.py + shaders/transform.frag
- [x] nodes/transform/crop.py + shaders/crop.frag
- [x] nodes/io/write.py — OIIO EXR/DPX/TIFF write
- [x] nodes/color/constant.py + shaders/constant.frag
- [x] nodes/merge/shuffle.py + shaders/shuffle.frag
- [x] Texture pool verified across all nodes
- [x] Shader cache verified (no recompile every evaluate)
- [x] All Phase 4 tests pass

**Milestone: Grade a plate, comp over background, write EXR to disk.**

---

## Phase 5 — Viewer Polish
**Target: Week 2**

- [x] Viewer sidebar — exposure, gamma, channel isolation, false colour, clipping
- [x] Zoom + pan
- [x] Ctrl+1…5 hotkeys — route nodes to viewer
- [x] ROI box
- [x] Graceful handling of missing input / bad file
- [x] All Phase 5 tests pass

**Milestone: A VFX artist can use the viewer comfortably.**

---

## Phase 6 — Conform Tool
**Target: Week 3**

- [x] pip install: opentimelineio, pycmx, pyaaf2, timecode into ./blender/ Python
- [x] conform/ingest.py — EDL/AAF/XML → OTIO
- [x] conform/matcher.py — media match
- [x] conform/handles.py — handle calculation
- [x] conform/structure.py — token folder hierarchy
- [x] conform/nk_export.py — .nk string templating
- [x] conform/vse_bridge.py — OTIO → VSE strips
- [x] Conform workspace UI (shot list + VSE + buttons)
- [x] All Phase 6 tests pass

**Milestone: Ingest EDL, get shot folders + Nuke scripts out.**

---

## Phase 7 — OpenClaw Integration
**Target: Week 4**

- [ ] openclaw_integration/agent_server.py — WebSocket to OpenClaw VPS
- [ ] openclaw_integration/node_builder.py — sandboxed write API
- [ ] openclaw_integration/validator.py — static analysis pre-reload
- [ ] openclaw_integration/hot_reload.py — importlib.reload + registry refresh
- [ ] memory/codebase.md, memory/conventions.md, memory/node_registry.json
- [ ] End-to-end: agent builds Saturation node in < 60 seconds
- [ ] All Phase 7 tests pass

**Milestone: Agent writes a working node. Appears in graph without restart.**

---

## Post-MVP

| Phase | Contents |
|-------|----------|
| 8 | 3D compositing — scanline render, Card3D, Camera node |
| 9 | OFX plugin hosting (first C++ compilation in project) |
| 10 | Advanced nodes — keyer, OIDN denoise, optical flow, lens distortion |
| 11 | Pipeline integration — AYON, ShotGrid, Kitsu, render farm |
| 12 | Marketplace — premium nodes, OpenClaw Studio tier, support SLAs |

---

## Version Tags

| Version | Trigger |
|---------|---------|
| v0.1.0 | Phase 3 complete |
| v0.2.0 | Phase 4 complete |
| v0.3.0 | Phase 5 complete |
| v0.4.0 | Phase 6 complete |
| v0.5.0 | Phase 7 complete |
| v1.0.0 | Production ready |
