"""OpenComp Roto node — draw bezier shapes to create masks.

Inputs:  Source (optional RGBA32F for dimensions)
Outputs: Mask (RGBA32F - alpha mask in all channels)
Shader:  shaders/roto.frag

For MVP: Basic shape modes (ellipse, rectangle)
Future: Full bezier spline editing with viewer tools
"""

import bpy
from ..base import OpenCompNode
from ...gpu_pipeline.executor import evaluate_shader


class RotoNode(OpenCompNode):
    """Draw shapes to create alpha masks."""

    bl_idname = "OC_N_roto"
    bl_label = "Roto"
    bl_icon = "MESH_CIRCLE"

    # Shape mode
    shape_mode: bpy.props.EnumProperty(
        name="Shape",
        description="Shape type",
        items=[
            ('ELLIPSE', "Ellipse", "Elliptical mask"),
            ('RECTANGLE', "Rectangle", "Rectangular mask"),
        ],
        default='ELLIPSE',
    )

    # Position (normalized 0-1, center of image is 0.5, 0.5)
    center_x: bpy.props.FloatProperty(
        name="Center X",
        default=0.5,
        min=0.0, max=1.0,
        subtype='FACTOR',
    )
    center_y: bpy.props.FloatProperty(
        name="Center Y",
        default=0.5,
        min=0.0, max=1.0,
        subtype='FACTOR',
    )

    # Size (normalized)
    size_x: bpy.props.FloatProperty(
        name="Width",
        default=0.3,
        min=0.001, max=2.0,
    )
    size_y: bpy.props.FloatProperty(
        name="Height",
        default=0.3,
        min=0.001, max=2.0,
    )

    # Rotation in degrees
    rotation: bpy.props.FloatProperty(
        name="Rotation",
        default=0.0,
        min=-180.0, max=180.0,
        subtype='ANGLE',
    )

    # Feather/softness
    feather: bpy.props.FloatProperty(
        name="Feather",
        description="Edge softness",
        default=0.01,
        min=0.0, max=0.5,
    )

    # Invert the mask
    invert: bpy.props.BoolProperty(
        name="Invert",
        default=False,
    )

    # Output resolution (when no input connected)
    output_width: bpy.props.IntProperty(
        name="Width",
        default=1920,
        min=1, max=8192,
    )
    output_height: bpy.props.IntProperty(
        name="Height",
        default=1080,
        min=1, max=8192,
    )

    _output_texture = None

    def init(self, context):
        super().init(context)
        # Optional source input (for getting dimensions)
        self.inputs.new("OC_NS_image", "Source")
        self.outputs.new("OC_NS_image", "Mask")
        # Start expanded so user can see shape controls
        self.hide = False

    def draw_buttons(self, context, layout):
        layout.prop(self, "shape_mode")

        col = layout.column(align=True)
        col.label(text="Position:")
        row = col.row(align=True)
        row.prop(self, "center_x", text="X")
        row.prop(self, "center_y", text="Y")

        col = layout.column(align=True)
        col.label(text="Size:")
        row = col.row(align=True)
        row.prop(self, "size_x", text="W")
        row.prop(self, "size_y", text="H")

        layout.prop(self, "rotation")
        layout.prop(self, "feather")
        layout.prop(self, "invert")

        # Show resolution controls when no source connected
        if not self.inputs["Source"].is_linked:
            col = layout.column(align=True)
            col.label(text="Output Size:")
            row = col.row(align=True)
            row.prop(self, "output_width", text="W")
            row.prop(self, "output_height", text="H")

    def evaluate(self, texture_pool):
        import math
        try:
            # Get dimensions from source or use output settings
            source_tex = self.inputs["Source"].get_texture()

            if source_tex is not None:
                width = source_tex.width
                height = source_tex.height
            else:
                width = self.output_width
                height = self.output_height

            # Convert rotation to radians
            rotation_rad = math.radians(self.rotation)

            # Shape mode as integer for shader
            shape_mode_int = 0 if self.shape_mode == 'ELLIPSE' else 1

            uniforms = {
                "u_resolution": (float(width), float(height)),
                "u_center": (self.center_x, self.center_y),
                "u_size": (self.size_x, self.size_y),
                "u_rotation": rotation_rad,
                "u_feather": self.feather,
                "u_invert": 1.0 if self.invert else 0.0,
                "u_shape_mode": float(shape_mode_int),
            }

            self._output_texture = evaluate_shader(
                "roto.frag",
                source_tex,  # Can be None - shader handles it
                uniforms,
                texture_pool,
                output_size=(width, height),
            )
            return self._output_texture

        except Exception as e:
            print(f"[OpenComp] RotoNode.evaluate error: {e}")
            import traceback
            traceback.print_exc()
            return None


def register():
    bpy.utils.register_class(RotoNode)


def unregister():
    try:
        bpy.utils.unregister_class(RotoNode)
    except RuntimeError:
        pass
