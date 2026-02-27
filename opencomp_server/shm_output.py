"""OpenComp Shared Memory Output — Zero-copy pixel transfer to Electron.

Uses POSIX shared memory (shm_open) to share GPU render results
with the Electron frontend without copying through the socket.

Architecture:
    1. Blender renders to GPUTexture
    2. Read pixels to numpy array (GPU → CPU, unavoidable)
    3. Write to shared memory (no copy if mmapped correctly)
    4. Electron maps the same shared memory and displays via WebGL
"""

import mmap
import struct
from typing import Optional, Tuple
import os

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Shared memory header format:
# - 4 bytes: width (uint32)
# - 4 bytes: height (uint32)
# - 4 bytes: channels (uint32)
# - 4 bytes: frame counter (uint32) - incremented each update
# - 4 bytes: flags (uint32) - reserved
# - 12 bytes: padding
# Total header: 32 bytes

HEADER_SIZE = 32
HEADER_FORMAT = '<5I12x'  # 5 uint32s + 12 bytes padding


class SharedMemoryOutput:
    """Shared memory buffer for viewer output."""

    def __init__(self, name: str = "/opencomp_viewer", max_size: int = 4096 * 4096 * 4 * 4):
        """Initialize shared memory output.

        Args:
            name: Shared memory name (must start with /).
            max_size: Maximum buffer size in bytes (header + pixels).
        """
        self.name = name
        self.max_size = max_size + HEADER_SIZE
        self._fd: Optional[int] = None
        self._mmap: Optional[mmap.mmap] = None
        self._frame_counter = 0

    def create(self):
        """Create the shared memory region."""
        import posix_ipc

        # Remove existing if present
        try:
            posix_ipc.unlink_shared_memory(self.name)
        except posix_ipc.ExistentialError:
            pass

        # Create new shared memory
        shm = posix_ipc.SharedMemory(
            self.name,
            flags=posix_ipc.O_CREAT | posix_ipc.O_EXCL,
            size=self.max_size,
        )
        self._fd = shm.fd

        # Memory map it
        self._mmap = mmap.mmap(
            self._fd,
            self.max_size,
            mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE,
        )

        # Initialize header
        self._write_header(0, 0, 0)
        print(f"[SHM] Created shared memory: {self.name} ({self.max_size} bytes)")

    def create_fallback(self):
        """Create shared memory using fallback method (no posix_ipc)."""
        # Use /dev/shm directly on Linux
        shm_path = f"/dev/shm{self.name}"

        # Create and size the file
        self._fd = os.open(shm_path, os.O_CREAT | os.O_RDWR, 0o666)
        os.ftruncate(self._fd, self.max_size)

        # Memory map it
        self._mmap = mmap.mmap(
            self._fd,
            self.max_size,
            mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE,
        )

        # Initialize header
        self._write_header(0, 0, 0)
        print(f"[SHM] Created shared memory (fallback): {shm_path}")

    def close(self):
        """Close and unlink the shared memory."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None

        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

        # Try to unlink
        try:
            import posix_ipc
            posix_ipc.unlink_shared_memory(self.name)
        except Exception:
            # Fallback: remove file directly
            shm_path = f"/dev/shm{self.name}"
            try:
                os.unlink(shm_path)
            except Exception:
                pass

        print(f"[SHM] Closed shared memory: {self.name}")

    def _write_header(self, width: int, height: int, channels: int):
        """Write the header to shared memory."""
        if not self._mmap:
            return

        header = struct.pack(
            HEADER_FORMAT,
            width,
            height,
            channels,
            self._frame_counter,
            0,  # flags
        )
        self._mmap.seek(0)
        self._mmap.write(header)

    def write_pixels(self, pixels: 'np.ndarray', width: int, height: int, channels: int = 4):
        """Write pixel data to shared memory.

        Args:
            pixels: Numpy array of pixel data (float32, already flattened or will be).
            width: Image width.
            height: Image height.
            channels: Number of channels (default 4 for RGBA).
        """
        if not self._mmap or not HAS_NUMPY:
            return

        # Check size
        pixel_bytes = width * height * channels * 4  # float32
        if pixel_bytes + HEADER_SIZE > self.max_size:
            print(f"[SHM] Image too large: {width}x{height}x{channels}")
            return

        # Update frame counter
        self._frame_counter += 1

        # Write header
        self._write_header(width, height, channels)

        # Write pixels
        self._mmap.seek(HEADER_SIZE)
        pixel_data = pixels.astype(np.float32).tobytes()
        self._mmap.write(pixel_data)

    def write_from_gpu_texture(self, texture, source_node: str = None) -> Tuple[int, int]:
        """Write pixels directly from a GPUTexture.

        Args:
            texture: Blender gpu.types.GPUTexture
            source_node: Optional name of the source node (for cached pixels lookup)

        Returns:
            (width, height) tuple.
        """
        if not self._mmap or not HAS_NUMPY:
            return (0, 0)

        width = texture.width
        height = texture.height

        # Try to use cached pixels first (workaround for GPU readback issues in headless mode)
        if source_node:
            try:
                from opencomp_core.node_graph.tree import _node_pixels
                if source_node in _node_pixels:
                    cached_w, cached_h, cached_pixels = _node_pixels[source_node]
                    if cached_w == width and cached_h == height:
                        print(f"[SHM] Using cached pixels from {source_node}: {cached_w}x{cached_h}")
                        # Cached pixels are already in top-to-bottom order (OIIO convention)
                        # SHM expects top-to-bottom, so no flip needed
                        pixels = np.ascontiguousarray(cached_pixels, dtype=np.float32)

                        # Sample pixel for debug
                        mid_y, mid_x = height // 2, width // 2
                        sample = pixels[mid_y, mid_x, :]
                        print(f"[SHM Cached] Sample [{mid_y},{mid_x}]: R={sample[0]:.4f} G={sample[1]:.4f} B={sample[2]:.4f} A={sample[3]:.4f}")

                        # Flatten and write
                        pixels = pixels.flatten()
                        self.write_pixels(pixels, width, height, 4)
                        return (width, height)
            except ImportError:
                pass
            except Exception as e:
                print(f"[SHM] Cached pixels error: {e}")

        # Fallback to GPU readback
        buffer = texture.read()

        # Debug: Check buffer info
        print(f"[SHM Debug] Buffer type: {type(buffer)}, len: {len(buffer)}")

        # texture.read() returns a nested Buffer structure, not flat floats
        # First convert without forcing dtype to preserve structure
        raw_array = np.array(buffer)
        print(f"[SHM Debug] Raw array shape: {raw_array.shape}, dtype: {raw_array.dtype}")

        # Now ensure float32 and correct shape
        if raw_array.shape == (height, width, 4):
            # Already correct shape
            pixels = raw_array.astype(np.float32)
        elif raw_array.ndim == 1 and raw_array.size == height * width * 4:
            # Flat array - reshape it
            pixels = raw_array.astype(np.float32).reshape(height, width, 4)
        else:
            # Try to interpret as flat and reshape
            pixels = raw_array.flatten().astype(np.float32).reshape(height, width, 4)

        print(f"[SHM Debug] Pixels shape: {pixels.shape}, dtype: {pixels.dtype}")

        # Sample pixel before flip
        mid_y, mid_x = height // 2, width // 2
        sample_before = pixels[mid_y, mid_x, :].copy()
        print(f"[SHM Debug] Sample before flip [{mid_y},{mid_x}]: R={sample_before[0]:.4f} G={sample_before[1]:.4f} B={sample_before[2]:.4f} A={sample_before[3]:.4f}")

        # Flip Y-axis: GPU textures are stored bottom-to-top (OpenGL convention)
        # but image display expects top-to-bottom
        pixels = np.flipud(pixels)

        # CRITICAL: Ensure contiguous after flip (flipud creates a view with negative stride)
        pixels = np.ascontiguousarray(pixels, dtype=np.float32)

        print(f"[SHM Debug] After flip - contiguous: {pixels.flags['C_CONTIGUOUS']}, strides: {pixels.strides}")

        # Flatten back for writing
        pixels = pixels.flatten()

        # Write to shared memory
        self.write_pixels(pixels, width, height, 4)

        return (width, height)


# ── Module-level instance ───────────────────────────────────────────────────

_shm_output: Optional[SharedMemoryOutput] = None


def get_shm_output() -> Optional[SharedMemoryOutput]:
    """Get the global shared memory output instance."""
    return _shm_output


def create_shm_output(name: str = "/opencomp_viewer") -> SharedMemoryOutput:
    """Create the global shared memory output instance."""
    global _shm_output

    if _shm_output is not None:
        return _shm_output

    _shm_output = SharedMemoryOutput(name)

    # Try posix_ipc first, fall back to /dev/shm
    try:
        _shm_output.create()
    except ImportError:
        _shm_output.create_fallback()

    return _shm_output


def close_shm_output():
    """Close the global shared memory output instance."""
    global _shm_output
    if _shm_output:
        _shm_output.close()
        _shm_output = None
