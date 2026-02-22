"""OpenComp Write node — writes GPUTexture to disk via OIIO.

Inputs:  Image (RGBA32F)
Outputs: (none — sink node)
Supported formats: EXR, DPX, TIFF (determined by file extension).
"""

import bpy
from ..base import OpenCompNode


class WriteNode(OpenCompNode):
    """Write image to disk using OpenImageIO."""

    bl_idname = "OC_N_write"
    bl_label = "Write"
    bl_icon = "FILE_TICK"

    filepath: bpy.props.StringProperty(
        name="File", subtype='FILE_PATH', default=""
    )
    file_format: bpy.props.EnumProperty(
        name="Format",
        items=[
            ('EXR',  "EXR",  "OpenEXR float"),
            ('DPX',  "DPX",  "DPX 10-bit log"),
            ('TIFF', "TIFF", "TIFF float"),
        ],
        default='EXR',
    )

    def init(self, context):
        self.inputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "filepath")
        layout.prop(self, "file_format")

    def evaluate(self, texture_pool):
        """Read back from GPU and write to disk via OIIO."""
        try:
            input_tex = self.inputs["Image"].get_texture()
            if input_tex is None or not self.filepath:
                return None

            import gpu
            bpy.utils.expose_bundled_modules()
            import OpenImageIO as oiio
            import numpy as np

            w, h = input_tex.width, input_tex.height

            # Read pixels back from GPU texture
            buf = input_tex.read()
            pixels = np.array(list(buf), dtype=np.float32).reshape(h, w, 4)

            # Flip vertically — GPU textures are bottom-up
            pixels = np.flipud(pixels)

            # Write with OIIO
            filepath = bpy.path.abspath(self.filepath)
            out = oiio.ImageOutput.create(filepath)
            if out is None:
                print(f"[OpenComp] WriteNode: cannot create output for {filepath}")
                return None

            spec = oiio.ImageSpec(w, h, 4, oiio.FLOAT)
            out.open(filepath, spec)
            out.write_image(pixels)
            out.close()

            print(f"[OpenComp] Write: {w}x{h} → {filepath}")
            return None  # Write has no output

        except Exception as e:
            print(f"[OpenComp] WriteNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(WriteNode)


def unregister():
    try:
        bpy.utils.unregister_class(WriteNode)
    except RuntimeError:
        pass
