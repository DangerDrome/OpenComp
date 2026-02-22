"""OpenComp Grade node — Lift / Gamma / Gain colour grade.

Inputs:  Image (RGBA32F, linear scene-referred)
Outputs: Image (RGBA32F, linear scene-referred)
Shader:  shaders/grade.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class GradeNode(OpenCompNode):
    """Lift / Gamma / Gain colour grade."""

    bl_idname = "OC_N_grade"
    bl_label = "Grade"
    bl_icon = "COLORSET_09_VEC"

    lift:  bpy.props.FloatVectorProperty(name="Lift",  default=(0.0, 0.0, 0.0), size=3)
    gamma: bpy.props.FloatVectorProperty(name="Gamma", default=(1.0, 1.0, 1.0), size=3)
    gain:  bpy.props.FloatVectorProperty(name="Gain",  default=(1.0, 1.0, 1.0), size=3)
    mix:   bpy.props.FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0)

    _output_texture = None

    def init(self, context):
        self.inputs.new("OC_NS_image", "Image")
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
            self._output_texture = evaluate_shader(
                "grade.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] GradeNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(GradeNode)


def unregister():
    try:
        bpy.utils.unregister_class(GradeNode)
    except RuntimeError:
        pass
