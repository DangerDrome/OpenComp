"""OpenComp texture pool — RGBA32F GPUTexture reuse.

Nodes request textures via get(width, height) and return them via release(tex).
The pool avoids GPU allocation thrash by reusing textures of the same size.
"""


class TexturePool:
    """Pool of RGBA32F GPUTextures keyed by (width, height)."""

    def __init__(self):
        self._available = {}  # (w, h) → [GPUTexture, ...]

    def get(self, width, height):
        """Get a texture from pool or allocate a new RGBA32F GPUTexture."""
        import gpu

        key = (width, height)
        if key in self._available and self._available[key]:
            return self._available[key].pop()

        return gpu.types.GPUTexture((width, height), format='RGBA32F')

    def release(self, tex):
        """Return a texture to the pool for reuse."""
        if tex is None:
            return
        key = (tex.width, tex.height)
        if key not in self._available:
            self._available[key] = []
        self._available[key].append(tex)

    def clear(self):
        """Drop all pooled textures (frees GPU memory)."""
        self._available.clear()
