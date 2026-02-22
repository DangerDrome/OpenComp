"""OpenComp Conform — token-based folder hierarchy generator.

Tokens: {sequence} {shot} {version} {fps} {resolution} {ext}
Creates per-shot directory structure for plates, comp, and render.
"""

import pathlib


DEFAULT_TEMPLATE = "{sequence}/{shot}"

# Subdirectories created for each shot
_SHOT_SUBDIRS = ["plates", "comp", "render"]


def generate_structure(output_root, clips, sequence="SEQ010",
                       version="v001", fps="24", resolution="1920x1080",
                       ext="exr", template=DEFAULT_TEMPLATE):
    """Create folder hierarchy for a list of clips.

    Args:
        output_root: Base directory for output.
        clips: List of clip dicts (must have 'clip_name').
        sequence: Sequence name token.
        version: Version token.
        fps: FPS token.
        resolution: Resolution token.
        ext: File extension token.
        template: Path template with {tokens}.

    Returns:
        List of created shot directory paths.
    """
    output_root = pathlib.Path(output_root)
    created = []

    for clip in clips:
        shot = clip.get('clip_name', 'unknown')

        # Expand tokens
        shot_rel = template.format(
            sequence=sequence,
            shot=shot,
            version=version,
            fps=fps,
            resolution=resolution,
            ext=ext,
        )

        shot_dir = output_root / shot_rel

        # Create shot subdirectories
        for subdir in _SHOT_SUBDIRS:
            (shot_dir / subdir).mkdir(parents=True, exist_ok=True)

        created.append(shot_dir)

    return created


def get_shot_paths(output_root, clip, sequence="SEQ010",
                   template=DEFAULT_TEMPLATE):
    """Get the directory paths for a single shot.

    Returns dict with keys: root, plates, comp, render
    """
    output_root = pathlib.Path(output_root)
    shot = clip.get('clip_name', 'unknown')

    shot_rel = template.format(
        sequence=sequence,
        shot=shot,
        version="v001", fps="24", resolution="1920x1080", ext="exr",
    )

    shot_dir = output_root / shot_rel
    return {
        "root": shot_dir,
        "plates": shot_dir / "plates",
        "comp": shot_dir / "comp",
        "render": shot_dir / "render",
    }
