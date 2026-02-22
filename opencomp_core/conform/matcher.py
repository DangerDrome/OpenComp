"""OpenComp Conform — match offline clips to source media on disk.

Match priority:
  1. Reel name in filename
  2. Source timecode overlap
  3. Clip name in filename

Returns matched and unmatched clip lists for the UI to display.
"""

import pathlib
import re

# Media file extensions to search
_MEDIA_EXTS = {
    '.exr', '.dpx', '.tiff', '.tif', '.png', '.jpg', '.jpeg',
    '.mov', '.mp4', '.mxf', '.avi', '.r3d',
}


def find_media_files(search_root, recursive=True):
    """Scan a directory for media files.

    Args:
        search_root: Root directory to search.
        recursive: Whether to search subdirectories.

    Returns:
        List of pathlib.Path objects.
    """
    search_root = pathlib.Path(search_root)
    if not search_root.is_dir():
        return []

    files = []
    pattern = '**/*' if recursive else '*'
    for path in search_root.glob(pattern):
        if path.is_file() and path.suffix.lower() in _MEDIA_EXTS:
            files.append(path)
    return files


def match_clips(clips, media_files):
    """Match clips to source media files.

    Args:
        clips: List of clip dicts from ingest.get_clips().
        media_files: List of pathlib.Path objects from find_media_files().

    Returns:
        (matched, unmatched) — two lists of clip dicts.
        Matched clips get a 'media_path' key added.
    """
    # Build lookup: lowercase filename stem → path
    file_stems = {}
    for f in media_files:
        # Strip frame number padding: name.0001.exr → name
        stem = _strip_frame_number(f.stem).lower()
        if stem not in file_stems:
            file_stems[stem] = f

    # Also index by full filename
    file_names = {f.name.lower(): f for f in media_files}

    matched = []
    unmatched = []

    for clip in clips:
        media_path = _try_match(clip, file_stems, file_names, media_files)
        if media_path:
            clip = dict(clip)  # copy to avoid mutating original
            clip['media_path'] = str(media_path)
            matched.append(clip)
        else:
            clip = dict(clip)
            clip['media_path'] = None
            unmatched.append(clip)

    return matched, unmatched


def _try_match(clip, file_stems, file_names, media_files):
    """Try to match a single clip. Returns path or None."""
    reel = (clip.get('reel') or '').strip().lower()
    clip_name = (clip.get('clip_name') or '').strip().lower()

    # Priority 1: reel name matches filename stem
    if reel and reel in file_stems:
        return file_stems[reel]

    # Priority 2: reel name is substring of any filename
    if reel:
        for stem, path in file_stems.items():
            if reel in stem:
                return path

    # Priority 3: clip name matches filename stem
    if clip_name and clip_name in file_stems:
        return file_stems[clip_name]

    # Priority 4: clip name is substring of any filename
    if clip_name:
        for stem, path in file_stems.items():
            if clip_name in stem:
                return path

    return None


def _strip_frame_number(stem):
    """Strip trailing frame number padding from a filename stem.

    Examples:
        'plate.0001' → 'plate'
        'SH010_src.1001' → 'SH010_src'
        'simple' → 'simple'
    """
    # Remove trailing .NNNN or _NNNN
    return re.sub(r'[._]\d{3,}$', '', stem)
