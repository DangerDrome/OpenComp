"""OpenComp socket types — ImageSocket, FloatSocket, VectorSocket.

Socket colours follow Nuke conventions:
  Image  — yellow
  Float  — grey
  Vector — blue
"""

import bpy


class ImageSocket(bpy.types.NodeSocket):
    """RGBA32F image data socket."""

    bl_idname = "OC_NS_image"
    bl_label = "Image"

    def draw(self, context, layout, node, text):
        layout.label(text=text)

    def draw_color(self, context, node):
        return (0.78, 0.78, 0.16, 1.0)

    def get_texture(self):
        """Return the GPUTexture from the connected upstream node, or None.

        If this is an output socket, looks up the owning node's texture
        from the module-level cache (avoids Blender RNA wrapper issues).
        If this is an input socket, follows the link to the connected output.
        """
        if self.is_output:
            from .tree import _node_textures
            return _node_textures.get(self.node.name, None)
        if self.is_linked:
            return self.links[0].from_socket.get_texture()
        return None


class FloatSocket(bpy.types.NodeSocket):
    """Single float value socket."""

    bl_idname = "OC_NS_float"
    bl_label = "Float"

    default_value: bpy.props.FloatProperty(name="Value", default=0.0)

    def draw(self, context, layout, node, text):
        if self.is_output or self.is_linked:
            layout.label(text=text)
        else:
            layout.prop(self, "default_value", text=text)

    def draw_color(self, context, node):
        return (0.63, 0.63, 0.63, 1.0)


class VectorSocket(bpy.types.NodeSocket):
    """3-component vector socket (XYZ or RGB)."""

    bl_idname = "OC_NS_vector"
    bl_label = "Vector"

    default_value: bpy.props.FloatVectorProperty(
        name="Value", default=(0.0, 0.0, 0.0), size=3
    )

    def draw(self, context, layout, node, text):
        if self.is_output or self.is_linked:
            layout.label(text=text)
        else:
            layout.prop(self, "default_value", text=text)

    def draw_color(self, context, node):
        return (0.39, 0.39, 0.78, 1.0)


_classes = (ImageSocket, FloatSocket, VectorSocket)


def register():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass  # Already registered


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
