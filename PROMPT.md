# OpenComp — Claude Code Session Prompt

Copy and paste everything below the line into Claude Code to start an unassisted build session.
Update the TARGET section at the bottom before each new session.

---

Read CLAUDE.md, ARCHITECTURE.md, CONVENTIONS.md, and ROADMAP.md in full
before writing a single line of code.

RULES:
- Do not stop to ask questions under any circumstances
- Do not ask for confirmation before creating files
- If you hit an ambiguity, make the simplest reasonable choice
  and document it in a comment
- If something fails, debug and fix it yourself
- Do not move to the next phase until ALL tests pass
- If you hit a genuine hard blocker that cannot be resolved,
  document it in BLOCKERS.md and continue with everything else

PROCESS FOR EACH PHASE:
1. Build the code
2. Write / complete the tests in tests/test_phaseN.py
3. Run: ./blender/blender --background --python tests/run_tests.py
4. Fix anything that fails
5. Re-run until exit code is 0 (all green)
6. Tick checkboxes in ROADMAP.md
7. git commit -m "Phase N complete — all tests passing"
8. Move to next phase without stopping

BLENDER BINARY: ./blender/blender
Blender is bundled inside this repo. Always use this path.
Never assume a system Blender install.

---

KNOWN GOTCHAS — read all of these before writing any code

GPU / SHADER:

1. Draw handler mode must be POST_PIXEL not POST_VIEW
   bpy.types.SpaceView3D.draw_handler_add(
       callback, (self, context), 'WINDOW', 'POST_PIXEL'
   )

2. Compile shaders once at registration — never inside the draw callback.
   Store compiled shaders in a module-level cache dict.
   Recompiling every frame is catastrophically slow.

3. Blender context may not be ready when handler first registers.
   If viewport shows nothing on first launch, delay initial evaluation:
   bpy.app.timers.register(lambda: trigger_redraw(), first_interval=0.1)

4. GPUTexture data must be gpu.types.Buffer — not a list or numpy array.
   flat = pixels.flatten().tolist()
   buf  = gpu.types.Buffer('FLOAT', len(flat), flat)
   tex  = gpu.types.GPUTexture((w, h), format='RGBA32F', data=buf)

5. Use GPUFrameBuffer not GPUOffScreen for the ping-pong pipeline.
   GPUOffScreen hides its internal texture — you can't use it as a node output.
   tex = gpu.types.GPUTexture((w, h), format='RGBA32F')
   fb  = gpu.types.GPUFrameBuffer(color_slots=[tex])

6. Always use GPUFrameBuffer as a context manager — never bind/unbind manually.
   with fb.bind():
       shader.bind()
       batch.draw(shader)

7. If the image appears upside down flip Y in fullscreen_quad.vert:
   v_uv = vec2(position.x * 0.5 + 0.5, 1.0 - (position.y * 0.5 + 0.5));

8. Shader uniform types must match exactly — mismatch fails silently.
   uniform vec3 u_lift needs exactly 3 floats:
   shader.uniform_float("u_lift", [r, g, b])        ← correct
   shader.uniform_float("u_lift", [r, g, b, 1.0])   ← wrong, silent failure

9. Shader cache must be keyed per-window not global.
   GPU resources are tied to the GL context of the window they were created in.
   Use: _cache[(window_id, shader_name)]
   A global shader dict crashes on second window open.

BLENDER API:

10. Node properties MUST use annotation syntax (colon) not assignment (equals).
    lift: bpy.props.FloatVectorProperty(...)   ← correct
    lift = bpy.props.FloatVectorProperty(...)  ← wrong, silently does nothing

11. ImageSocket.get_texture() must be implemented manually.
    The socket must store and return the upstream node's output texture.
    class ImageSocket(bpy.types.NodeSocket):
        def get_texture(self):
            if self.is_output:
                return self.node._output_texture
            if self.is_linked:
                return self.links[0].from_socket.get_texture()
            return None

12. Node.update() fires constantly during graph edits — never evaluate there.
    Use update() only to mark dirty. Heavy work here makes the UI lag badly.

13. App template __init__.py runs before the add-on registers.
    Anything needing OpenCompNodeTree must go in a load_post handler:
    @bpy.app.handlers.persistent
    def on_load_post(scene):
        setup_workspace()
    bpy.app.handlers.load_post.append(on_load_post)

14. Always wrap unregister_class in try/except RuntimeError.
    try:
        bpy.utils.unregister_class(MyClass)
    except RuntimeError:
        pass

OIIO:

15. Always close ImageInput explicitly — skipping holds file locks.
    inp = oiio.ImageInput.open(path)
    pixels = inp.read_image(oiio.FLOAT)
    inp.close()

16. read_image() returns a flat array — always reshape.
    pixels = pixels.reshape(spec.height, spec.width, spec.nchannels)
    Note: height before width (numpy convention).

17. Multi-layer EXR channels have layer prefix in their names.
    Channels are "diffuse.R", "diffuse.G" not just "R", "G".
    Always inspect spec.channelnames before assuming RGBA order.

OCIO:

18. OCIO config may be None in --background mode.
    Explicitly load Blender's bundled config:
    config_path = REPO_ROOT / "blender" / "5.0" / "datafiles" / "colormanagement" / "config.ocio"
    config = ocio.Config.CreateFromFile(str(config_path))
    ocio.SetCurrentConfig(config)
    If the image looks washed out in the viewer, this is why.
    If the image looks too dark, gamma is being double-applied.

19. OCIO GPU shader extraction must happen on the main thread.
    Never call extractGpuShaderInfo() from a background thread or timer.
    Do it during registration or inside a draw handler.

20. expose_bundled_modules() must be called before any OIIO or OCIO import.
    Call it at module load time — not inside functions or class methods.

TESTING:

21. --background mode has no GPU context on headless Linux.
    Guard GPU tests so they skip gracefully rather than error:
    if bpy.app.background:
        print("  (skipped — no GPU context in background mode)")
        return
    On a local machine with a display this is not an issue.

---

TARGET — update this before each session:

The app_template/__init__.py is not fully implemented.
When ./blender/blender --app-template OpenComp is run it still
looks like Blender.

Fix this without touching anything else. Specifically:
- Override TOPBAR_HT_upper_bar to show OpenComp menus not Blender menus
- Hide N-panel, T-panel, header bar in the node editor on startup
- Set workspace to a single maximized Node Editor
- Apply dark theme
- The startup.blend should be generated programmatically on first run

All 83 existing tests must still pass after this fix.
Do not break anything that is already working.