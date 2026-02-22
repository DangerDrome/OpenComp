"""OpenComp Viewer sidebar panel — display controls in the 3D viewport.

Provides gain, gamma, channel isolation, false colour, clipping controls
in the VIEW_3D sidebar under the "OpenComp" tab.
"""

import bpy


class OC_PT_viewer(bpy.types.Panel):
    """OpenComp viewer controls panel."""

    bl_idname = "OC_PT_viewer"
    bl_label = "Viewer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OpenComp"

    def draw(self, context):
        layout = self.layout

        try:
            settings = context.scene.oc_viewer
        except AttributeError:
            layout.label(text="Viewer not initialised")
            return

        # Proxy (pipeline-level setting, at the top)
        row = layout.row(align=True)
        row.label(text="Proxy:")
        row.prop(settings, "proxy", text="")

        layout.separator()

        # Gain / Gamma
        col = layout.column(align=True)
        col.prop(settings, "gain")
        col.prop(settings, "gamma")

        layout.separator()

        # Channel isolation
        layout.label(text="Channel:")
        row = layout.row(align=True)
        row.prop(settings, "channel_mode", expand=True)

        layout.separator()

        # False colour + clipping
        row = layout.row(align=True)
        row.prop(settings, "false_color", toggle=True)
        row.prop(settings, "clipping", toggle=True)

        layout.separator()

        # Background
        layout.label(text="Background:")
        row = layout.row(align=True)
        row.prop(settings, "bg_mode", expand=True)
        if settings.bg_mode == 'CUSTOM':
            layout.prop(settings, "bg_custom_color", text="")

        layout.separator()

        # Navigation controls
        layout.operator("oc.viewer_reset", text="Reset View", icon='HOME')


def register():
    bpy.utils.register_class(OC_PT_viewer)


def unregister():
    try:
        bpy.utils.unregister_class(OC_PT_viewer)
    except RuntimeError:
        pass
