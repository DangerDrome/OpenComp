"""OpenComp Conform — workspace UI panel and operators.

Shot list panel showing event, reel, source TC, duration, match status.
Operators: Ingest EDL, Match Media, Generate Structure, Export .nk Scripts.
"""

import bpy
import pathlib


# ── PropertyGroup for conform state ────────────────────────────────────

class OpenCompConformSettings(bpy.types.PropertyGroup):
    """Conform tool settings stored on Scene."""

    edl_filepath: bpy.props.StringProperty(
        name="EDL File", subtype='FILE_PATH', default="",
        description="Path to EDL/AAF/XML file",
    )
    media_root: bpy.props.StringProperty(
        name="Media Root", subtype='DIR_PATH', default="",
        description="Root directory to search for source media",
    )
    output_root: bpy.props.StringProperty(
        name="Output Root", subtype='DIR_PATH', default="",
        description="Root directory for generated shot folders",
    )
    sequence_name: bpy.props.StringProperty(
        name="Sequence", default="SEQ010",
        description="Sequence name token",
    )
    fps: bpy.props.FloatProperty(
        name="FPS", default=24.0, min=1.0, max=120.0,
        description="Timeline frame rate",
    )
    head_handles: bpy.props.IntProperty(
        name="Head Handles", default=8, min=0, max=100,
        description="Handle frames before cut point",
    )
    tail_handles: bpy.props.IntProperty(
        name="Tail Handles", default=8, min=0, max=100,
        description="Handle frames after cut point",
    )


# ── Module-level conform state ─────────────────────────────────────────

_conform_state = {
    "timeline": None,
    "clips": [],
    "matched": [],
    "unmatched": [],
    "shot_dirs": [],
}


# ── Operators ──────────────────────────────────────────────────────────

class OC_OT_conform_ingest(bpy.types.Operator):
    """Ingest EDL/AAF/XML into timeline"""
    bl_idname = "oc.conform_ingest"
    bl_label = "Ingest EDL"

    def execute(self, context):
        settings = context.scene.oc_conform
        filepath = bpy.path.abspath(settings.edl_filepath)

        if not filepath or not pathlib.Path(filepath).exists():
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        from . import ingest
        try:
            timeline = ingest.ingest_auto(filepath, fps=settings.fps)
            clips = ingest.get_clips(timeline)

            _conform_state["timeline"] = timeline
            _conform_state["clips"] = clips
            _conform_state["matched"] = []
            _conform_state["unmatched"] = []

            self.report({'INFO'}, f"Ingested {len(clips)} clips")
        except Exception as e:
            self.report({'ERROR'}, f"Ingest failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class OC_OT_conform_match(bpy.types.Operator):
    """Match clips to source media on disk"""
    bl_idname = "oc.conform_match"
    bl_label = "Match Media"

    def execute(self, context):
        settings = context.scene.oc_conform
        media_root = bpy.path.abspath(settings.media_root)

        if not media_root or not pathlib.Path(media_root).is_dir():
            self.report({'ERROR'}, f"Media root not found: {media_root}")
            return {'CANCELLED'}

        clips = _conform_state.get("clips", [])
        if not clips:
            self.report({'WARNING'}, "No clips ingested yet")
            return {'CANCELLED'}

        from . import matcher
        media_files = matcher.find_media_files(media_root)
        matched, unmatched = matcher.match_clips(clips, media_files)

        _conform_state["matched"] = matched
        _conform_state["unmatched"] = unmatched

        self.report(
            {'INFO'},
            f"Matched {len(matched)}/{len(clips)} clips "
            f"({len(unmatched)} unmatched)",
        )
        return {'FINISHED'}


class OC_OT_conform_structure(bpy.types.Operator):
    """Generate shot folder structure"""
    bl_idname = "oc.conform_structure"
    bl_label = "Generate Structure"

    def execute(self, context):
        settings = context.scene.oc_conform
        output_root = bpy.path.abspath(settings.output_root)

        if not output_root:
            self.report({'ERROR'}, "Output root not set")
            return {'CANCELLED'}

        clips = _conform_state.get("clips", [])
        if not clips:
            self.report({'WARNING'}, "No clips ingested yet")
            return {'CANCELLED'}

        from . import structure
        shot_dirs = structure.generate_structure(
            output_root, clips,
            sequence=settings.sequence_name,
        )
        _conform_state["shot_dirs"] = shot_dirs

        self.report({'INFO'}, f"Created {len(shot_dirs)} shot directories")
        return {'FINISHED'}


class OC_OT_conform_export_nk(bpy.types.Operator):
    """Export Nuke scripts for all shots"""
    bl_idname = "oc.conform_export_nk"
    bl_label = "Export .nk Scripts"

    def execute(self, context):
        settings = context.scene.oc_conform
        output_root = bpy.path.abspath(settings.output_root)

        clips = _conform_state.get("clips", [])
        if not clips:
            self.report({'WARNING'}, "No clips ingested yet")
            return {'CANCELLED'}

        from . import handles, nk_export, structure

        # Add handles
        clips_with_handles = handles.calculate_handles(
            clips,
            head=settings.head_handles,
            tail=settings.tail_handles,
        )

        exported = 0
        for clip in clips_with_handles:
            paths = structure.get_shot_paths(
                output_root, clip, sequence=settings.sequence_name,
            )
            shot_dir = paths["root"]
            shot_dir.mkdir(parents=True, exist_ok=True)

            nk_export.export_nk_for_clip(
                clip, shot_dir, sequence=settings.sequence_name,
            )
            exported += 1

        self.report({'INFO'}, f"Exported {exported} .nk scripts")
        return {'FINISHED'}


# ── Panel ──────────────────────────────────────────────────────────────

class OC_PT_conform(bpy.types.Panel):
    """OpenComp Conform panel."""
    bl_idname = "OC_PT_conform"
    bl_label = "Conform"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "OpenComp"

    def draw(self, context):
        layout = self.layout

        try:
            settings = context.scene.oc_conform
        except AttributeError:
            layout.label(text="Conform not initialised")
            return

        # File paths
        layout.prop(settings, "edl_filepath")
        layout.prop(settings, "media_root")
        layout.prop(settings, "output_root")

        layout.separator()

        # Settings
        row = layout.row(align=True)
        row.prop(settings, "sequence_name")
        row.prop(settings, "fps")

        row = layout.row(align=True)
        row.prop(settings, "head_handles")
        row.prop(settings, "tail_handles")

        layout.separator()

        # Action buttons
        col = layout.column(align=True)
        col.operator("oc.conform_ingest", icon='IMPORT')
        col.operator("oc.conform_match", icon='VIEWZOOM')
        col.operator("oc.conform_structure", icon='FILE_FOLDER')
        col.operator("oc.conform_export_nk", icon='EXPORT')

        layout.separator()

        # Shot list
        clips = _conform_state.get("clips", [])
        matched = _conform_state.get("matched", [])
        unmatched = _conform_state.get("unmatched", [])

        if clips:
            layout.label(
                text=f"Clips: {len(clips)} total, "
                     f"{len(matched)} matched, "
                     f"{len(unmatched)} unmatched",
            )

            box = layout.box()
            for clip in clips[:20]:  # Show first 20
                row = box.row()
                # Match status icon
                is_matched = any(
                    m.get('clip_name') == clip.get('clip_name')
                    for m in matched
                )
                icon = 'CHECKMARK' if is_matched else 'ERROR'
                row.label(text=f"E{clip.get('event', '?'):03d}", icon=icon)
                row.label(text=clip.get('reel', '-'))
                row.label(text=clip.get('src_tc_in', '-'))
                row.label(text=f"{clip.get('duration_frames', 0)}f")

            if len(clips) > 20:
                layout.label(text=f"... and {len(clips) - 20} more")


# ── Registration ───────────────────────────────────────────────────────

_classes = [
    OpenCompConformSettings,
    OC_OT_conform_ingest,
    OC_OT_conform_match,
    OC_OT_conform_structure,
    OC_OT_conform_export_nk,
    OC_PT_conform,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.oc_conform = bpy.props.PointerProperty(
        type=OpenCompConformSettings
    )


def unregister():
    try:
        del bpy.types.Scene.oc_conform
    except (AttributeError, RuntimeError):
        pass
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
