# OpenComp — Blender version compatibility shims

import bpy

BLENDER_VERSION = bpy.app.version  # e.g. (5, 0, 0)

if BLENDER_VERSION >= (5, 1, 0):
    from .blender_51 import *
else:
    from .blender_5x import *
