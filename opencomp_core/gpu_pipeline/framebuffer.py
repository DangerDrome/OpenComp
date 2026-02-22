"""OpenComp ping-pong framebuffer system.

Used for multi-pass rendering (e.g. separable blur: horizontal → vertical).
Alternates between two RGBA32F textures so one pass can read from one
while writing to the other.
"""


class PingPongBuffer:
    """Ping-pong pair of RGBA32F textures for multi-pass rendering."""

    def __init__(self, width, height, texture_pool):
        self.width = width
        self.height = height
        self._pool = texture_pool
        self._textures = [
            texture_pool.get(width, height),
            texture_pool.get(width, height),
        ]
        self._index = 0

    @property
    def source(self):
        """Texture to read from (input to current pass)."""
        return self._textures[self._index]

    @property
    def target(self):
        """Texture to write to (output of current pass)."""
        return self._textures[1 - self._index]

    def swap(self):
        """Swap source and target for the next pass."""
        self._index = 1 - self._index

    def release(self):
        """Return both textures to the pool."""
        for tex in self._textures:
            if tex is not None:
                self._pool.release(tex)
        self._textures = [None, None]
