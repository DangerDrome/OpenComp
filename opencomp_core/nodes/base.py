"""OpenComp base node class — all compositor nodes inherit from this.

Subclasses must:
  - Set bl_idname = "OC_N_<name>"
  - Set bl_label
  - Implement evaluate(texture_pool) → GPUTexture or None
  - Define inputs/outputs in init(context)
"""

import bpy


class OpenCompNode(bpy.types.Node):
    """Base class for all OpenComp compositor nodes."""

    bl_idname = "OC_N_base"
    bl_label = "OpenComp Base"

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == "OC_NT_compositor"

    def init(self, context):
        """Initialize node - collapsed by default."""
        self.hide = True

    def evaluate(self, texture_pool):
        """Evaluate this node and return output GPUTexture.

        Must be overridden by subclasses.
        Returns None if evaluation fails or no output.
        """
        raise NotImplementedError
