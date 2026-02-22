"""OpenComp Crop node — blacks out pixels outside the crop region.

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, cropped)
Shader:  shaders/crop.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class CropNode(OpenCompNode):
    """Crop — blacks out pixels outside the specified region."""

    bl_idname = "OC_N_crop"
    bl_label = "Crop"
    bl_icon = "SELECT_SET"

    left:   bpy.props.FloatProperty(name="Left",   default=0.0, min=0.0, max=1.0)
    right:  bpy.props.FloatProperty(name="Right",  default=1.0, min=0.0, max=1.0)
    bottom: bpy.props.FloatProperty(name="Bottom", default=0.0, min=0.0, max=1.0)
    top:    bpy.props.FloatProperty(name="Top",    default=1.0, min=0.0, max=1.0)

    _output_texture = None

    def init(self, context):
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "left")
        col.prop(self, "right")
        col.prop(self, "bottom")
        col.prop(self, "top")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None

            uniforms = {
                "u_crop": [self.left, self.bottom, self.right, self.top],
            }
            self._output_texture = evaluate_shader(
                "crop.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] CropNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(CropNode)


def unregister():
    try:
        bpy.utils.unregister_class(CropNode)
    except RuntimeError:
        pass
