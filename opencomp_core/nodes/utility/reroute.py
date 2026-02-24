"""OpenComp Reroute node — passes through image data for cleaner wiring.

Inputs:  Image (RGBA32F)
Outputs: Image (RGBA32F, unchanged)
"""

import bpy
from ..base import OpenCompNode


class RerouteNode(OpenCompNode):
    """Reroute — passes through the input image unchanged for cleaner graph layout."""

    bl_idname = "OC_N_reroute"
    bl_label = "Reroute"
    bl_icon = "CON_FOLLOWPATH"

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.inputs.new("OC_NS_image", "Image")
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        # Reroute node has no UI - it's just a passthrough
        pass

    def evaluate(self, texture_pool):
        """Simply pass through the input texture."""
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None:
                return None
            self._output_texture = input_tex
            return self._output_texture
        except Exception as e:
            print(f"[OpenComp] RerouteNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(RerouteNode)


def unregister():
    try:
        bpy.utils.unregister_class(RerouteNode)
    except RuntimeError:
        pass
