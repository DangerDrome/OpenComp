"""OpenComp Over node — premultiplied alpha-over compositing.

Inputs:  A (foreground), B (background)  — RGBA32F
Outputs: Image (RGBA32F)
Shader:  shaders/over.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class OverNode(OpenCompNode):
    """Premultiplied alpha-over composite: A + B * (1 - A.a)."""

    bl_idname = "OC_N_over"
    bl_label = "Over"
    bl_icon = "NODE_COMPOSITING"

    mix: bpy.props.FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "A")
        self.inputs.new("OC_NS_image", "B")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "mix")

    def evaluate(self, texture_pool):
        try:
            fg_tex = self.inputs["A"].get_texture()
            bg_tex = self.inputs["B"].get_texture()

            if fg_tex is None and bg_tex is None:
                return None
            if fg_tex is None:
                self._output_texture = bg_tex
                return bg_tex
            if bg_tex is None:
                self._output_texture = fg_tex
                return fg_tex

            uniforms = {"u_mix": self.mix}
            self._output_texture = evaluate_shader(
                "over.frag", fg_tex, uniforms, texture_pool,
                extra_textures={"u_bg": bg_tex},
            )
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] OverNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(OverNode)


def unregister():
    try:
        bpy.utils.unregister_class(OverNode)
    except RuntimeError:
        pass
