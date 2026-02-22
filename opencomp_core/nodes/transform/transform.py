"""OpenComp Transform node — 2D affine (translate, rotate, scale).

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, transformed)
Shader:  shaders/transform.frag
"""

import math

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class TransformNode(OpenCompNode):
    """2D affine transform: translate, rotate, scale around center."""

    bl_idname = "OC_N_transform"
    bl_label = "Transform"
    bl_icon = "OBJECT_ORIGIN"

    translate: bpy.props.FloatVectorProperty(
        name="Translate", default=(0.0, 0.0), size=2
    )
    rotate: bpy.props.FloatProperty(
        name="Rotate", default=0.0, subtype='ANGLE'
    )
    scale: bpy.props.FloatVectorProperty(
        name="Scale", default=(1.0, 1.0), size=2
    )
    center: bpy.props.FloatVectorProperty(
        name="Center", default=(0.5, 0.5), size=2
    )

    _output_texture = None

    def init(self, context):
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "translate")
        layout.prop(self, "rotate")
        layout.prop(self, "scale")
        layout.prop(self, "center")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None

            uniforms = {
                "u_translate": list(self.translate),
                "u_rotate":    self.rotate,  # already radians from ANGLE subtype
                "u_scale":     list(self.scale),
                "u_center":    list(self.center),
            }
            self._output_texture = evaluate_shader(
                "transform.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] TransformNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(TransformNode)


def unregister():
    try:
        bpy.utils.unregister_class(TransformNode)
    except RuntimeError:
        pass
