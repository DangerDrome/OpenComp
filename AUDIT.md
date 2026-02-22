# OpenComp — Audit Prompt

Drop this into a Claude Code session to run a full project audit.
Can be re-run at any point in the project lifecycle.
Update the SCOPE section to focus on specific areas if needed.

---

Read CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md, and ROADMAP.md before starting.

Run a full audit of the OpenComp codebase. Do not fix anything during the audit.
Document everything you find in AUDIT_REPORT.md at the repo root.
When the audit is complete, produce a prioritised fix list.

---

## AUDIT SCOPE

Run all of the following checks. Do not skip any section.

---

### 1. STATIC ANALYSIS

Install and run ruff against all Python files:
```
./blender/blender --background --python -c "
import subprocess, sys
subprocess.run([sys.executable, '-m', 'pip', 'install', 'ruff', '--break-system-packages'])
"
./blender/blender/5.0/python/bin/python3.11 -m ruff check opencomp_core/ --output-format=text
```

Check for:
- Unused imports
- Undefined names
- Style violations (E, W, F codes)
- Complexity issues (C codes)
- Any ruff rule violations

Also run manually check for:
- Functions longer than 50 lines (split candidates)
- Classes longer than 200 lines (refactor candidates)
- Any `print()` statements missing the [OpenComp] prefix
- Any `except:` bare except clauses (should be `except Exception as e:`)
- Any hardcoded paths (should use pathlib.Path and REPO_ROOT)
- Any direct GPUTexture allocation outside texture_pool.get()
- Any `import os` (banned per CONVENTIONS.md — use pathlib only)
- Any clamping of intermediate pipeline values (banned — only clamp at display)

---

### 2. GLSL SHADER AUDIT

For every .frag file in opencomp_core/shaders/:
- Confirm it has the OpenComp header comment block (name, description, inputs, outputs)
- Confirm all uniforms are prefixed with u_
- Confirm in variable is v_uv
- Confirm out variable is named out_color
- Confirm no clamping of intermediate values (clamp() only allowed in ocio_display.frag)
- Confirm alpha is preserved: out_color = vec4(processed_rgb, src.a)
- Confirm safe division: no division without max(denom, 0.0001) guard
- Confirm safe pow: no pow() of negative values without max(x, 0.0) guard
- Check for any texture() calls outside 0-1 UV range without wrapping mode set
- Confirm fullscreen_quad.vert has not been modified (it's shared and must not change)
- Check for Y-flip issues (v_uv should map correctly — flag if manual flip present)

List every shader with any violation found.

---

### 3. CONVENTIONS COMPLIANCE

Check every Python node file in opencomp_core/nodes/ against CONVENTIONS.md:

For each node class:
- bl_idname starts with OC_N_
- bl_label is human readable
- All bpy.props use annotation syntax (colon not equals)
- init() calls self.inputs.new() and self.outputs.new() with OC_NS_ socket types
- evaluate() method exists and returns GPUTexture or None
- evaluate() has try/except that returns None on failure
- evaluate() uses texture_pool.get() not direct GPUTexture allocation
- evaluate() logs errors with [OpenComp] prefix
- Docstring present describing inputs, outputs, shader file

For each socket class:
- bl_idname starts with OC_NS_
- get_texture() implemented on ImageSocket

For all operators:
- bl_idname starts with OC_OT_
- bl_label present

For all panels:
- bl_idname starts with OC_PT_
- bl_space_type and bl_region_type set correctly

---

### 4. TEST COVERAGE AUDIT

Run the full test suite and confirm baseline:
```
./blender/blender --background --python tests/run_tests.py
```

Then audit the tests themselves:
- Count total tests per phase
- Identify any phase with fewer than 8 tests (likely undertested)
- Check if every node class has at least one test
- Check if every shader file has at least one compilation test
- Check if evaluator edge cases are covered:
  - Empty graph
  - Single node graph
  - Disconnected nodes
  - Cycle detection
  - None propagation through chain
- Check if OIIO read handles these cases:
  - Missing file
  - Corrupt file
  - RGB (no alpha)
  - RGBA
  - Multi-layer EXR
  - Single channel (luma)
- Check if conform tool tests cover:
  - Empty EDL
  - EDL with no matched media
  - Handles exceeding source range
  - Duplicate shot names

List every gap found.

---

### 5. GPU RESOURCE MANAGEMENT AUDIT

Check for resource leaks:
- Every GPUTexture created via texture_pool.get() — is it released via texture_pool.release()?
- Every gpu draw handler registered via draw_handler_add() — is there a corresponding draw_handler_remove() on unregister?
- Every GPUFrameBuffer — is it used as a context manager (with fb.bind():)?
- Any GPUTexture allocated directly (not via pool) — flag every instance
- Shader cache — confirm it's keyed per-window not globally
- Check ViewerNode unregister path — confirm draw handler is cleaned up

---

### 6. INSTALL AND SETUP AUDIT

Check install.py:
- Does it correctly find the bundled Blender version directory?
- Does it create scripts/addons/ if it doesn't exist?
- Does it create scripts/startup/bl_app_templates_system/ if it doesn't exist?
- Does it handle the case where the symlink already exists?
- Does it work on Linux, macOS, and Windows (check platform-specific paths)?
- Does it print clear success/failure messages?

Check the app template:
- Does --app-template OpenComp launch without errors?
- Does the topbar show OpenComp menus not Blender menus?
- Are all default Blender panels hidden?
- Is the node editor the only visible editor?
- Does it survive file open/save without reverting to Blender UI?

---

### 7. CONFORM TOOL AUDIT

Check ingest.py:
- Does it handle EDL files with Windows line endings (CRLF)?
- Does it handle EDL files with no reel name?
- Does it handle drop-frame timecodes correctly?
- Does it fail gracefully on malformed EDL?

Check matcher.py:
- Does it handle directories that don't exist?
- Does it handle directories with no matching media?
- Is the match priority order correct: reel name → timecode → filename?

Check nk_export.py:
- Are the generated .nk files syntactically valid Nuke format?
- Are frame padding patterns correct (%04d)?
- Are Read node paths absolute not relative?
- Is the xpos/ypos auto-layout producing non-overlapping graphs?
- Does it handle shot names with spaces or special characters?

Check vse_bridge.py:
- Is timecode placement frame-accurate?
- Are handles set as frame_offset_start/frame_offset_end?

---

### 8. ARCHITECTURE AUDIT

Node graph evaluator:
- Is Kahn's topological sort implemented correctly?
- Does dirty propagation mark all downstream nodes correctly?
- Does evaluate_safe() genuinely prevent crashes from propagating?
- Is there a maximum graph depth limit? (stack overflow risk on very deep graphs)

GPU pipeline:
- Is the ping-pong framebuffer correctly alternating read/write targets?
- Is the texture pool bounded? (unbounded pool = memory leak on large projects)
- Does the executor handle mismatched texture sizes between nodes?
- Is there a fallback if shader compilation fails at runtime?

OCIO integration:
- Is the OCIO config loaded correctly in both GUI and background mode?
- Is the display GLSL re-extracted when the display transform changes?
- Is the OCIO processor cached or recreated on every frame?

---

### 9. SECURITY AUDIT

Check for:
- Any eval() or exec() calls
- Any subprocess calls (banned except in install.py and tests)
- Any network calls in the compositor pipeline
- Any file writes outside designated output directories
- Any use of pickle or yaml.load() (unsafe deserialization)
- The OpenClaw validator — does it actually block all dangerous patterns?
  Test: import os, import subprocess, bpy.ops.wm, open('/etc/passwd')

---

### 10. DOCUMENTATION AUDIT

Check:
- Every public function has a docstring
- Every node class docstring lists: inputs, outputs, shader file
- README.md setup instructions are accurate and complete
- CONVENTIONS.md matches actual code patterns used
- ROADMAP.md checkboxes are up to date
- Any TODO or FIXME comments in the code — list them all

---

## OUTPUT FORMAT

Write findings to AUDIT_REPORT.md with this structure:

```
# OpenComp Audit Report
Date: [date]
Commit: [current git hash]
Tests: [N/N passing]

## Summary
[2-3 sentence overall health assessment]

## Critical Issues (fix immediately)
[anything that causes crashes, data loss, or security issues]

## High Priority (fix before v1.0)
[correctness issues, resource leaks, missing error handling]

## Medium Priority (fix before wider release)
[conventions violations, test gaps, documentation gaps]

## Low Priority (nice to have)
[style issues, minor improvements]

## Metrics
- Total Python files: N
- Total GLSL shaders: N
- Total test count: N
- Ruff violations: N
- Nodes without tests: [list]
- Shaders with violations: [list]
- Resource leak risks: [list]

## Fix Priority List
[Ordered list of specific things to fix, most critical first]
```

Do not fix anything during the audit.
Complete all 10 sections before writing the report.
Be specific — every finding should reference the exact file and line number.
