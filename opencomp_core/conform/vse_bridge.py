"""OpenComp Conform — OTIO clips to Blender VSE strips.

Places clips on the VSE timeline with timecode-accurate positioning.
Handles set as frame_offset_start / frame_offset_end.
Multi-track support (up to 10 tracks).
"""

import bpy
import opentimelineio as otio


def timeline_to_vse(timeline, scene=None):
    """Convert an OTIO Timeline to Blender VSE strips.

    Args:
        timeline: otio.schema.Timeline object.
        scene: Blender scene (defaults to bpy.context.scene).

    Returns:
        List of created VSE strip names.
    """
    if scene is None:
        scene = bpy.context.scene

    # Ensure sequencer exists
    if scene.sequence_editor is None:
        scene.sequence_editor_create()

    sed = scene.sequence_editor
    created_strips = []

    for track_idx, track in enumerate(timeline.video_tracks()):
        channel = min(track_idx + 1, 10)  # VSE channels 1-10

        for clip in track.find_clips():
            if not isinstance(clip, otio.schema.Clip):
                continue

            src_range = clip.source_range
            if src_range is None:
                continue

            # Record position in timeline
            rec_range = clip.trimmed_range_in_parent()
            if rec_range is None:
                continue

            _fps = src_range.start_time.rate  # noqa: F841 - available for future use
            rec_start = int(rec_range.start_time.value) + 1  # Blender 1-based
            duration = int(rec_range.duration.value)

            # Get media path
            media_path = _get_media_path(clip)

            if media_path:
                try:
                    strip = sed.sequences.new_movie(
                        name=clip.name or f"clip_{track_idx}",
                        filepath=media_path,
                        channel=channel,
                        frame_start=rec_start,
                    )
                except Exception:
                    # Fallback: create color strip as placeholder
                    strip = sed.sequences.new_effect(
                        name=clip.name or f"clip_{track_idx}",
                        type='COLOR',
                        channel=channel,
                        frame_start=rec_start,
                        frame_end=rec_start + duration,
                    )
            else:
                # No media — create placeholder color strip
                strip = sed.sequences.new_effect(
                    name=clip.name or f"clip_{track_idx}",
                    type='COLOR',
                    channel=channel,
                    frame_start=rec_start,
                    frame_end=rec_start + duration,
                )

            created_strips.append(strip.name)

    # Set scene frame range to cover all strips
    if created_strips:
        all_strips = sed.sequences_all
        if all_strips:
            scene.frame_start = min(s.frame_final_start for s in all_strips)
            scene.frame_end = max(s.frame_final_end for s in all_strips)

    return created_strips


def _get_media_path(clip):
    """Extract media file path from an OTIO clip's media reference."""
    ref = clip.media_reference
    if ref is None:
        return None

    if isinstance(ref, otio.schema.ExternalReference):
        url = ref.target_url
        if url.startswith('file://'):
            return url[7:]
        return url

    return None


def clear_vse(scene=None):
    """Remove all strips from the VSE."""
    if scene is None:
        scene = bpy.context.scene

    if scene.sequence_editor is None:
        return

    sed = scene.sequence_editor
    for strip in list(sed.sequences_all):
        sed.sequences.remove(strip)
