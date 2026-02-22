"""OpenComp Conform — ingest EDL/AAF/XML into OTIO timeline.

Primary EDL parser: pycmx (always available).
OTIO used as the canonical timeline model and for .otio/.aaf formats.

Returns an opentimelineio.schema.Timeline object.
"""

import pathlib
import opentimelineio as otio


def ingest_edl(filepath, fps=24.0):
    """Parse a CMX 3600 EDL file into an OTIO Timeline.

    Uses pycmx to parse the EDL, then builds an OTIO Timeline from
    the parsed events.

    Args:
        filepath: Path to the EDL file.
        fps: Frame rate for timecode interpretation.

    Returns:
        otio.schema.Timeline
    """
    filepath = str(filepath)

    # Try OTIO's built-in CMX adapter first (available in some versions)
    try:
        timeline = otio.adapters.read_from_file(
            filepath, adapter_name="cmx_3600", rate=fps,
        )
        return timeline
    except Exception:
        pass

    # Primary path: use pycmx
    return _ingest_edl_pycmx(filepath, fps)


def _ingest_edl_pycmx(filepath, fps):
    """Parse EDL using pycmx and build OTIO Timeline.

    pycmx structure: edl.events → Event objects with .edits (list of Edit).
    Each Edit has: source_in, source_out, record_in, record_out (strings),
    source (reel), clip_name.
    """
    import pycmx

    edl = pycmx.parse_cmx3600(open(filepath))

    timeline = otio.schema.Timeline(name="Conform")
    track = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    timeline.tracks.append(track)

    for event in edl.events:
        if not event.edits:
            continue

        for edit in event.edits:
            # Skip black/filler
            if edit.black:
                continue

            src_in = _tc_to_rational(str(edit.source_in), fps)
            src_out = _tc_to_rational(str(edit.source_out), fps)
            duration = src_out - src_in

            clip_name = edit.clip_name or ""
            if not clip_name:
                clip_name = f"clip_{event.number:03d}"

            reel = str(edit.source) if edit.source else ""

            media_ref = otio.schema.MissingReference()
            media_ref.metadata['cmx_3600'] = {'reel': reel}

            clip = otio.schema.Clip(
                name=clip_name,
                media_reference=media_ref,
                source_range=otio.opentime.TimeRange(
                    start_time=src_in,
                    duration=duration,
                ),
            )

            track.append(clip)

    return timeline


def ingest_aaf(filepath):
    """Parse an AAF file into an OTIO Timeline.

    Args:
        filepath: Path to the AAF file.

    Returns:
        otio.schema.Timeline
    """
    filepath = str(filepath)
    timeline = otio.adapters.read_from_file(filepath)
    return timeline


def ingest_xml(filepath):
    """Parse an FCP XML file into an OTIO Timeline.

    Args:
        filepath: Path to the XML file.

    Returns:
        otio.schema.Timeline
    """
    filepath = str(filepath)
    timeline = otio.adapters.read_from_file(filepath)
    return timeline


def ingest_auto(filepath, fps=24.0):
    """Auto-detect format and parse into OTIO Timeline.

    Supported: .edl, .aaf, .xml, .fcpxml, .otio
    """
    filepath = pathlib.Path(filepath)
    ext = filepath.suffix.lower()

    if ext == '.edl':
        return ingest_edl(filepath, fps=fps)
    elif ext == '.aaf':
        return ingest_aaf(filepath)
    elif ext in ('.xml', '.fcpxml'):
        return ingest_xml(filepath)
    elif ext == '.otio':
        return otio.adapters.read_from_file(str(filepath))
    else:
        raise ValueError(f"Unsupported conform format: {ext}")


def get_clips(timeline):
    """Extract all clips from a timeline, flattened across tracks.

    Returns list of dicts with keys:
        event, reel, clip_name, src_tc_in, src_tc_out,
        rec_tc_in, rec_tc_out, duration_frames, track
    """
    clips = []
    event_num = 1

    for track_idx, track in enumerate(timeline.video_tracks()):
        for clip in track.find_clips():
            if not isinstance(clip, otio.schema.Clip):
                continue

            src_range = clip.source_range
            if src_range is None:
                continue

            fps = src_range.start_time.rate

            src_in = src_range.start_time
            src_out = src_in + src_range.duration
            duration_frames = int(src_range.duration.value)

            # Reel name from media reference metadata
            reel = ""
            if clip.media_reference and hasattr(clip.media_reference, 'metadata'):
                meta = clip.media_reference.metadata
                if isinstance(meta, dict):
                    reel = meta.get('cmx_3600', {}).get('reel', '')
                else:
                    # OTIO AnyDictionary — try attribute access
                    try:
                        reel = meta.get('cmx_3600', {}).get('reel', '')
                    except Exception:
                        pass
            if not reel:
                reel = getattr(clip.media_reference, 'name', '') or ''

            # Record timecode (trim range in parent)
            rec_range = clip.trimmed_range_in_parent()
            rec_in = rec_range.start_time if rec_range else src_in
            rec_out = (rec_in + rec_range.duration) if rec_range else src_out

            clips.append({
                "event": event_num,
                "reel": reel,
                "clip_name": clip.name or f"clip_{event_num:03d}",
                "src_tc_in": _tc_string(src_in),
                "src_tc_out": _tc_string(src_out),
                "rec_tc_in": _tc_string(rec_in),
                "rec_tc_out": _tc_string(rec_out),
                "duration_frames": duration_frames,
                "track": track_idx + 1,
                "_otio_clip": clip,  # keep reference for downstream
            })
            event_num += 1

    return clips


def _tc_to_rational(tc_str, fps):
    """Convert timecode string HH:MM:SS:FF to OTIO RationalTime."""
    parts = tc_str.replace(';', ':').split(':')
    if len(parts) == 4:
        h, m, s, f = [int(p) for p in parts]
        total_frames = ((h * 3600 + m * 60 + s) * fps) + f
        return otio.opentime.RationalTime(total_frames, fps)
    # Fallback: try as frame number
    return otio.opentime.RationalTime(float(tc_str), fps)


def _tc_string(rational_time):
    """Convert OTIO RationalTime to HH:MM:SS:FF timecode string."""
    try:
        return otio.opentime.to_timecode(rational_time)
    except Exception:
        return f"{int(rational_time.value)}f"
