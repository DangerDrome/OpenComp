"""
Phase 6 tests — Conform Tool: ingest, matcher, handles, structure,
nk_export, vse_bridge, UI.
Must be run inside Blender: ./blender/blender --background --python tests/run_tests.py
All tests must pass before Phase 7 begins.
"""

import pathlib
import sys
import tempfile
import os

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ── Helpers ───────────────────────────────────────────────────────────

_SAMPLE_EDL = """\
TITLE: TEST_CONFORM
FCM: NON-DROP FRAME

001  REEL01   V     C        01:00:00:00 01:00:02:00 01:00:00:00 01:00:02:00
* FROM CLIP NAME: SH010

002  REEL02   V     C        01:00:05:00 01:00:08:00 01:00:02:00 01:00:05:00
* FROM CLIP NAME: SH020

003  REEL03   V     C        01:00:10:00 01:00:12:12 01:00:05:00 01:00:07:12
* FROM CLIP NAME: SH030
"""


def _write_sample_edl(directory):
    """Write a sample EDL for testing."""
    edl_path = pathlib.Path(directory) / "test.edl"
    edl_path.write_text(_SAMPLE_EDL)
    return edl_path


def run(test):

    # ── Dependencies available ────────────────────────────────────────

    def check_otio_available():
        import opentimelineio as otio
        assert otio.__version__, "OTIO version not available"

    def check_pycmx_available():
        import pycmx
        assert pycmx is not None

    def check_timecode_available():
        import timecode
        assert timecode is not None

    # ── Ingest module ─────────────────────────────────────────────────

    def check_ingest_module():
        from opencomp_core.conform.ingest import (
            ingest_edl, ingest_auto, get_clips,
        )
        assert callable(ingest_edl)
        assert callable(ingest_auto)
        assert callable(get_clips)

    def check_ingest_edl_roundtrip():
        from opencomp_core.conform.ingest import ingest_edl, get_clips

        with tempfile.TemporaryDirectory() as tmpdir:
            edl_path = _write_sample_edl(tmpdir)
            timeline = ingest_edl(edl_path, fps=24.0)
            assert timeline is not None, "Timeline is None"

            clips = get_clips(timeline)
            assert len(clips) >= 2, \
                f"Expected at least 2 clips, got {len(clips)}"

            # Verify clip structure
            clip = clips[0]
            assert 'event' in clip, "Clip missing 'event'"
            assert 'clip_name' in clip, "Clip missing 'clip_name'"
            assert 'duration_frames' in clip, "Clip missing 'duration_frames'"
            assert 'src_tc_in' in clip, "Clip missing 'src_tc_in'"
            assert clip['duration_frames'] > 0, "Duration should be > 0"

    # ── Matcher module ────────────────────────────────────────────────

    def check_matcher_module():
        from opencomp_core.conform.matcher import (
            find_media_files, match_clips,
        )
        assert callable(find_media_files)
        assert callable(match_clips)

    def check_matcher_find_and_match():
        from opencomp_core.conform.matcher import find_media_files, match_clips

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake media files
            (pathlib.Path(tmpdir) / "REEL01.0001.exr").touch()
            (pathlib.Path(tmpdir) / "REEL02.0001.exr").touch()
            (pathlib.Path(tmpdir) / "unrelated.mov").touch()

            media_files = find_media_files(tmpdir, recursive=False)
            assert len(media_files) >= 2, \
                f"Expected at least 2 media files, got {len(media_files)}"

            # Create fake clips
            clips = [
                {"event": 1, "reel": "REEL01", "clip_name": "SH010"},
                {"event": 2, "reel": "REEL02", "clip_name": "SH020"},
                {"event": 3, "reel": "REEL99", "clip_name": "SH030"},
            ]

            matched, unmatched = match_clips(clips, media_files)
            assert len(matched) >= 2, \
                f"Expected at least 2 matches, got {len(matched)}"
            assert len(unmatched) >= 1, \
                f"Expected at least 1 unmatched, got {len(unmatched)}"
            assert matched[0].get('media_path') is not None, \
                "Matched clip should have media_path"

    # ── Handles module ────────────────────────────────────────────────

    def check_handles_module():
        from opencomp_core.conform.handles import (
            calculate_handles, DEFAULT_HANDLES,
        )
        assert callable(calculate_handles)
        assert DEFAULT_HANDLES == 8

    def check_handles_calculation():
        from opencomp_core.conform.handles import calculate_handles
        from opencomp_core.conform.ingest import ingest_edl, get_clips

        with tempfile.TemporaryDirectory() as tmpdir:
            edl_path = _write_sample_edl(tmpdir)
            timeline = ingest_edl(edl_path, fps=24.0)
            clips = get_clips(timeline)

            result = calculate_handles(clips, head=4, tail=4)
            assert len(result) == len(clips), "Handle count mismatch"

            for clip in result:
                assert 'head_handles' in clip, "Missing head_handles"
                assert 'tail_handles' in clip, "Missing tail_handles"
                assert 'total_frames' in clip, "Missing total_frames"
                assert clip['total_frames'] >= clip['duration_frames'], \
                    "Total frames should be >= duration"

    # ── Structure module ──────────────────────────────────────────────

    def check_structure_module():
        from opencomp_core.conform.structure import (
            generate_structure, get_shot_paths,
        )
        assert callable(generate_structure)
        assert callable(get_shot_paths)

    def check_structure_generation():
        from opencomp_core.conform.structure import generate_structure

        with tempfile.TemporaryDirectory() as tmpdir:
            clips = [
                {"clip_name": "SH010"},
                {"clip_name": "SH020"},
            ]
            shot_dirs = generate_structure(tmpdir, clips, sequence="SEQ010")
            assert len(shot_dirs) == 2, f"Expected 2 shot dirs, got {len(shot_dirs)}"

            for shot_dir in shot_dirs:
                assert (shot_dir / "plates").is_dir(), \
                    f"Missing plates/ in {shot_dir}"
                assert (shot_dir / "comp").is_dir(), \
                    f"Missing comp/ in {shot_dir}"
                assert (shot_dir / "render").is_dir(), \
                    f"Missing render/ in {shot_dir}"

    # ── NK Export module ──────────────────────────────────────────────

    def check_nk_export_module():
        from opencomp_core.conform.nk_export import (
            generate_nk, export_nk_for_clip,
        )
        assert callable(generate_nk)
        assert callable(export_nk_for_clip)

    def check_nk_generation():
        from opencomp_core.conform.nk_export import generate_nk

        nk = generate_nk(
            shot_name="SH010",
            plate_path="/plates/SH010.%04d.exr",
            output_path="/render/SH010_comp.%04d.exr",
            first_frame=1001,
            last_frame=1048,
        )
        assert "Read {" in nk, "Missing Read node in .nk"
        assert "Write {" in nk, "Missing Write node in .nk"
        assert "Viewer {" in nk, "Missing Viewer node in .nk"
        assert "SH010" in nk, "Missing shot name in .nk"
        assert "%04d" in nk, "Missing frame padding in .nk"
        assert "1001" in nk, "Missing first frame in .nk"
        assert "1048" in nk, "Missing last frame in .nk"

    def check_nk_file_export():
        from opencomp_core.conform.nk_export import export_nk_for_clip

        with tempfile.TemporaryDirectory() as tmpdir:
            shot_dir = pathlib.Path(tmpdir) / "SEQ010" / "SH010"
            (shot_dir / "plates").mkdir(parents=True)
            (shot_dir / "render").mkdir(parents=True)

            clip = {
                "clip_name": "SH010",
                "duration_frames": 48,
                "head_handles": 8,
                "tail_handles": 8,
            }

            nk_path = export_nk_for_clip(clip, shot_dir)
            assert nk_path.exists(), f".nk file not created: {nk_path}"
            assert nk_path.suffix == '.nk', "Wrong extension"

            content = nk_path.read_text()
            assert "Read {" in content, "Missing Read node"
            assert "Write {" in content, "Missing Write node"

    # ── VSE Bridge module ─────────────────────────────────────────────

    def check_vse_bridge_module():
        from opencomp_core.conform.vse_bridge import (
            timeline_to_vse, clear_vse,
        )
        assert callable(timeline_to_vse)
        assert callable(clear_vse)

    # ── UI module ─────────────────────────────────────────────────────

    def check_ui_module():
        from opencomp_core.conform.ui import (
            OpenCompConformSettings, OC_PT_conform,
            OC_OT_conform_ingest, OC_OT_conform_match,
            OC_OT_conform_structure, OC_OT_conform_export_nk,
        )
        assert OC_PT_conform.bl_idname == "OC_PT_conform"
        assert OC_OT_conform_ingest.bl_idname == "oc.conform_ingest"
        assert OC_OT_conform_match.bl_idname == "oc.conform_match"
        assert OC_OT_conform_structure.bl_idname == "oc.conform_structure"
        assert OC_OT_conform_export_nk.bl_idname == "oc.conform_export_nk"

        ann = getattr(OpenCompConformSettings, '__annotations__', {})
        for prop in ('edl_filepath', 'media_root', 'output_root',
                     'sequence_name', 'fps', 'head_handles', 'tail_handles'):
            assert prop in ann, \
                f"OpenCompConformSettings missing: {prop}"

    # ── Integration: full EDL → .nk pipeline ──────────────────────────

    def check_full_pipeline():
        """End-to-end: ingest EDL, generate structure, export .nk."""
        from opencomp_core.conform.ingest import ingest_edl, get_clips
        from opencomp_core.conform.handles import calculate_handles
        from opencomp_core.conform.structure import generate_structure
        from opencomp_core.conform.nk_export import export_nk_for_clip

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Ingest
            edl_path = _write_sample_edl(tmpdir)
            timeline = ingest_edl(edl_path, fps=24.0)
            clips = get_clips(timeline)
            assert len(clips) >= 2

            # 2. Add handles
            clips = calculate_handles(clips, head=8, tail=8)

            # 3. Generate structure
            output_root = pathlib.Path(tmpdir) / "output"
            shot_dirs = generate_structure(output_root, clips)
            assert len(shot_dirs) >= 2

            # 4. Export .nk for each shot
            for clip, shot_dir in zip(clips, shot_dirs):
                nk_path = export_nk_for_clip(clip, shot_dir)
                assert nk_path.exists(), f".nk not created: {nk_path}"
                content = nk_path.read_text()
                assert "Read {" in content

    # ── Register all tests ────────────────────────────────────────────

    test("OTIO available",                       check_otio_available)
    test("pycmx available",                      check_pycmx_available)
    test("timecode available",                   check_timecode_available)
    test("Ingest module correct",                check_ingest_module)
    test("EDL ingest roundtrip",                 check_ingest_edl_roundtrip)
    test("Matcher module correct",               check_matcher_module)
    test("Matcher find and match",               check_matcher_find_and_match)
    test("Handles module correct",               check_handles_module)
    test("Handles calculation",                  check_handles_calculation)
    test("Structure module correct",             check_structure_module)
    test("Structure generation",                 check_structure_generation)
    test("NK export module correct",             check_nk_export_module)
    test("NK generation content",                check_nk_generation)
    test("NK file export",                       check_nk_file_export)
    test("VSE bridge module correct",            check_vse_bridge_module)
    test("UI module correct",                    check_ui_module)
    test("Full EDL → .nk pipeline",              check_full_pipeline)
