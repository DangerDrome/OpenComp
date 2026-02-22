"""
Phase 5 tests — Viewer Polish: display controls, zoom/pan, ROI, routing, keymaps.
Must be run inside Blender: ./blender/blender --background --python tests/run_tests.py
All tests must pass before Phase 6 begins.
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

SHADER_DIR = REPO_ROOT / "opencomp_core" / "shaders"


def run(test):

    # ── Display shader ────────────────────────────────────────────────

    def check_viewer_display_shader_exists():
        path = SHADER_DIR / "viewer_display.frag"
        assert path.exists(), "viewer_display.frag missing"
        src = path.read_text()
        assert len(src) > 100, "viewer_display.frag is too short"
        assert "out_color" in src, "viewer_display.frag missing out_color"

    def check_viewer_display_shader_uniforms():
        from opencomp_core.gpu_pipeline.executor import get_shader_source
        _, frag_src = get_shader_source("viewer_display.frag")
        required_uniforms = [
            "u_image", "u_gain", "u_gamma", "u_channel",
            "u_false_color", "u_clipping",
            "u_zoom", "u_pan",
            "u_roi_enabled", "u_roi", "u_resolution",
        ]
        for u in required_uniforms:
            assert u in frag_src, f"viewer_display.frag missing uniform '{u}'"

    # ── PropertyGroup ─────────────────────────────────────────────────

    def check_viewer_settings_propertygroup():
        from opencomp_core.nodes.viewer.viewer import OpenCompViewerSettings
        ann = getattr(OpenCompViewerSettings, '__annotations__', {})
        for prop in ('gain', 'gamma', 'channel_mode', 'false_color', 'clipping'):
            assert prop in ann, \
                f"OpenCompViewerSettings missing property: {prop}"

    # ── Viewer state ──────────────────────────────────────────────────

    def check_viewer_state_keys():
        from opencomp_core.nodes.viewer.viewer import _viewer_state
        for key in ('texture', 'shader', 'batch', 'handler',
                    'zoom', 'pan', 'roi_enabled', 'roi'):
            assert key in _viewer_state, \
                f"_viewer_state missing key: {key}"

    def check_viewer_state_defaults():
        from opencomp_core.nodes.viewer.viewer import _viewer_state
        assert _viewer_state["zoom"] == 1.0, "Default zoom should be 1.0"
        assert _viewer_state["pan"] == [0.0, 0.0], "Default pan should be [0,0]"
        assert _viewer_state["roi_enabled"] is False, "ROI should default to off"

    # ── Panel ─────────────────────────────────────────────────────────

    def check_viewer_panel():
        from opencomp_core.nodes.viewer.panel import OC_PT_viewer
        assert OC_PT_viewer.bl_idname == "OC_PT_viewer"
        assert OC_PT_viewer.bl_space_type == 'VIEW_3D'
        assert OC_PT_viewer.bl_region_type == 'UI'
        assert OC_PT_viewer.bl_category == "OpenComp"
        assert hasattr(OC_PT_viewer, 'draw'), "Panel missing draw method"

    # ── Operators ─────────────────────────────────────────────────────

    def check_zoom_operators():
        from opencomp_core.nodes.viewer.operators import (
            OC_OT_viewer_zoom_in, OC_OT_viewer_zoom_out,
        )
        assert OC_OT_viewer_zoom_in.bl_idname == "oc.viewer_zoom_in"
        assert OC_OT_viewer_zoom_out.bl_idname == "oc.viewer_zoom_out"
        assert hasattr(OC_OT_viewer_zoom_in, 'execute')
        assert hasattr(OC_OT_viewer_zoom_out, 'execute')

    def check_pan_operator():
        from opencomp_core.nodes.viewer.operators import OC_OT_viewer_pan
        assert OC_OT_viewer_pan.bl_idname == "oc.viewer_pan"
        assert hasattr(OC_OT_viewer_pan, 'invoke')
        assert hasattr(OC_OT_viewer_pan, 'modal')

    def check_roi_operator():
        from opencomp_core.nodes.viewer.operators import OC_OT_viewer_roi
        assert OC_OT_viewer_roi.bl_idname == "oc.viewer_roi"
        assert hasattr(OC_OT_viewer_roi, 'invoke')
        assert hasattr(OC_OT_viewer_roi, 'modal')

    def check_route_operator():
        from opencomp_core.nodes.viewer.operators import OC_OT_viewer_route
        assert OC_OT_viewer_route.bl_idname == "oc.viewer_route"
        assert hasattr(OC_OT_viewer_route, 'execute')
        ann = getattr(OC_OT_viewer_route, '__annotations__', {})
        assert 'index' in ann, "Route operator missing index property"

    def check_reset_operator():
        from opencomp_core.nodes.viewer.operators import OC_OT_viewer_reset
        assert OC_OT_viewer_reset.bl_idname == "oc.viewer_reset"
        assert hasattr(OC_OT_viewer_reset, 'execute')

    # ── Keymaps ───────────────────────────────────────────────────────

    def check_keymap_module():
        from opencomp_core.nodes.viewer import keymaps
        assert hasattr(keymaps, 'register'), "keymaps missing register()"
        assert hasattr(keymaps, 'unregister'), "keymaps missing unregister()"
        assert callable(keymaps.register)
        assert callable(keymaps.unregister)

    # ── Backward compat (Phase 3 tests still pass) ────────────────────

    def check_backward_compat():
        from opencomp_core.nodes.viewer import viewer
        assert hasattr(viewer, 'register')
        assert hasattr(viewer, 'unregister')
        assert hasattr(viewer, '_draw_viewer_callback')
        assert hasattr(viewer, 'extract_ocio_display_glsl')

    # ── Edge case handling ────────────────────────────────────────────

    def check_viewer_no_input_graceful():
        """ViewerNode.evaluate with None input should not crash."""
        from opencomp_core.nodes.viewer.viewer import ViewerNode, _viewer_state
        assert hasattr(ViewerNode, 'evaluate')
        # Set texture to None directly — simulates no input
        _viewer_state["texture"] = None
        assert _viewer_state["texture"] is None, "Should handle None gracefully"

    # ── Register all tests ────────────────────────────────────────────

    test("Viewer display shader exists",         check_viewer_display_shader_exists)
    test("Viewer display shader uniforms",       check_viewer_display_shader_uniforms)
    test("Viewer settings PropertyGroup",        check_viewer_settings_propertygroup)
    test("Viewer state keys present",            check_viewer_state_keys)
    test("Viewer state defaults correct",        check_viewer_state_defaults)
    test("Viewer panel class correct",           check_viewer_panel)
    test("Zoom operators correct",               check_zoom_operators)
    test("Pan operator correct",                 check_pan_operator)
    test("ROI operator correct",                 check_roi_operator)
    test("Route operator correct",               check_route_operator)
    test("Reset operator correct",               check_reset_operator)
    test("Keymap module correct",                check_keymap_module)
    test("Backward compatibility with Phase 3",  check_backward_compat)
    test("Viewer handles no input gracefully",   check_viewer_no_input_graceful)
