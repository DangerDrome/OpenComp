"""OpenComp texture pool — RGBA32F GPUTexture reuse.

Nodes request textures via get(width, height) and return them via release(tex).
The pool avoids GPU allocation thrash by reusing textures of the same size.

The pool has configurable bounds to prevent unbounded memory growth:
- max_textures_per_size: Maximum textures to keep per resolution (default: 4)
- max_total_textures: Maximum total textures in pool (default: 32)

When limits are exceeded, oldest textures are evicted.
"""


class TexturePool:
    """Pool of RGBA32F GPUTextures keyed by (width, height).

    Attributes:
        max_textures_per_size: Max textures to keep per (w, h) key.
        max_total_textures: Max total textures across all sizes.
    """

    def __init__(self, max_textures_per_size=4, max_total_textures=32):
        """Initialize the texture pool.

        Args:
            max_textures_per_size: Maximum textures to keep per resolution.
            max_total_textures: Maximum total textures in pool.
        """
        self._available = {}  # (w, h) → [GPUTexture, ...]
        self.max_textures_per_size = max_textures_per_size
        self.max_total_textures = max_total_textures

    def get(self, width, height):
        """Get a texture from pool or allocate a new RGBA32F GPUTexture."""
        import gpu

        key = (width, height)
        if key in self._available and self._available[key]:
            return self._available[key].pop()

        return gpu.types.GPUTexture((width, height), format='RGBA32F')

    def release(self, tex):
        """Return a texture to the pool for reuse.

        If pool limits are exceeded, the texture is discarded instead.
        """
        if tex is None:
            return

        key = (tex.width, tex.height)

        # Check per-size limit
        if key not in self._available:
            self._available[key] = []

        if len(self._available[key]) >= self.max_textures_per_size:
            # Limit reached for this size, discard texture
            del tex
            return

        # Check total limit
        total = sum(len(textures) for textures in self._available.values())
        if total >= self.max_total_textures:
            # Evict oldest texture from the largest pool
            self._evict_one()

        self._available[key].append(tex)

    def _evict_one(self):
        """Evict one texture from the pool (largest pool first)."""
        if not self._available:
            return

        # Find the key with the most textures
        largest_key = max(self._available.keys(),
                         key=lambda k: len(self._available[k]),
                         default=None)

        if largest_key and self._available[largest_key]:
            # Remove and discard the oldest texture
            tex = self._available[largest_key].pop(0)
            del tex

            # Clean up empty entries
            if not self._available[largest_key]:
                del self._available[largest_key]

    def clear(self):
        """Drop all pooled textures (frees GPU memory)."""
        self._available.clear()

    def stats(self):
        """Return pool statistics for debugging.

        Returns:
            dict with 'total_textures', 'sizes', and 'memory_estimate_mb'
        """
        total = sum(len(textures) for textures in self._available.values())
        sizes = {k: len(v) for k, v in self._available.items()}

        # Estimate memory (RGBA32F = 16 bytes per pixel)
        memory_bytes = 0
        for (w, h), textures in self._available.items():
            memory_bytes += len(textures) * w * h * 16

        return {
            'total_textures': total,
            'sizes': sizes,
            'memory_estimate_mb': memory_bytes / (1024 * 1024),
        }


# Module-level singleton instance
_texture_pool = None


def get_texture_pool():
    """Get the global TexturePool singleton instance."""
    global _texture_pool
    if _texture_pool is None:
        _texture_pool = TexturePool()
    return _texture_pool
