"""OpenComp Shuffle node — channel routing.

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, channels remapped)
Shader:  shaders/shuffle.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader
from ... import console

_CHANNEL_ITEMS = [
    ('R', "R", "Red channel",    0),
    ('G', "G", "Green channel",  1),
    ('B', "B", "Blue channel",   2),
    ('A', "A", "Alpha channel",  3),
    ('ZERO', "0", "Black",       4),
    ('ONE',  "1", "White",       5),
]

_CH_INDEX = {item[0]: float(item[3]) for item in _CHANNEL_ITEMS}


class ShuffleNode(OpenCompNode):
    """Channel routing — remap any output channel to any source channel."""

    bl_idname = "OC_N_shuffle"
    bl_label = "Shuffle"
    bl_icon = "UV_SYNC_SELECT"

    r_source: bpy.props.EnumProperty(name="R", items=_CHANNEL_ITEMS, default='R')
    g_source: bpy.props.EnumProperty(name="G", items=_CHANNEL_ITEMS, default='G')
    b_source: bpy.props.EnumProperty(name="B", items=_CHANNEL_ITEMS, default='B')
    a_source: bpy.props.EnumProperty(name="A", items=_CHANNEL_ITEMS, default='A')

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "r_source")
        col.prop(self, "g_source")
        col.prop(self, "b_source")
        col.prop(self, "a_source")

    def evaluate(self, texture_pool):
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None
            uniforms = {
                "u_r_source": _CH_INDEX[self.r_source],
                "u_g_source": _CH_INDEX[self.g_source],
                "u_b_source": _CH_INDEX[self.b_source],
                "u_a_source": _CH_INDEX[self.a_source],
            }
            self._output_texture = evaluate_shader(
                "shuffle.frag", input_tex, uniforms, texture_pool
            )
            return self._output_texture
        except Exception as e:
            console.error(f"ShuffleNode.evaluate error: {e}", "Node")
            return None


def register():
    bpy.utils.register_class(ShuffleNode)


def unregister():
    try:
        bpy.utils.unregister_class(ShuffleNode)
    except RuntimeError:
        pass
