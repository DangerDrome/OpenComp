"""OpenComp Blur node — separable gaussian blur (horizontal + vertical passes).

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, blurred)
Shader:  shaders/blur_h.frag + shaders/blur_v.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader
from ... import console


class BlurNode(OpenCompNode):
    """Separable gaussian blur — two-pass (horizontal + vertical)."""

    bl_idname = "OC_N_blur"
    bl_label = "Blur"
    bl_icon = "MESH_UVSPHERE"

    size: bpy.props.FloatProperty(name="Size", default=5.0, min=0.0, max=100.0)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "size")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None

            w, h = input_tex.width, input_tex.height
            uniforms = {
                "u_radius":     float(self.size),
                "u_resolution": [float(w), float(h)],
            }

            # Pass 1: horizontal blur
            intermediate = evaluate_shader(
                "blur_h.frag", input_tex, uniforms, texture_pool
            )

            # Pass 2: vertical blur
            output = evaluate_shader(
                "blur_v.frag", intermediate, uniforms, texture_pool
            )

            # Release intermediate — only final output survives
            texture_pool.release(intermediate)

            self._output_texture = output
            return self._output_texture
        except Exception as e:
            console.error(f"BlurNode.evaluate error: {e}", "Node")
            return None


def register():
    bpy.utils.register_class(BlurNode)


def unregister():
    try:
        bpy.utils.unregister_class(BlurNode)
    except RuntimeError:
        pass
