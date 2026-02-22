"""Generate splash.png and splash_2x.png for the OpenComp app template.

Run via: ./blender/blender --background --python app_template/_generate_splash.py

Blender auto-discovers splash.png / splash_2x.png in app template directories.
Generates both sizes using numpy for pixel manipulation and OIIO for PNG output.

Design:
- Dark background (#1a1a1a)
- Teal accent line (#00b4d8)
- "OpenComp" title text, white, centered
- "Open Source VFX Compositor" subtitle, grey
- "v0.4.0" version label, bottom-right
"""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "app_template"

# Splash sizes — Blender expects exactly these
SPLASH_1X = (501, 282)   # (width, height)
SPLASH_2X = (1002, 564)


def _generate_splash_array(width, height):
    """Generate splash image as a numpy uint8 RGBA array (H, W, 4)."""
    import numpy as np

    img = np.zeros((height, width, 4), dtype=np.uint8)

    # Dark background #1a1a1a
    img[:, :, 0] = 26
    img[:, :, 1] = 26
    img[:, :, 2] = 26
    img[:, :, 3] = 255

    # Teal accent line (#00b4d8) — horizontal band near top
    accent_y_start = int(height * 0.12)
    accent_y_end = accent_y_start + max(2, int(height * 0.007))
    img[accent_y_start:accent_y_end, :, 0] = 0
    img[accent_y_start:accent_y_end, :, 1] = 180
    img[accent_y_start:accent_y_end, :, 2] = 216
    img[accent_y_start:accent_y_end, :, 3] = 255

    # Second accent line below title area
    accent2_y_start = int(height * 0.55)
    accent2_y_end = accent2_y_start + max(1, int(height * 0.004))
    img[accent2_y_start:accent2_y_end, :, 0] = 0
    img[accent2_y_start:accent2_y_end, :, 1] = 180
    img[accent2_y_start:accent2_y_end, :, 2] = 216
    img[accent2_y_start:accent2_y_end, :, 3] = 128  # semi-transparent feel via dimming

    # Render "OpenComp" title as block letters (simple bitmap approach)
    # Each letter is drawn as filled rectangles — no font dependency
    scale = width / 501.0

    _draw_text_block(img, "OPENCOMP", width // 2, int(height * 0.33),
                     char_w=int(14 * scale), char_h=int(22 * scale),
                     spacing=int(3 * scale),
                     color=(255, 255, 255, 255))

    # Subtitle
    _draw_text_block(img, "OPEN SOURCE VFX COMPOSITOR", width // 2, int(height * 0.50),
                     char_w=int(5 * scale), char_h=int(8 * scale),
                     spacing=int(2 * scale),
                     color=(153, 153, 153, 255))

    # Version label — bottom right
    _draw_text_block(img, "V0.4.0", int(width * 0.88), int(height * 0.90),
                     char_w=int(4 * scale), char_h=int(6 * scale),
                     spacing=int(1 * scale),
                     color=(100, 100, 100, 255))

    return img


# Simple 5x7 bitmap font for uppercase + digits + dot + space
_FONT = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    'J': ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'Q': ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01110", "10001", "10000", "01110", "00001", "10001", "01110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'Z': ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    '3': ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    '.': ["00000", "00000", "00000", "00000", "00000", "00000", "01100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def _draw_text_block(img, text, cx, cy, char_w, char_h, spacing, color):
    """Draw text centered at (cx, cy) using scaled bitmap font."""
    import numpy as np

    h, w = img.shape[:2]
    glyph_w = 5  # bitmap font is 5 columns
    glyph_h = 7  # bitmap font is 7 rows

    # Pixel scale per glyph cell
    sx = max(1, char_w // glyph_w)
    sy = max(1, char_h // glyph_h)

    total_w = len(text) * (glyph_w * sx + spacing) - spacing
    start_x = cx - total_w // 2
    start_y = cy - (glyph_h * sy) // 2

    for ci, ch in enumerate(text.upper()):
        glyph = _FONT.get(ch)
        if glyph is None:
            continue
        ox = start_x + ci * (glyph_w * sx + spacing)
        for row_i, row_str in enumerate(glyph):
            for col_i, pixel in enumerate(row_str):
                if pixel == '1':
                    px = ox + col_i * sx
                    py = start_y + row_i * sy
                    # Fill the scaled pixel block
                    y0 = max(0, py)
                    y1 = min(h, py + sy)
                    x0 = max(0, px)
                    x1 = min(w, px + sx)
                    if y0 < y1 and x0 < x1:
                        img[y0:y1, x0:x1] = color


def _write_png(filepath, img_array):
    """Write uint8 RGBA array to PNG using OIIO."""
    import OpenImageIO as oiio

    h, w = img_array.shape[:2]
    spec = oiio.ImageSpec(w, h, 4, oiio.UINT8)
    out = oiio.ImageOutput.create(str(filepath))
    if out is None:
        print(f"[OpenComp] ERROR: Could not create output for {filepath}")
        return False
    out.open(str(filepath), spec)
    out.write_image(img_array)
    out.close()
    return True


def main():
    import bpy
    bpy.utils.expose_bundled_modules()

    print("[OpenComp] Generating splash images...")

    # 1x splash
    w1, h1 = SPLASH_1X
    img1 = _generate_splash_array(w1, h1)
    path1 = OUTPUT_DIR / "splash.png"
    if _write_png(path1, img1):
        print(f"[OpenComp] splash.png saved ({w1}x{h1})")

    # 2x splash (HiDPI)
    w2, h2 = SPLASH_2X
    img2 = _generate_splash_array(w2, h2)
    path2 = OUTPUT_DIR / "splash_2x.png"
    if _write_png(path2, img2):
        print(f"[OpenComp] splash_2x.png saved ({w2}x{h2})")

    print("[OpenComp] Splash generation complete")


if __name__ == "__main__":
    main()
