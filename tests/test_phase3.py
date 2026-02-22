"""
Phase 3 tests — First real pipeline: GPU pipeline, Read node, Viewer, OCIO.
Must be run inside Blender: ./blender/blender --background --python tests/run_tests.py
All tests must pass before Phase 4 begins.
"""

import pathlib
import sys
import os
import tempfile

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def run(test):

    def check_texture_pool_module():
        from opencomp_core.gpu_pipeline.texture_pool import TexturePool
        pool = TexturePool()
        assert hasattr(pool, 'get'), "TexturePool missing get()"
        assert hasattr(pool, 'release'), "TexturePool missing release()"
        assert hasattr(pool, 'clear'), "TexturePool missing clear()"

    def check_framebuffer_module():
        from opencomp_core.gpu_pipeline.framebuffer import PingPongBuffer
        assert hasattr(PingPongBuffer, 'swap'), "PingPongBuffer missing swap()"
        assert hasattr(PingPongBuffer, 'release'), "PingPongBuffer missing release()"
        # Verify source/target are properties
        assert isinstance(
            PingPongBuffer.source, property
        ), "PingPongBuffer.source should be a property"
        assert isinstance(
            PingPongBuffer.target, property
        ), "PingPongBuffer.target should be a property"

    def check_executor_module():
        from opencomp_core.gpu_pipeline.executor import (
            evaluate_shader, get_shader_source, SHADER_DIR,
        )
        assert callable(evaluate_shader), "evaluate_shader not callable"
        assert callable(get_shader_source), "get_shader_source not callable"
        assert SHADER_DIR.is_dir(), f"SHADER_DIR not found: {SHADER_DIR}"

    def check_shader_source_loading():
        from opencomp_core.gpu_pipeline.executor import get_shader_source
        vert, frag = get_shader_source("passthrough.frag")
        assert "gl_Position" in vert, "Vertex shader missing gl_Position"
        assert "u_image" in frag, "Passthrough frag missing u_image"
        assert "out_color" in frag, "Passthrough frag missing out_color"

    def check_oiio_roundtrip():
        """Write a test EXR with OIIO, read it back, verify pixels match."""
        import bpy
        bpy.utils.expose_bundled_modules()
        import OpenImageIO as oiio
        import numpy as np

        width, height = 8, 8
        # Deterministic test pattern
        pixels = np.zeros((height, width, 4), dtype=np.float32)
        pixels[:, :, 0] = 0.25   # R
        pixels[:, :, 1] = 0.50   # G
        pixels[:, :, 2] = 0.75   # B
        pixels[:, :, 3] = 1.00   # A

        tmp = tempfile.mktemp(suffix=".exr")
        try:
            # Write
            out = oiio.ImageOutput.create(tmp)
            spec = oiio.ImageSpec(width, height, 4, oiio.FLOAT)
            out.open(tmp, spec)
            out.write_image(pixels)
            out.close()

            # Read back
            inp = oiio.ImageInput.open(tmp)
            rspec = inp.spec()
            rpixels = inp.read_image(oiio.FLOAT)
            rpixels = rpixels.reshape(rspec.height, rspec.width, rspec.nchannels)
            inp.close()

            assert rspec.width == width, f"Width mismatch: {rspec.width} != {width}"
            assert rspec.height == height, f"Height mismatch: {rspec.height} != {height}"
            assert np.allclose(pixels, rpixels, atol=1e-5), "Pixel data mismatch"
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def check_read_node():
        from opencomp_core.nodes.io.read import ReadNode
        assert ReadNode.bl_idname == "OC_N_read", \
            f"ReadNode bl_idname wrong: {ReadNode.bl_idname}"
        assert hasattr(ReadNode, 'evaluate'), "ReadNode missing evaluate()"
        # Verify filepath property annotation exists
        annotations = getattr(ReadNode, '__annotations__', {})
        assert 'filepath' in annotations, "ReadNode missing filepath property"

    def check_viewer_node():
        from opencomp_core.nodes.viewer.viewer import ViewerNode
        assert ViewerNode.bl_idname == "OC_N_viewer", \
            f"ViewerNode bl_idname wrong: {ViewerNode.bl_idname}"
        assert hasattr(ViewerNode, 'evaluate'), "ViewerNode missing evaluate()"

    def check_ocio_config_loads():
        """Verify OCIO config can be loaded from the bundled Blender files."""
        import bpy
        bpy.utils.expose_bundled_modules()
        import PyOpenColorIO as ocio

        # Try current config first
        config = ocio.GetCurrentConfig()
        if config is None:
            # Fallback to bundled config file
            config_path = (
                REPO_ROOT / "blender" / "5.0" / "datafiles"
                / "colormanagement" / "config.ocio"
            )
            assert config_path.exists(), f"OCIO config not found: {config_path}"
            config = ocio.Config.CreateFromFile(str(config_path))

        assert config is not None, "OCIO config is None"
        # Verify scene_linear role exists
        role = config.getColorSpace(ocio.ROLE_SCENE_LINEAR)
        assert role is not None, "OCIO scene_linear role not found"

    def check_ocio_glsl_extraction():
        """Verify OCIO display GLSL can be extracted."""
        from opencomp_core.nodes.viewer.viewer import extract_ocio_display_glsl
        glsl = extract_ocio_display_glsl()
        # May be None in some environments, but if it returns text verify it
        if glsl is not None:
            assert len(glsl) > 0, "OCIO GLSL text is empty"
            assert "vec4" in glsl or "float" in glsl, \
                "OCIO GLSL doesn't look like valid shader code"

    def check_viewer_draw_handler_api():
        """Verify the viewer module has draw handler registration code."""
        from opencomp_core.nodes.viewer import viewer
        assert hasattr(viewer, 'register'), "viewer module missing register()"
        assert hasattr(viewer, 'unregister'), "viewer module missing unregister()"
        assert hasattr(viewer, '_draw_viewer_callback'), \
            "viewer module missing _draw_viewer_callback"

    test("TexturePool module correct",          check_texture_pool_module)
    test("PingPongBuffer module correct",       check_framebuffer_module)
    test("Executor module correct",             check_executor_module)
    test("Shader source loading works",         check_shader_source_loading)
    test("OIIO write/read roundtrip",           check_oiio_roundtrip)
    test("ReadNode class correct",              check_read_node)
    test("ViewerNode class correct",            check_viewer_node)
    test("OCIO config loads",                   check_ocio_config_loads)
    test("OCIO GLSL extraction",                check_ocio_glsl_extraction)
    test("Viewer draw handler API",             check_viewer_draw_handler_api)
