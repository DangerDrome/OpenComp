"""OpenComp Read node — loads image files via OIIO into RGBA32F GPUTexture.

Inputs:  (none — source node)
Outputs: Image (RGBA32F, linear scene-referred)
"""

import bpy
from ..base import OpenCompNode


# Cache: {node_name: (resolved_path, GPUTexture)} — avoids re-reading
# the same file from disk every evaluation tick.
_read_cache = {}


def _on_prop_update(self, context):
    """Trigger graph re-evaluation when filepath changes."""
    # Invalidate cache for this node so it re-reads
    _read_cache.pop(self.name, None)
    from ...node_graph.tree import request_evaluate
    request_evaluate()


class ReadNode(OpenCompNode):
    """Read an image file from disk using OpenImageIO."""

    bl_idname = "OC_N_read"
    bl_label = "Read"
    bl_icon = "FILE_IMAGE"

    filepath: bpy.props.StringProperty(
        name="File", subtype='FILE_PATH', default="",
        update=_on_prop_update,
    )

    _output_texture = None

    def init(self, context):
        self.outputs.new("OC_NS_image", "Image")

    def draw_buttons(self, context, layout):
        layout.prop(self, "filepath")

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
    bpy.utils.register_class(ReadNode)


def unregister():
    try:
        bpy.utils.unregister_class(ReadNode)
    except RuntimeError:
        pass
