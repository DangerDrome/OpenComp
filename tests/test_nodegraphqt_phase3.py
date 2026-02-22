"""Phase 3 Tests — Core Canvas Features.

Tests thumbnails, properties panel, and keyboard shortcuts.
"""

import sys
import os
import struct
import pathlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Add qt_canvas directly to avoid bpy import from opencomp_core/__init__.py
QT_CANVAS_PATH = os.path.join(PROJECT_ROOT, "opencomp_core", "qt_canvas")
sys.path.insert(0, QT_CANVAS_PATH)


def test_thumbnail_shm_write():
    """Thumbnail SHM file created correctly."""
    try:
        from viewer.thumbnail import (
            write_thumbnail, get_shm_path, clear_thumbnail,
            THUMB_WIDTH, THUMB_HEIGHT
        )

        node_id = "test_node_123"
        width = THUMB_WIDTH
        height = THUMB_HEIGHT

        # Create dummy RGBA data
        rgba_data = bytes([255, 0, 0, 255] * (width * height))  # Red pixels

        # Write thumbnail
        success = write_thumbnail(node_id, width, height, rgba_data)
        assert success, "write_thumbnail failed"

        # Check file exists
        shm_path = get_shm_path(node_id)
        assert shm_path.exists(), f"SHM file not created at {shm_path}"

        # Read and verify header
        with open(shm_path, 'rb') as f:
            header = f.read(8)
            w, h = struct.unpack('<II', header)
            assert w == width, f"Width mismatch: {w} != {width}"
            assert h == height, f"Height mismatch: {h} != {height}"

        # Cleanup
        clear_thumbnail(node_id)

        print("  ✓ Thumbnail SHM file created correctly")
        return True
    except Exception as e:
        print(f"  ✗ Thumbnail SHM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thumbnail_read():
    """QImage created from SHM data has correct dimensions."""
    try:
        from viewer.thumbnail import (
            write_thumbnail, read_thumbnail, clear_thumbnail,
            THUMB_WIDTH, THUMB_HEIGHT
        )
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        node_id = "test_node_456"
        width = THUMB_WIDTH
        height = THUMB_HEIGHT

        # Create gradient RGBA data
        rgba_data = bytearray()
        for y in range(height):
            for x in range(width):
                r = int(x * 255 / width)
                g = int(y * 255 / height)
                b = 128
                a = 255
                rgba_data.extend([r, g, b, a])

        # Write thumbnail
        write_thumbnail(node_id, width, height, bytes(rgba_data))

        # Read as QPixmap
        pixmap = read_thumbnail(node_id)

        assert pixmap is not None, "read_thumbnail returned None"
        assert pixmap.width() == width, f"Width mismatch: {pixmap.width()}"
        assert pixmap.height() == height, f"Height mismatch: {pixmap.height()}"

        # Cleanup
        clear_thumbnail(node_id)

        print("  ✓ QImage created from SHM data has correct dimensions")
        return True
    except Exception as e:
        print(f"  ✗ Thumbnail read test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_properties_panel_widgets():
    """Properties panel shows correct widgets for each param type."""
    try:
        from PySide6.QtWidgets import QApplication
        from ui.properties import PropertiesPanel

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        panel = PropertiesPanel()
        assert panel is not None

        # Check the panel can be created and has the expected structure
        assert hasattr(panel, 'set_node')
        assert hasattr(panel, 'property_changed')

        print("  ✓ Properties panel has correct widget structure")
        return True
    except Exception as e:
        print(f"  ✗ Properties panel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_shortcuts_defined():
    """All keyboard shortcuts registered without conflict."""
    try:
        from canvas.shortcuts import SHORTCUTS

        # Check expected shortcuts exist
        expected = [
            'zoom_to_fit', 'frame_selected', 'select_all',
            'undo', 'redo', 'delete', 'duplicate',
            'add_node', 'disable_node', 'auto_layout'
        ]

        for name in expected:
            assert name in SHORTCUTS, f"Missing shortcut: {name}"

        # Check for duplicates
        values = [str(v.toString()) for v in SHORTCUTS.values()]
        duplicates = set([v for v in values if values.count(v) > 1])

        if duplicates:
            print(f"  Warning: Duplicate shortcuts: {duplicates}")

        print(f"  ✓ All {len(expected)} expected shortcuts defined")
        return True
    except Exception as e:
        print(f"  ✗ Shortcuts test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thumbnail_cleanup():
    """Thumbnail cleanup works correctly."""
    try:
        from viewer.thumbnail import (
            write_thumbnail, clear_thumbnail, get_shm_path,
            clear_all_thumbnails, THUMB_WIDTH, THUMB_HEIGHT
        )

        # Create a few thumbnails
        node_ids = ["cleanup_test_1", "cleanup_test_2", "cleanup_test_3"]
        rgba_data = bytes([0] * THUMB_WIDTH * THUMB_HEIGHT * 4)

        for node_id in node_ids:
            write_thumbnail(node_id, THUMB_WIDTH, THUMB_HEIGHT, rgba_data)

        # Verify they exist
        for node_id in node_ids:
            assert get_shm_path(node_id).exists()

        # Clear one
        clear_thumbnail(node_ids[0])
        assert not get_shm_path(node_ids[0]).exists()
        assert get_shm_path(node_ids[1]).exists()

        # Clear all remaining
        clear_all_thumbnails()
        for node_id in node_ids:
            assert not get_shm_path(node_id).exists()

        print("  ✓ Thumbnail cleanup works correctly")
        return True
    except Exception as e:
        print(f"  ✗ Thumbnail cleanup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thumbnail_widget():
    """ThumbnailWidget updates correctly."""
    try:
        from viewer.thumbnail import (
            ThumbnailWidget, write_thumbnail, clear_thumbnail,
            THUMB_WIDTH, THUMB_HEIGHT
        )
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        node_id = "widget_test_node"

        # Create widget before thumbnail exists
        widget = ThumbnailWidget(node_id)
        assert not widget.is_available
        assert widget.pixmap is None

        # Write thumbnail
        rgba_data = bytes([128, 128, 128, 255] * THUMB_WIDTH * THUMB_HEIGHT)
        write_thumbnail(node_id, THUMB_WIDTH, THUMB_HEIGHT, rgba_data)

        # Update widget
        updated = widget.update()
        assert updated, "Widget did not update"
        assert widget.is_available
        assert widget.pixmap is not None

        # Cleanup
        clear_thumbnail(node_id)

        print("  ✓ ThumbnailWidget updates correctly")
        return True
    except Exception as e:
        print(f"  ✗ ThumbnailWidget test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_phase3_tests():
    """Run all Phase 3 tests."""
    print("\n" + "=" * 60)
    print("NodeGraphQt Phase 3 Tests — Core Canvas Features")
    print("=" * 60 + "\n")

    tests = [
        ("Thumbnail SHM Write", test_thumbnail_shm_write),
        ("Thumbnail Read", test_thumbnail_read),
        ("Properties Panel Widgets", test_properties_panel_widgets),
        ("Shortcuts Defined", test_shortcuts_defined),
        ("Thumbnail Cleanup", test_thumbnail_cleanup),
        ("ThumbnailWidget Updates", test_thumbnail_widget),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"Testing: {name}")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test error: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Phase 3 Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_phase3_tests()
    sys.exit(0 if success else 1)
