"""
Phase 4 tests — Core Node Library: 11 nodes, 13 shaders, updated executor.
Must be run inside Blender: ./blender/blender --background --python tests/run_tests.py
All tests must pass before Phase 5 begins.
"""

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

SHADER_DIR = REPO_ROOT / "opencomp_core" / "shaders"


def run(test):

    # ── Shader files exist with correct uniforms ──────────────────────────

    def check_all_phase4_shaders_exist():
        expected = [
            "grade.frag", "cdl.frag", "constant.frag",
            "over.frag", "merge.frag", "shuffle.frag",
            "blur_h.frag", "blur_v.frag", "sharpen.frag",
            "transform.frag", "crop.frag",
        ]
        for name in expected:
            path = SHADER_DIR / name
            assert path.exists(), f"Shader missing: {name}"
            src = path.read_text()
            assert len(src) > 20, f"Shader {name} is too short"
            assert "out_color" in src, f"Shader {name} missing out_color output"

    def check_shader_uniforms():
        from opencomp_core.gpu_pipeline.executor import get_shader_source

        checks = {
            "grade.frag":     ["u_lift", "u_gamma", "u_gain", "u_mix"],
            "cdl.frag":       ["u_slope", "u_offset", "u_power", "u_saturation"],
            "constant.frag":  ["u_color"],
            "over.frag":      ["u_image", "u_bg", "u_mix"],
            "merge.frag":     ["u_image", "u_bg", "u_mode", "u_mix"],
            "shuffle.frag":   ["u_r_source", "u_g_source", "u_b_source", "u_a_source"],
            "blur_h.frag":    ["u_radius", "u_resolution"],
            "blur_v.frag":    ["u_radius", "u_resolution"],
            "sharpen.frag":   ["u_amount", "u_resolution"],
            "transform.frag": ["u_translate", "u_rotate", "u_scale", "u_center"],
            "crop.frag":      ["u_crop"],
        }
        for frag, uniforms in checks.items():
            _, frag_src = get_shader_source(frag)
            for u in uniforms:
                assert u in frag_src, \
                    f"Shader {frag} missing uniform '{u}'"

    # ── Node classes exist with correct bl_idname and properties ──────────

    def check_grade_node():
        from opencomp_core.nodes.color.grade import GradeNode
        assert GradeNode.bl_idname == "OC_N_grade"
        assert hasattr(GradeNode, 'evaluate')
        ann = getattr(GradeNode, '__annotations__', {})
        for prop in ('lift', 'gamma', 'gain', 'mix'):
            assert prop in ann, f"GradeNode missing property: {prop}"

    def check_cdl_node():
        from opencomp_core.nodes.color.cdl import CDLNode
        assert CDLNode.bl_idname == "OC_N_cdl"
        assert hasattr(CDLNode, 'evaluate')
        ann = getattr(CDLNode, '__annotations__', {})
        for prop in ('slope', 'offset', 'power', 'saturation'):
            assert prop in ann, f"CDLNode missing property: {prop}"

    def check_constant_node():
        from opencomp_core.nodes.color.constant import ConstantNode
        assert ConstantNode.bl_idname == "OC_N_constant"
        assert hasattr(ConstantNode, 'evaluate')
        ann = getattr(ConstantNode, '__annotations__', {})
        assert 'color' in ann, "ConstantNode missing color property"
        assert 'width_prop' in ann, "ConstantNode missing width_prop"
        assert 'height_prop' in ann, "ConstantNode missing height_prop"

    def check_over_node():
        from opencomp_core.nodes.merge.over import OverNode
        assert OverNode.bl_idname == "OC_N_over"
        assert hasattr(OverNode, 'evaluate')
        ann = getattr(OverNode, '__annotations__', {})
        assert 'mix' in ann, "OverNode missing mix property"

    def check_merge_node():
        from opencomp_core.nodes.merge.merge import MergeNode
        assert MergeNode.bl_idname == "OC_N_merge"
        assert hasattr(MergeNode, 'evaluate')
        ann = getattr(MergeNode, '__annotations__', {})
        assert 'mode' in ann, "MergeNode missing mode property"
        assert 'mix' in ann, "MergeNode missing mix property"

    def check_shuffle_node():
        from opencomp_core.nodes.merge.shuffle import ShuffleNode
        assert ShuffleNode.bl_idname == "OC_N_shuffle"
        assert hasattr(ShuffleNode, 'evaluate')
        ann = getattr(ShuffleNode, '__annotations__', {})
        for prop in ('r_source', 'g_source', 'b_source', 'a_source'):
            assert prop in ann, f"ShuffleNode missing property: {prop}"

    def check_blur_node():
        from opencomp_core.nodes.filter.blur import BlurNode
        assert BlurNode.bl_idname == "OC_N_blur"
        assert hasattr(BlurNode, 'evaluate')
        ann = getattr(BlurNode, '__annotations__', {})
        assert 'size' in ann, "BlurNode missing size property"

    def check_sharpen_node():
        from opencomp_core.nodes.filter.sharpen import SharpenNode
        assert SharpenNode.bl_idname == "OC_N_sharpen"
        assert hasattr(SharpenNode, 'evaluate')
        ann = getattr(SharpenNode, '__annotations__', {})
        assert 'amount' in ann, "SharpenNode missing amount property"

    def check_transform_node():
        from opencomp_core.nodes.transform.transform import TransformNode
        assert TransformNode.bl_idname == "OC_N_transform"
        assert hasattr(TransformNode, 'evaluate')
        ann = getattr(TransformNode, '__annotations__', {})
        for prop in ('translate', 'rotate', 'scale', 'center'):
            assert prop in ann, f"TransformNode missing property: {prop}"

    def check_crop_node():
        from opencomp_core.nodes.transform.crop import CropNode
        assert CropNode.bl_idname == "OC_N_crop"
        assert hasattr(CropNode, 'evaluate')
        ann = getattr(CropNode, '__annotations__', {})
        for prop in ('left', 'right', 'bottom', 'top'):
            assert prop in ann, f"CropNode missing property: {prop}"

    def check_write_node():
        from opencomp_core.nodes.io.write import WriteNode
        assert WriteNode.bl_idname == "OC_N_write"
        assert hasattr(WriteNode, 'evaluate')
        ann = getattr(WriteNode, '__annotations__', {})
        assert 'filepath' in ann, "WriteNode missing filepath property"
        assert 'file_format' in ann, "WriteNode missing file_format property"

    # ── Executor supports extra_textures and output_size ──────────────────

    def check_executor_extended_api():
        import inspect
        from opencomp_core.gpu_pipeline.executor import evaluate_shader
        sig = inspect.signature(evaluate_shader)
        params = list(sig.parameters.keys())
        assert 'extra_textures' in params, \
            "evaluate_shader missing extra_textures parameter"
        assert 'output_size' in params, \
            "evaluate_shader missing output_size parameter"

    # ── Register all tests ────────────────────────────────────────────────

    test("Phase 4 shader files exist",           check_all_phase4_shaders_exist)
    test("Shader uniforms correct",              check_shader_uniforms)
    test("GradeNode class correct",              check_grade_node)
    test("CDLNode class correct",                check_cdl_node)
    test("ConstantNode class correct",           check_constant_node)
    test("OverNode class correct",               check_over_node)
    test("MergeNode class correct",              check_merge_node)
    test("ShuffleNode class correct",            check_shuffle_node)
    test("BlurNode class correct",               check_blur_node)
    test("SharpenNode class correct",            check_sharpen_node)
    test("TransformNode class correct",          check_transform_node)
    test("CropNode class correct",               check_crop_node)
    test("WriteNode class correct",              check_write_node)
    test("Executor extended API",                check_executor_extended_api)
