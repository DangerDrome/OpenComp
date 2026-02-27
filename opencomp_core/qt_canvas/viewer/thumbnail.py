"""OpenComp Qt Canvas — Node thumbnail display.

Receives thumbnail data from Blender via shared memory and displays
it on nodes in the Qt canvas.

SHM Protocol:
    /tmp/opencomp_thumb_{node_id}.shm
    Format: 4 bytes width + 4 bytes height + raw RGBA8 bytes
"""

import struct
import mmap
import pathlib
from typing import Optional

from qtpy.QtGui import QImage, QPixmap
from qtpy.QtCore import Qt


# Thumbnail dimensions
THUMB_WIDTH = 128
THUMB_HEIGHT = 72


def get_shm_path(node_id: str) -> pathlib.Path:
    """Get shared memory file path for a node's thumbnail.

    Args:
        node_id: Node's unique ID (oc_id).

    Returns:
        Path to the shared memory file.
    """
    return pathlib.Path(f"/tmp/opencomp_thumb_{node_id}.shm")


def read_thumbnail(node_id: str) -> Optional[QPixmap]:
    """Read thumbnail data from shared memory and create QPixmap.

    Args:
        node_id: Node's unique ID.

    Returns:
        QPixmap of the thumbnail, or None if not available.
    """
    shm_path = get_shm_path(node_id)

    if not shm_path.exists():
        return None

    try:
        with open(shm_path, 'rb') as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

            # Read header: width (4 bytes) + height (4 bytes)
            header = mm.read(8)
            if len(header) < 8:
                mm.close()
                return None

            width, height = struct.unpack('<II', header)

            if width == 0 or height == 0:
                mm.close()
                return None

            # Read RGBA data
            expected_size = width * height * 4
            data = mm.read(expected_size)
            mm.close()

            if len(data) < expected_size:
                return None

            # Create QImage from raw RGBA data
            image = QImage(
                data, width, height, width * 4,
                QImage.Format_RGBA8888
            )

            # Convert to QPixmap
            pixmap = QPixmap.fromImage(image)

            # Scale to thumbnail size if needed
            if width != THUMB_WIDTH or height != THUMB_HEIGHT:
                pixmap = pixmap.scaled(
                    THUMB_WIDTH, THUMB_HEIGHT,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

            return pixmap

    except Exception:
        return None


def write_thumbnail(node_id: str, width: int, height: int, rgba_data: bytes) -> bool:
    """Write thumbnail data to shared memory (called from Blender side).

    Args:
        node_id: Node's unique ID.
        width: Image width in pixels.
        height: Image height in pixels.
        rgba_data: Raw RGBA8 pixel data.

    Returns:
        True if successful, False otherwise.
    """
    shm_path = get_shm_path(node_id)

    try:
        # Write header + data
        header = struct.pack('<II', width, height)

        with open(shm_path, 'wb') as f:
            f.write(header)
            f.write(rgba_data)

        return True
    except Exception:
        return False


def clear_thumbnail(node_id: str) -> bool:
    """Remove thumbnail shared memory file.

    Args:
        node_id: Node's unique ID.

    Returns:
        True if removed, False otherwise.
    """
    shm_path = get_shm_path(node_id)

    try:
        shm_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def clear_all_thumbnails() -> int:
    """Remove all thumbnail shared memory files.

    Returns:
        Number of files removed.
    """
    import glob
    count = 0
    for path in glob.glob("/tmp/opencomp_thumb_*.shm"):
        try:
            pathlib.Path(path).unlink()
            count += 1
        except Exception:
            pass
    return count


class ThumbnailWidget:
    """Widget for displaying thumbnails in NodeGraphQt nodes.

    This is a lightweight wrapper that can be added to node classes.
    """

    def __init__(self, node_id: str):
        self._node_id = node_id
        self._pixmap: Optional[QPixmap] = None
        self._last_update = 0

    def update(self) -> bool:
        """Update thumbnail from shared memory.

        Returns:
            True if thumbnail was updated, False otherwise.
        """
        import time
        now = time.time()

        # Rate limit updates to 10Hz
        if now - self._last_update < 0.1:
            return False

        self._last_update = now
        new_pixmap = read_thumbnail(self._node_id)

        if new_pixmap is not None:
            self._pixmap = new_pixmap
            return True

        return False

    @property
    def pixmap(self) -> Optional[QPixmap]:
        """Get the current thumbnail pixmap."""
        return self._pixmap

    @property
    def is_available(self) -> bool:
        """Check if a thumbnail is available."""
        return self._pixmap is not None


# ── Blender-side helpers ────────────────────────────────────────────────────

def create_thumbnail_from_gpu_texture(node_id: str, texture) -> bool:
    """Create thumbnail from a Blender GPUTexture.

    This function is meant to be called from Blender to create
    thumbnails from evaluated node outputs.

    Args:
        node_id: Node's unique ID.
        texture: gpu.types.GPUTexture instance.

    Returns:
        True if successful, False otherwise.
    """
    try:
        import gpu
        import numpy as np

        # Read back texture to CPU
        width, height = texture.width, texture.height

        # Create framebuffer to read from
        fb = gpu.types.GPUFrameBuffer(color_slots=[texture])

        with fb.bind():
            # Read pixels
            buffer = fb.read_color(0, 0, width, height, 4, 0, 'FLOAT')

        # Convert to numpy array
        pixels = np.array(buffer)
        pixels = pixels.reshape((height, width, 4))

        # Flip Y (OpenGL has Y=0 at bottom)
        pixels = np.flipud(pixels)

        # Scale down to thumbnail size
        if width > THUMB_WIDTH or height > THUMB_HEIGHT:
            # Simple downscale by taking every Nth pixel
            scale_x = max(1, width // THUMB_WIDTH)
            scale_y = max(1, height // THUMB_HEIGHT)
            pixels = pixels[::scale_y, ::scale_x]

        # Clamp and convert to uint8
        pixels = np.clip(pixels * 255, 0, 255).astype(np.uint8)

        # Write to shared memory
        return write_thumbnail(
            node_id,
            pixels.shape[1],
            pixels.shape[0],
            pixels.tobytes()
        )

    except Exception as e:
        print(f"[OpenComp] Thumbnail creation failed: {e}")
        return False
