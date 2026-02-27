"""OpenComp Merge node — arithmetic blend modes (plus / multiply / screen).

Inputs:  A, B  — RGBA32F
Outputs: Image (RGBA32F)
Shader:  shaders/merge.frag
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader
from ... import console

_MODE_ITEMS = [
    ('PLUS',     "Plus",     "Additive blend",  0),
    ('MULTIPLY', "Multiply", "Multiply blend",  1),
    ('SCREEN',   "Screen",   "Screen blend",    2),
]

_MODE_INDEX = {item[0]: item[3] for item in _MODE_ITEMS}


class MergeNode(OpenCompNode):
    """Arithmetic blend modes: plus, multiply, screen."""

    bl_idname = "OC_N_merge"
    bl_label = "Merge"
    bl_icon = "NODE_COMPOSITING"

    mode: bpy.props.EnumProperty(name="Mode", items=_MODE_ITEMS, default='PLUS')
    mix:  bpy.props.FloatProperty(name="Mix", default=1.0, min=0.0, max=1.0)

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "A")
        self.inputs.new("OC_NS_image", "B")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "mode")
        layout.prop(self, "mix")

    def evaluate(self, texture_pool):
        try:
            a_tex = self.inputs["A"].get_texture()
            b_tex = self.inputs["B"].get_texture()

            if a_tex is None and b_tex is None:
                return None
            if a_tex is None:
                self._output_texture = b_tex
                return b_tex
            if b_tex is None:
                self._output_texture = a_tex
                return a_tex

            uniforms = {
                "u_mode": float(_MODE_INDEX.get(self.mode, 0)),
                "u_mix":  self.mix,
            }
            self._output_texture = evaluate_shader(
                "merge.frag", a_tex, uniforms, texture_pool,
                extra_textures={"u_bg": b_tex},
            )
            return self._output_texture
        except Exception as e:
            console.error(f"MergeNode.evaluate error: {e}", "Node")
            return None


def register():
    bpy.utils.register_class(MergeNode)


def unregister():
    try:
        bpy.utils.unregister_class(MergeNode)
    except RuntimeError:
        pass
