"""OpenComp Read node — loads image files via OIIO into RGBA32F GPUTexture.

Inputs:  (none — source node)
Outputs: Image (RGBA32F, linear scene-referred)
"""

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from ..base import OpenCompNode


class OC_OT_read_browse(Operator, ImportHelper):
    """Browse for image file"""
    bl_idname = "oc.read_browse"
    bl_label = "Browse Image"

    node_name: bpy.props.StringProperty()

    filter_glob: bpy.props.StringProperty(
        default="*.exr;*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.hdr;*.dpx;*.cin",
        options={'HIDDEN'},
    )

    def execute(self, context):
        # Find the node and set filepath
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor":
                node = tree.nodes.get(self.node_name)
                if node:
                    node.filepath = self.filepath
                    break
        return {'FINISHED'}


# Cache: {node_name: (resolved_path, GPUTexture)} — avoids re-reading
# the same file from disk every evaluation tick.
_read_cache = {}


def _on_prop_update(self, context):
    """Trigger graph re-evaluation when filepath changes."""
    # Invalidate cache for this node so it re-reads
    _read_cache.pop(self.name, None)
    # Also invalidate thumbnail cache
    _thumbnail_cache.pop(self.name, None)
    from ...node_graph.tree import request_evaluate
    request_evaluate()


# Thumbnail cache: {node_name: bpy.types.Image}
_thumbnail_cache = {}


class ReadNode(OpenCompNode):
    """Read an image file from disk using OpenImageIO."""

    bl_idname = "OC_N_read"
    bl_label = "Read"
    bl_icon = "FILE_IMAGE"

    filepath: bpy.props.StringProperty(
        name="File", subtype='FILE_PATH', default="",
        update=_on_prop_update,
    )
    show_thumbnail: bpy.props.BoolProperty(
        name="Show Thumbnail", default=False,
        description="Display a preview thumbnail of the image",
    )

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.outputs.new("OC_NS_image", "Image")

    def _get_thumbnail(self):
        """Get or create a Blender image for thumbnail preview."""
        if not self.filepath:
            return None

        resolved = bpy.path.abspath(self.filepath)

        # Check cache
        cached = _thumbnail_cache.get(self.name)
        if cached and cached[0] == resolved:
            img = cached[1]
            # Ensure preview is available
            if img and img.preview:
                return img
            return None

        # Load image into Blender for preview
        try:
            import os
            if not os.path.exists(resolved):
                return None

            # Use a unique name based on node name to avoid conflicts
            img_name = f"_oc_thumb_{self.name}"

            # Remove old image if exists
            if img_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[img_name])

            # Load new image
            img = bpy.data.images.load(resolved)
            img.name = img_name

            # Ensure preview is generated
            img.preview_ensure()

            _thumbnail_cache[self.name] = (resolved, img)
            return img
        except Exception as e:
            print(f"[OpenComp] Could not load thumbnail: {e}")
            return None

    def draw_buttons(self, context, layout):
        # File path - FILE_PATH subtype automatically adds browse button
        layout.prop(self, "filepath", text="")

        # Thumbnail toggle
        row = layout.row()
        row.prop(self, "show_thumbnail", icon='IMAGE_DATA', text="")

        # Show thumbnail if enabled
        if self.show_thumbnail and self.filepath:
            img = self._get_thumbnail()
            if img:
                layout.template_icon(icon_value=img.preview.icon_id, scale=5.0)

    def evaluate(self, texture_pool):
        """Read image file → RGBA32F GPUTexture."""
        try:
            if not self.filepath:
                return None

            resolved = bpy.path.abspath(self.filepath)

            # Read proxy factor from viewer settings
            proxy_factor = 1
            try:
                proxy_factor = int(bpy.context.scene.oc_viewer.proxy)
            except (AttributeError, ValueError):
                pass

            # Return cached texture if filepath + proxy haven't changed
            cache_key = (resolved, proxy_factor)
            cached = _read_cache.get(self.name)
            if cached and cached[0] == cache_key:
                return cached[1]

            bpy.utils.expose_bundled_modules()
            import OpenImageIO as oiio
            import numpy as np
            import gpu

            inp = oiio.ImageInput.open(resolved)
            if inp is None:
                print(f"[OpenComp] ReadNode: cannot open {self.filepath}")
                return None

            spec = inp.spec()
            pixels = oiio.ImageInput.read_image(inp, oiio.FLOAT)
            pixels = pixels.reshape(spec.height, spec.width, spec.nchannels)

            # Ensure RGBA — pad missing channels
            if spec.nchannels == 3:
                alpha = np.ones(
                    (spec.height, spec.width, 1), dtype=np.float32
                )
                pixels = np.concatenate([pixels, alpha], axis=2)
            elif spec.nchannels == 1:
                pixels = np.concatenate(
                    [np.repeat(pixels, 3, axis=2),
                     np.ones((spec.height, spec.width, 1), dtype=np.float32)],
                    axis=2,
                )

            inp.close()

            # Apply proxy downscale via numpy stride slicing
            if proxy_factor > 1:
                pixels = pixels[::proxy_factor, ::proxy_factor, :]

            h, w = pixels.shape[0], pixels.shape[1]

            # Upload to GPU
            flat = pixels.flatten().tolist()
            buf = gpu.types.Buffer('FLOAT', len(flat), flat)
            tex = gpu.types.GPUTexture(
                (w, h), format='RGBA32F', data=buf
            )

            _read_cache[self.name] = (cache_key, tex)
            proxy_label = f" (proxy 1/{proxy_factor})" if proxy_factor > 1 else ""
            print(f"[OpenComp] Read: {w}x{h}{proxy_label} from {self.filepath}")
            return tex

        except Exception as e:
            print(f"[OpenComp] ReadNode.evaluate error: {e}")
            return None


def register():
    bpy.utils.register_class(OC_OT_read_browse)
    bpy.utils.register_class(ReadNode)


def unregister():
    # Clean up thumbnail images
    for name, (_, img) in list(_thumbnail_cache.items()):
        try:
            if img and img.name in bpy.data.images:
                bpy.data.images.remove(img)
        except Exception:
            pass
    _thumbnail_cache.clear()
    _read_cache.clear()

    try:
        bpy.utils.unregister_class(ReadNode)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(OC_OT_read_browse)
    except RuntimeError:
        pass
