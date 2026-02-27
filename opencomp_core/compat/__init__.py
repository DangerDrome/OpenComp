# OpenComp — Blender version compatibility shims
#
# This module provides version-specific API shims. Add helpers to blender_5x.py
# or blender_51.py as needed, and add them to __all__ in those files.
# They will be automatically re-exported here.

import bpy

BLENDER_VERSION = bpy.app.version  # e.g. (5, 0, 0)

# Re-export version-specific symbols
# Using __all__ in submodules to control what gets exported
if BLENDER_VERSION >= (5, 1, 0):
    from .blender_51 import *  # noqa: F401, F403
else:
    from .blender_5x import *  # noqa: F401, F403
