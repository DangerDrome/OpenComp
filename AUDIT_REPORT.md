# OpenComp Audit Report

**Date:** 2026-02-26
**Commit:** a6582d0
**Tests:** 83 tests across 8 phases (Phase 7 not yet written)

---

## Summary

OpenComp is in a healthy state with Phases 0-6 complete. The codebase follows most conventions correctly. Main issues are:
- 80 ruff violations (mostly unused imports and bare except clauses)
- 3 files using banned `import os` instead of pathlib
- 30 bare `except:` clauses instead of `except Exception as e:`
- node_canvas/operators.py is 1500 lines (needs splitting)
- Shader cache is global instead of per-window (potential multi-window crash)

---

## Critical Issues (fix immediately)

### 1. Shader Cache Not Per-Window
**File:** `opencomp_core/gpu_pipeline/executor.py:16`
**Issue:** `_shader_cache = {}` is a global dict. Per CLAUDE.md gotcha #9, GPU resources are tied to the GL context of the window they were created in. A global shader dict will crash on second window open.
**Fix:** Key cache by window: `_cache[(window_id, shader_name)]`

---

## High Priority (fix before v1.0)

### 1. Banned `import os` Usage (CONVENTIONS.md violation)
Per CONVENTIONS.md, `import os` is banned — use `pathlib.Path` only.

| File | Line |
|------|------|
| `opencomp_core/nodegraph/qt_integration.py` | 11 |
| `opencomp_core/qt_canvas/launch.py` | 13 |
| `opencomp_core/nodes/io/read.py` | 8 |

### 2. Bare `except:` Clauses (30 instances)
All should be `except Exception as e:` per CONVENTIONS.md.

| File | Lines |
|------|-------|
| `nodegraph/qt_integration.py` | 85, 310, 317, 330 |
| `nodegraph/bridge.py` | 116, 313 |
| `ui/headers.py` | 162 |
| `ui/toolbar.py` | 321 |
| `ui/viewer.py` | 875, 879, 917 |
| `node_canvas/toolbar.py` | 97 |
| `node_canvas/operators.py` | 178, 199 |
| `qt_canvas/blender_launch.py` | 129 |
| `qt_canvas/canvas/session.py` | 109, 209 |
| `qt_canvas/ipc/client.py` | 100, 123, 153, 182, 222, 231, 263 |
| `qt_canvas/ipc/server.py` | 54, 61, 96, 133 |

### 3. subprocess in Node Code
**File:** `opencomp_core/nodes/io/read.py:12`
**Issue:** Uses subprocess for ffprobe/ffmpeg. Per CONVENTIONS.md, subprocess is banned except in install.py and tests.
**Note:** This is needed for video file support. Consider documenting this as an approved exception.

### 4. Texture Pool Not Bounded
**File:** `opencomp_core/gpu_pipeline/texture_pool.py`
**Issue:** No maximum pool size. On large projects with many different resolutions, pool could grow unbounded causing memory leaks.
**Fix:** Add `max_pool_size` and eviction strategy.

---

## Medium Priority (fix before wider release)

### 1. Large Files Need Refactoring

| File | Lines | Issue |
|------|-------|-------|
| `node_canvas/operators.py` | 1500 | Very large, split into logical modules |
| `ui/viewer.py` | 918 | Large, consider splitting viewer vs cache |
| `node_canvas/renderer.py` | 899 | Large |
| `nodegraph/bridge.py` | 552 | Large |
| `nodes/io/read.py` | 1058 | Large, handles images + sequences + video |

### 2. Unused Imports (F401 ruff violations)

| File | Import |
|------|--------|
| `conform/__init__.py` | ingest, matcher, handles, structure, nk_export |
| `qt_canvas/ipc/server.py:188` | bpy |
| `qt_canvas/launch.py:23` | QTimer |
| `qt_canvas/ui/properties.py` | QPushButton, QFileDialog, QGroupBox, Qt |
| `qt_canvas/viewer/thumbnail.py:14` | Tuple |
| Multiple files | Various unused imports |

### 3. F403: Import * Used
**File:** `opencomp_core/compat/__init__.py:8,10`
**Issue:** `from .blender_51 import *` and `from .blender_5x import *` make it hard to trace what's imported.
**Fix:** Use explicit imports.

### 4. Test Phase 7 Not Written
**File:** `tests/test_phase7.py`
**Issue:** Contains 0 tests. OpenClaw integration (Phase 7) is not yet complete per ROADMAP.md.

### 5. ingest.py CRLF Handling
**File:** `opencomp_core/conform/ingest.py:50`
**Issue:** `pycmx.parse_cmx3600(open(filepath))` doesn't explicitly handle CRLF line endings.
**Fix:** Open with `newline=''` or normalize line endings before parsing.

### 6. Direct GPUTexture Allocation in Nodes
Per CONVENTIONS.md, nodes should use texture_pool.get() instead of direct GPUTexture allocation. Found in:

| File | Line | Justification |
|------|------|---------------|
| `nodes/io/read.py` | 641 | OIIO pixels to GPU - needs direct allocation |
| `nodes/io/read.py` | 942 | Frame cache upload - needs direct allocation |
| `nodes/viewer/viewer.py` | 212 | Frame cache upload - needs direct allocation |

**Note:** These are legitimate uses for initial GPU upload, not intermediate pipeline textures.

---

## Low Priority (nice to have)

### 1. E402: Module Import Not at Top
**File:** `opencomp_core/__init__.py:27`
**Issue:** `import bpy` not at top due to comments.

### 2. F541: f-string Without Placeholders
**File:** `opencomp_core/qt_canvas/launch.py:119`
**Code:** `print(f"[OpenComp Canvas] Started")` - should be plain string.

### 3. Missing `docs/` Directory Content
**Issue:** `tests/test_phase0.py` expects a `docs/` directory but it may be empty.

### 4. OpenClaw Validator Not Implemented
**File:** `opencomp_core/openclaw_integration/validator.py`
**Issue:** Phase 7 incomplete - validator not yet implemented.

---

## GLSL Shader Audit Results

All 14 fragment shaders pass audit. They all have:
- OpenComp header comment with name, description, inputs, outputs
- All uniforms prefixed with `u_`
- Input variable `v_uv`
- Output variable `out_color`
- Alpha preservation where applicable
- Safe division guards where needed

| Shader | Status | Notes |
|--------|--------|-------|
| fullscreen_quad.vert | PASS | Shared vertex shader, unmodified |
| passthrough.frag | PASS | Identity pass |
| grade.frag | PASS | Safe pow() with max() guard |
| cdl.frag | PASS | Safe pow() with max() guard |
| constant.frag | PASS | No input image (generator) |
| crop.frag | PASS | - |
| over.frag | PASS | - |
| merge.frag | PASS | - |
| shuffle.frag | PASS | - |
| blur_h.frag | PASS | clamp() on radius parameter (acceptable) |
| blur_v.frag | PASS | clamp() on radius parameter (acceptable) |
| sharpen.frag | PASS | - |
| transform.frag | PASS | Safe divide with max() guard |
| roto.frag | PASS | - |
| viewer_display.frag | PASS | clamp() for display only (allowed) |

---

## Test Coverage Audit

| Phase | Test Count | Status |
|-------|------------|--------|
| Phase 0 | 8 | Complete |
| Phase 1 | 10 | Complete |
| Phase 2 | 10 | Complete |
| Phase 3 | 10 | Complete |
| Phase 4 | 14 | Complete |
| Phase 5 | 14 | Complete |
| Phase 6 | 17 | Complete |
| Phase 7 | 0 | **Not written** |

**Total:** 83 tests

### Test Coverage Gaps
- No explicit GPU texture creation tests (GPU tests skipped in background mode)
- No cycle detection stress test (large graphs)
- No multi-window shader cache test
- No memory pressure test for texture pool
- No video file read tests
- No CRLF/Windows line ending EDL tests

---

## GPU Resource Management Audit

### Positive Findings
- `texture_pool.py`: Proper get/release pattern implemented
- `tree.py`: Draw handler properly removed in unregister()
- `framebuffer.py`: PingPongBuffer has release() method
- `viewer.py`: Has proper register/unregister for draw handlers

### Issues Found
- Shader cache is global, not per-window (Critical - see above)
- Texture pool has no maximum size bound
- No explicit GPUTexture cleanup on add-on unregister

---

## Security Audit

| Check | Status | Details |
|-------|--------|---------|
| eval() | PASS | Only Qt `app.exec()` found |
| exec() | PASS | None found |
| subprocess | WARN | Used in read.py (ffmpeg) and blender_launch.py |
| pickle | PASS | None found |
| yaml.load | PASS | None found |
| Network calls | PASS | None in compositor pipeline |
| File writes | PASS | Confined to designated output directories |
| OpenClaw validator | N/A | Not yet implemented (Phase 7 incomplete) |

---

## Install and Setup Audit

### install.py
- Correctly finds bundled Blender version directory
- Creates scripts/addons_core/ if needed
- Creates scripts/startup/bl_app_templates_system/ if needed
- Handles existing symlink/directory (removes and recreates)
- Works on Linux, macOS, Windows (symlink vs copy)
- Prints clear success/failure messages

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Python files | 84 |
| Total GLSL shaders | 15 |
| Total test count | 83 |
| Ruff violations | 80 |
| Bare except clauses | 30 |
| `import os` violations | 3 |
| Lines in largest file | 1500 |

### Nodes Without Dedicated Tests
All node classes have at least one test checking their class structure. Integration tests needed for:
- ReadNode with video files
- ViewerNode frame caching
- BlurNode with extreme radius values

### Shaders With Violations
None - all shaders pass audit.

### Resource Leak Risks
1. Shader cache not per-window
2. Texture pool unbounded
3. No explicit GPU cleanup on unregister

---

## Fix Priority List

### Immediate (do first)
1. Make shader cache per-window in `executor.py`

### High Priority
2. Replace all `import os` with pathlib equivalents
3. Fix all 30 bare `except:` clauses
4. Add bounds to texture pool
5. Document subprocess exception for video support

### Medium Priority
6. Split `node_canvas/operators.py` into smaller modules
7. Fix unused imports (ruff F401)
8. Replace `from .blender_5x import *` with explicit imports
9. Write Phase 7 tests
10. Handle CRLF in EDL ingest

### Low Priority
11. Move `import bpy` to top of `__init__.py`
12. Remove f-prefix from string without placeholders
13. Add integration tests for edge cases

---

*Generated by OpenComp audit process. Do not fix anything during audit - use this report for planning.*
