"""OpenComp Conform — handle calculation.

Adds head and tail handles to each clip, clamped to the available
source media range. Never exceeds source in/out points.
"""

DEFAULT_HANDLES = 8  # frames


def calculate_handles(clips, head=DEFAULT_HANDLES, tail=DEFAULT_HANDLES):
    """Add handles to clip list.

    Args:
        clips: List of clip dicts from ingest.get_clips().
        head: Number of handle frames before cut point.
        tail: Number of handle frames after cut point.

    Returns:
        List of clip dicts with added keys:
            head_handles, tail_handles, src_in_with_handles,
            src_out_with_handles, total_frames
    """
    import opentimelineio as otio

    result = []
    for clip in clips:
        clip = dict(clip)  # copy

        otio_clip = clip.get('_otio_clip')
        src_range = otio_clip.source_range if otio_clip else None

        if src_range is None:
            clip['head_handles'] = 0
            clip['tail_handles'] = 0
            clip['src_in_with_handles'] = clip.get('src_tc_in', '00:00:00:00')
            clip['src_out_with_handles'] = clip.get('src_tc_out', '00:00:00:00')
            clip['total_frames'] = clip.get('duration_frames', 0)
            result.append(clip)
            continue

        fps = src_range.start_time.rate
        src_in = src_range.start_time
        src_out = src_in + src_range.duration

        # Get available range from media reference
        avail_range = None
        if otio_clip and otio_clip.media_reference:
            avail_range = getattr(
                otio_clip.media_reference, 'available_range', None
            )

        # Calculate clamped handles
        actual_head = head
        actual_tail = tail

        if avail_range is not None:
            avail_in = avail_range.start_time
            avail_out = avail_in + avail_range.duration

            # Clamp head: can't go before available start
            max_head = max(0, int((src_in - avail_in).value))
            actual_head = min(head, max_head)

            # Clamp tail: can't go past available end
            max_tail = max(0, int((avail_out - src_out).value))
            actual_tail = min(tail, max_tail)

        # New in/out with handles
        head_offset = otio.opentime.RationalTime(actual_head, fps)
        tail_offset = otio.opentime.RationalTime(actual_tail, fps)
        new_in = src_in - head_offset
        new_out = src_out + tail_offset

        clip['head_handles'] = actual_head
        clip['tail_handles'] = actual_tail
        clip['src_in_with_handles'] = otio.opentime.to_timecode(new_in)
        clip['src_out_with_handles'] = otio.opentime.to_timecode(new_out)
        clip['total_frames'] = clip.get('duration_frames', 0) + actual_head + actual_tail

        result.append(clip)

    return result
