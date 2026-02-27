"""OpenComp CDL node — ASC CDL (slope / offset / power) with saturation.

Inputs:  Image (RGBA32F, linear scene-referred)
Outputs: Image (RGBA32F, linear scene-referred)
Shader:  shaders/cdl.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader
from ... import console


class CDLNode(OpenCompNode):
    """ASC CDL colour correction."""

    bl_idname = "OC_N_cdl"
    bl_label = "CDL"
    bl_icon = "COLORSET_03_VEC"

    slope:      bpy.props.FloatVectorProperty(name="Slope",  default=(1.0, 1.0, 1.0), size=3, min=0.0)
    offset:     bpy.props.FloatVectorProperty(name="Offset", default=(0.0, 0.0, 0.0), size=3)
    power:      bpy.props.FloatVectorProperty(name="Power",  default=(1.0, 1.0, 1.0), size=3, min=0.0)
    saturation: bpy.props.FloatProperty(name="Saturation", default=1.0, min=0.0, max=4.0)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "slope")
        layout.prop(self, "offset")
        layout.prop(self, "power")
        layout.prop(self, "saturation")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None
            uniforms = {
                "u_slope":      list(self.slope),
                "u_offset":     list(self.offset),
                "u_power":      list(self.power),
                "u_saturation": self.saturation,
            }
            self._output_texture = evaluate_shader(
                "cdl.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            console.error(f"CDLNode.evaluate error: {e}", "Node")
            return None


def register():
    bpy.utils.register_class(CDLNode)


def unregister():
    try:
        bpy.utils.unregister_class(CDLNode)
    except RuntimeError:
        pass
