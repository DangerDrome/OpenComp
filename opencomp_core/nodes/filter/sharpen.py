"""OpenComp Sharpen node — 3x3 Laplacian unsharp mask.

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, sharpened)
Shader:  shaders/sharpen.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class SharpenNode(OpenCompNode):
    """3x3 Laplacian sharpening."""

    bl_idname = "OC_N_sharpen"
    bl_label = "Sharpen"
    bl_icon = "MESH_UVSPHERE"

    amount: bpy.props.FloatProperty(name="Amount", default=0.5, min=0.0, max=10.0)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "amount")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None

            w, h = input_tex.width, input_tex.height
            uniforms = {
                "u_amount":     self.amount,
                "u_resolution": [float(w), float(h)],
            }
            self._output_texture = evaluate_shader(
                "sharpen.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] SharpenNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(SharpenNode)


def unregister():
    try:
        bpy.utils.unregister_class(SharpenNode)
    except RuntimeError:
        pass
