"""OpenComp Constant node — solid colour generator.

Inputs:  (none — source node)
Outputs: Image (RGBA32F)
Shader:  shaders/constant.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader
from ... import console


class ConstantNode(OpenCompNode):
    """Generate a solid colour image."""

    bl_idname = "OC_N_constant"
    bl_label = "Constant"
    bl_icon = "IMAGE_DATA"

    color:       bpy.props.FloatVectorProperty(
        name="Color", default=(0.0, 0.0, 0.0, 1.0), size=4,
        subtype='COLOR', min=0.0, max=1.0,
    )
    width_prop:  bpy.props.IntProperty(name="Width",  default=1920, min=1, max=8192)
    height_prop: bpy.props.IntProperty(name="Height", default=1080, min=1, max=8192)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "color")
        row = layout.row(align=True)
        row.prop(self, "width_prop")
        row.prop(self, "height_prop")

    def evaluate(self, texture_pool):
        try:
            uniforms = {"u_color": list(self.color)}
            self._output_texture = evaluate_shader(
                "constant.frag", None, uniforms, texture_pool,
                output_size=(self.width_prop, self.height_prop),
            )
            return self._output_texture
        except Exception as e:
            console.error(f"ConstantNode.evaluate error: {e}", "Node")
            return None


def register():
    bpy.utils.register_class(ConstantNode)


def unregister():
    try:
        bpy.utils.unregister_class(ConstantNode)
    except RuntimeError:
        pass
