"""OpenComp Read node — loads image files via OIIO into RGBA32F GPUTexture.

Inputs:  (none — source node)
Outputs: Image (RGBA32F, linear scene-referred)
"""

import bpy
import os
import re
import glob
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from ..base import OpenCompNode


def _zoom_timeline_to_fit():
    """Zoom the timeline to fit the current frame range."""
    try:
        scene = bpy.context.scene
        frame_start = scene.frame_start
        frame_end = scene.frame_end

        # Find timeline area
        for area in bpy.context.screen.areas:
            if area.type == 'DOPESHEET_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        try:
                            with bpy.context.temp_override(area=area, region=region):
                                bpy.ops.action.view_all()
                        except Exception:
                            pass
                        break
                break
    except Exception:
        pass


# ─── Image Sequence Detection ───────────────────────────────────────────────

# Common frame number patterns in order of preference
_SEQUENCE_PATTERNS = [
    # name.0001.ext (most common - dots)
    re.compile(r'^(.+?)\.(\d{2,8})\.([^.]+)$'),
    # name_0001.ext (underscore separator)
    re.compile(r'^(.+?)_(\d{2,8})\.([^.]+)$'),
    # name-0001.ext (dash separator)
    re.compile(r'^(.+?)-(\d{2,8})\.([^.]+)$'),
    # name0001.ext (no separator - least preferred)
    re.compile(r'^(.+?)(\d{4,8})\.([^.]+)$'),
]

# Supported image extensions for sequences
_IMAGE_EXTENSIONS = {'.exr', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.dpx', '.cin', '.hdr'}


def detect_sequence(filepath):
    """Detect if a file is part of an image sequence.

    Returns:
        tuple: (sequence_path, first_frame, last_frame, frame_count) or None
        - sequence_path uses #### notation for frame numbers
        - Example: /path/to/image.####.exr
    """
    if not os.path.exists(filepath):
        return None

    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()

    # Only process known image formats
    if ext not in _IMAGE_EXTENSIONS:
        return None

    # Try each pattern
    for pattern in _SEQUENCE_PATTERNS:
        match = pattern.match(filename)
        if match:
            prefix = match.group(1)
            frame_str = match.group(2)
            extension = match.group(3)
            padding = len(frame_str)

            # Determine the separator used
            if filename[len(prefix)] == '.':
                separator = '.'
            elif filename[len(prefix)] == '_':
                separator = '_'
            elif filename[len(prefix)] == '-':
                separator = '-'
            else:
                separator = ''

            # Build glob pattern to find all frames
            glob_pattern = os.path.join(
                directory,
                f"{prefix}{separator}{'?' * padding}.{extension}"
            )

            # Find all matching files
            matching_files = glob.glob(glob_pattern)

            if len(matching_files) > 1:
                # Extract frame numbers and sort
                frames = []
                for f in matching_files:
                    m = pattern.match(os.path.basename(f))
                    if m:
                        frames.append(int(m.group(2)))

                if frames:
                    frames.sort()
                    first_frame = frames[0]
                    last_frame = frames[-1]
                    frame_count = len(frames)

                    # Build sequence path with #### notation
                    hash_padding = '#' * padding
                    sequence_path = os.path.join(
                        directory,
                        f"{prefix}{separator}{hash_padding}.{extension}"
                    )

                    return (sequence_path, first_frame, last_frame, frame_count)

    return None


def get_sequence_frame_path(sequence_path, frame):
    """Convert a sequence path with #### to a specific frame path."""
    # Count the number of # characters
    match = re.search(r'(#+)', sequence_path)
    if not match:
        return sequence_path

    hash_str = match.group(1)
    padding = len(hash_str)
    frame_str = str(frame).zfill(padding)

    return sequence_path.replace(hash_str, frame_str)


class OC_OT_read_browse(Operator, ImportHelper):
    """Browse for image file"""
    bl_idname = "oc.read_browse"
    bl_label = "Browse Image"

    node_name: bpy.props.StringProperty()

    filter_glob: bpy.props.StringProperty(
        default="*.exr;*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.hdr;*.dpx;*.cin",
        options={'HIDDEN'},
    )

    def execute(self, context):
        filepath = self.filepath

        # Check if this is part of a sequence
        seq_info = detect_sequence(filepath)
        if seq_info:
            sequence_path, first_frame, last_frame, frame_count = seq_info
            print(f"[OpenComp] Detected sequence: {sequence_path}")
            print(f"[OpenComp]   Frames {first_frame}-{last_frame} ({frame_count} files)")
            filepath = sequence_path  # Use the #### pattern path

        # Find the node and set filepath
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor":
                node = tree.nodes.get(self.node_name)
                if node:
                    node.filepath = filepath
                    if seq_info:
                        node.is_sequence = True
                        node.first_frame = first_frame
                        node.last_frame = last_frame
                        # Set scene frame range to match sequence
                        context.scene.frame_start = first_frame
                        context.scene.frame_end = last_frame
                        context.scene.frame_set(first_frame)
                        # Zoom timeline to fit frame range
                        _zoom_timeline_to_fit()
                        self.report({'INFO'}, f"Loaded sequence: {frame_count} frames ({first_frame}-{last_frame})")
                    else:
                        node.is_sequence = False
                    break
        return {'FINISHED'}


class OC_OT_read_drop(Operator):
    """Create Read node from dropped image file"""
    bl_idname = "oc.read_drop"
    bl_label = "Drop Image"
    bl_options = {'REGISTER', 'UNDO'}

    # Single file path (for direct calls) - SKIP_SAVE required for FileHandler
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to the dropped image file",
        subtype='FILE_PATH',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    # Directory + files (for FileHandler drops)
    directory: bpy.props.StringProperty(
        name="Directory",
        subtype='DIR_PATH',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    files: bpy.props.CollectionProperty(
        name="Files",
        type=bpy.types.OperatorFileListElement,
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    def execute(self, context):
        # Get the node tree
        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            return {'CANCELLED'}

        tree = space.node_tree
        if not tree or tree.bl_idname != "OC_NT_compositor":
            return {'CANCELLED'}

        # Collect all filepaths to process
        filepaths = []

        # Check if we have files from FileHandler (drag-drop from OS)
        if self.files and self.directory:
            for file_elem in self.files:
                fp = os.path.join(self.directory, file_elem.name)
                if os.path.exists(fp):
                    filepaths.append(fp)
        elif self.filepath:
            filepaths.append(self.filepath)

        if not filepaths:
            self.report({'WARNING'}, "No valid files to import")
            return {'CANCELLED'}

        # Get cursor position in node editor for placement
        try:
            region = context.region
            rv2d = region.view2d
            view_center_x = rv2d.region_to_view(region.width / 2, 0)[0]
            view_center_y = rv2d.region_to_view(0, region.height / 2)[1]
            base_location = [view_center_x, view_center_y]
        except Exception:
            base_location = [0, 0]

        created_nodes = []
        processed_sequences = set()  # Track sequences we've already created nodes for
        node_offset = 0

        for filepath in filepaths:
            # Check if this is part of a sequence
            seq_info = detect_sequence(filepath)

            if seq_info:
                sequence_path, first_frame, last_frame, frame_count = seq_info

                # Skip if we already created a node for this sequence
                if sequence_path in processed_sequences:
                    continue
                processed_sequences.add(sequence_path)

                # Create Read node with sequence path (containing ####)
                new_node = tree.nodes.new('OC_N_read')
                new_node.location = (base_location[0] + node_offset, base_location[1])
                new_node.filepath = sequence_path
                new_node.is_sequence = True
                new_node.first_frame = first_frame
                new_node.last_frame = last_frame
            else:
                # Single file, not a sequence
                new_node = tree.nodes.new('OC_N_read')
                new_node.location = (base_location[0] + node_offset, base_location[1])
                new_node.filepath = filepath
                new_node.is_sequence = False

            created_nodes.append((new_node, seq_info))
            node_offset += 250  # Offset each subsequent node

        # Select only the new nodes
        for n in tree.nodes:
            n.select = False
        for node, _ in created_nodes:
            node.select = True
        if created_nodes:
            tree.nodes.active = created_nodes[-1][0]

        # Sync to canvas state
        try:
            from ...node_canvas.state import get_canvas_state
            from ...node_canvas.operators import sync_from_tree
            state = get_canvas_state()
            sync_from_tree(state, tree)
        except Exception:
            pass

        # Tag for redraw
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()

        # Report what was created
        if len(created_nodes) == 1:
            node, seq_info = created_nodes[0]
            if seq_info:
                _, first_frame, last_frame, frame_count = seq_info
                # Set scene frame range to match sequence
                context.scene.frame_start = first_frame
                context.scene.frame_end = last_frame
                context.scene.frame_set(first_frame)
                # Zoom timeline to fit frame range
                _zoom_timeline_to_fit()
                self.report({'INFO'}, f"Loaded sequence: {frame_count} frames ({first_frame}-{last_frame})")
            else:
                self.report({'INFO'}, f"Loaded: {os.path.basename(node.filepath)}")
        else:
            self.report({'INFO'}, f"Created {len(created_nodes)} Read nodes")

        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


# Cache: {node_name: (cache_key, GPUTexture)} — avoids re-reading
# the same file from disk every evaluation tick.
_read_cache = {}

# Metadata cache: {node_name: dict} — stores EXR/image metadata for HUD display
_metadata_cache = {}


def _on_prop_update(self, context):
    """Trigger graph re-evaluation when filepath changes."""
    # Invalidate cache for this node so it re-reads
    _read_cache.pop(self.name, None)
    # Also invalidate thumbnail cache
    _thumbnail_cache.pop(self.name, None)
    from ...node_graph.tree import request_evaluate
    request_evaluate()


# Thumbnail cache: {node_name: bpy.types.Image}
_thumbnail_cache = {}


class ReadNode(OpenCompNode):
    """Read an image file from disk using OpenImageIO."""

    bl_idname = "OC_N_read"
    bl_label = "Read"
    bl_icon = "FILE_IMAGE"

    filepath: bpy.props.StringProperty(
        name="File", subtype='FILE_PATH', default="",
        update=_on_prop_update,
        description="File path. Use #### for frame padding in sequences",
    )
    # Sequence properties
    is_sequence: bpy.props.BoolProperty(
        name="Sequence", default=False,
        description="Treat as image sequence",
    )
    first_frame: bpy.props.IntProperty(
        name="First", default=1,
        description="First frame of sequence",
    )
    last_frame: bpy.props.IntProperty(
        name="Last", default=1,
        description="Last frame of sequence",
    )
    show_thumbnail: bpy.props.BoolProperty(
        name="Show Thumbnail", default=False,
        description="Display a preview thumbnail of the image",
    )

    _output_texture = None

    def init(self, context):
        super().init(context)
        self.outputs.new("OC_NS_image", "Image")

    def _get_thumbnail(self):
        """Get or create a Blender image for thumbnail preview."""
        if not self.filepath:
            return None

        resolved = bpy.path.abspath(self.filepath)

        # Check cache
        cached = _thumbnail_cache.get(self.name)
        if cached and cached[0] == resolved:
            img = cached[1]
            # Ensure preview is available
            if img and img.preview:
                return img
            return None

        # Load image into Blender for preview
        try:
            import os
            if not os.path.exists(resolved):
                return None

            # Use a unique name based on node name to avoid conflicts
            img_name = f"_oc_thumb_{self.name}"

            # Remove old image if exists
            if img_name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[img_name])

            # Load new image
            img = bpy.data.images.load(resolved)
            img.name = img_name

            # Ensure preview is generated
            img.preview_ensure()

            _thumbnail_cache[self.name] = (resolved, img)
            return img
        except Exception as e:
            print(f"[OpenComp] Could not load thumbnail: {e}")
            return None

    def draw_buttons(self, context, layout):
        # File path - FILE_PATH subtype automatically adds browse button
        layout.prop(self, "filepath", text="")

        # Sequence controls
        if self.is_sequence:
            row = layout.row(align=True)
            row.prop(self, "first_frame", text="First")
            row.prop(self, "last_frame", text="Last")
            # Show current frame and total
            frame_count = self.last_frame - self.first_frame + 1
            current_frame = context.scene.frame_current
            layout.label(text=f"Frame {current_frame} ({frame_count} total)")

        # Thumbnail toggle
        row = layout.row()
        row.prop(self, "show_thumbnail", icon='IMAGE_DATA', text="")

        # Show thumbnail if enabled
        if self.show_thumbnail and self.filepath:
            img = self._get_thumbnail()
            if img:
                layout.template_icon(icon_value=img.preview.icon_id, scale=5.0)

    def _resolve_frame_path(self, filepath, frame):
        """Resolve sequence path with #### to actual frame path."""
        # Count # characters
        hash_count = filepath.count('#')
        if hash_count == 0:
            return filepath
        # Replace #### with zero-padded frame number
        frame_str = str(frame).zfill(hash_count)
        return filepath.replace('#' * hash_count, frame_str)

    def evaluate(self, texture_pool):
        """Read image file → RGBA32F GPUTexture."""
        try:
            if not self.filepath:
                return None

            # Get current frame for sequences
            current_frame = bpy.context.scene.frame_current

            # Resolve the actual file path
            if self.is_sequence:
                # Clamp to sequence range
                frame = max(self.first_frame, min(current_frame, self.last_frame))
                resolved = bpy.path.abspath(self._resolve_frame_path(self.filepath, frame))
            else:
                resolved = bpy.path.abspath(self.filepath)
                frame = 0  # Not a sequence

            # Read proxy factor from viewer settings
            proxy_factor = 1
            try:
                proxy_factor = int(bpy.context.scene.oc_viewer.proxy)
            except (AttributeError, ValueError):
                pass

            # Check if this frame has a cached GPU texture (fast path for real-time playback)
            if self.is_sequence:
                try:
                    from ..viewer.viewer import get_cached_texture, _cached_frames
                    if frame in _cached_frames:
                        tex = get_cached_texture(frame)
                        if tex is not None:
                            return tex  # Fast path: return cached GPU texture directly
                except ImportError as e:
                    print(f"[OpenComp] Cache import error: {e}")

            # Return cached texture if filepath + frame + proxy haven't changed
            cache_key = (self.filepath, frame, proxy_factor)
            cached = _read_cache.get(self.name)
            if cached and cached[0] == cache_key:
                return cached[1]

            bpy.utils.expose_bundled_modules()
            import OpenImageIO as oiio
            import numpy as np
            import gpu
            import time

            t_start = time.perf_counter()

            # Enable multithreaded reading (helps with EXR decompression)
            config = oiio.ImageSpec()
            config["oiio:threads"] = 0  # 0 = use all available cores
            inp = oiio.ImageInput.open(resolved, config)
            if inp is None:
                print(f"[OpenComp] ReadNode: cannot open {self.filepath}")
                return None

            spec = inp.spec()

            # ── Extract metadata from OIIO spec ──
            metadata = self._extract_metadata(spec, resolved)
            _metadata_cache[self.name] = metadata

            # Read image data
            pixels = inp.read_image(oiio.FLOAT)
            pixels = pixels.reshape(spec.height, spec.width, spec.nchannels)

            # Ensure RGBA — pad missing channels (optimized with pre-allocation)
            if spec.nchannels == 3:
                # Pre-allocate RGBA and copy RGB + set alpha=1
                rgba = np.empty((spec.height, spec.width, 4), dtype=np.float32)
                rgba[:, :, :3] = pixels
                rgba[:, :, 3] = 1.0
                pixels = rgba
            elif spec.nchannels == 1:
                # Grayscale to RGBA
                rgba = np.empty((spec.height, spec.width, 4), dtype=np.float32)
                rgba[:, :, 0] = pixels[:, :, 0]
                rgba[:, :, 1] = pixels[:, :, 0]
                rgba[:, :, 2] = pixels[:, :, 0]
                rgba[:, :, 3] = 1.0
                pixels = rgba

            inp.close()

            # Apply proxy downscale via numpy stride slicing
            if proxy_factor > 1:
                pixels = np.ascontiguousarray(pixels[::proxy_factor, ::proxy_factor, :])

            h, w = pixels.shape[0], pixels.shape[1]

            # OPTIMIZATION: Try direct numpy buffer pass (zero-copy if it works)
            # Falls back to array.array method if direct pass fails
            pixels = np.ascontiguousarray(pixels, dtype=np.float32)

            try:
                # Attempt 1: Direct memoryview (fastest if supported)
                buf = gpu.types.Buffer('FLOAT', pixels.size, memoryview(pixels.ravel()))
            except (TypeError, ValueError):
                # Attempt 2: array.array (still fast)
                import array
                arr = array.array('f')
                arr.frombytes(pixels.tobytes())
                buf = gpu.types.Buffer('FLOAT', len(arr), arr)

            tex = gpu.types.GPUTexture(
                (w, h), format='RGBA32F', data=buf
            )

            # Cache both GPU texture and pixel data for sequences (enables real-time playback)
            if self.is_sequence:
                try:
                    from ..viewer.viewer import cache_frame_with_texture
                    cache_frame_with_texture(frame, tex, pixels, w, h)
                except ImportError:
                    pass

            _read_cache[self.name] = (cache_key, tex)
            t_elapsed = (time.perf_counter() - t_start) * 1000  # ms
            proxy_label = f" (proxy 1/{proxy_factor})" if proxy_factor > 1 else ""
            print(f"[OpenComp] Read: {w}x{h}{proxy_label} in {t_elapsed:.1f}ms from {self.filepath}")
            return tex

        except Exception as e:
            print(f"[OpenComp] ReadNode.evaluate error: {e}")
            return None

    def _extract_metadata(self, spec, filepath):
        """Extract metadata from OIIO ImageSpec for HUD display."""
        import os

        metadata = {
            "filename": os.path.basename(filepath),
            "width": spec.width,
            "height": spec.height,
            "channels": spec.nchannels,
            "channel_names": list(spec.channelnames) if spec.channelnames else [],
            "format": os.path.splitext(filepath)[1].upper().lstrip("."),
            "bit_depth": None,
            "compression": None,
            "colorspace": None,
            "software": None,
            "pixel_aspect": 1.0,
            "framerate": None,
            "timecode": None,
            "image_type": None,        # scanlineimage, tiledimage
            "nuke_version": None,      # Nuke version if available
        }

        # Pixel data type → bit depth string
        format_str = str(spec.format)
        if "half" in format_str.lower():
            metadata["bit_depth"] = "16-bit half"
        elif "float" in format_str.lower():
            metadata["bit_depth"] = "32-bit float"
        elif "uint16" in format_str.lower():
            metadata["bit_depth"] = "16-bit int"
        elif "uint8" in format_str.lower():
            metadata["bit_depth"] = "8-bit int"
        else:
            metadata["bit_depth"] = format_str

        # Extract string attributes
        try:
            metadata["compression"] = spec.get_string_attribute("compression", "")
            metadata["colorspace"] = spec.get_string_attribute("oiio:ColorSpace", "")
            metadata["software"] = spec.get_string_attribute("Software", "")

            # Pixel aspect ratio
            par = spec.get_float_attribute("PixelAspectRatio", 1.0)
            metadata["pixel_aspect"] = par

            # Framerate (if available)
            fps = spec.get_float_attribute("FramesPerSecond", 0.0)
            if fps > 0:
                metadata["framerate"] = fps

            # Timecode (if available)
            tc = spec.get_string_attribute("smpte:TimeCode", "")
            if tc:
                metadata["timecode"] = tc

            # ACES metadata
            aces_clip = spec.get_string_attribute("acesImageContainerFlag", "")
            if aces_clip:
                metadata["aces"] = True

            # EXR-specific: chromaticities, white point, etc.
            chroma = spec.get_string_attribute("chromaticities", "")
            if chroma:
                metadata["chromaticities"] = chroma

            # Image type: scanlineimage vs tiledimage
            # Check tile dimensions - if > 0, it's tiled
            if spec.tile_width > 0 and spec.tile_height > 0:
                metadata["image_type"] = f"tiled ({spec.tile_width}×{spec.tile_height})"
            else:
                metadata["image_type"] = "scanline"

            # Extract Nuke version from software string
            software = metadata.get("software", "") or ""
            if "nuke" in software.lower():
                metadata["nuke_version"] = software
            elif "Nuke" in software:
                metadata["nuke_version"] = software

            # Also check for nuke-specific attributes
            nuke_ver = spec.get_string_attribute("nuke/version", "")
            if nuke_ver:
                metadata["nuke_version"] = f"Nuke {nuke_ver}"

            # Writer info
            writer = spec.get_string_attribute("openexr:writer", "")
            if writer and not metadata.get("software"):
                metadata["software"] = writer

        except Exception:
            pass

        return metadata


class OC_FH_image_drop(bpy.types.FileHandler):
    """Handle image file drops into OpenComp Node Editor."""
    bl_idname = "OC_FH_image_drop"
    bl_label = "OpenComp Read"
    bl_import_operator = "oc.read_drop"
    bl_file_extensions = ".exr;.png;.jpg;.jpeg;.tif;.tiff;.hdr;.dpx;.cin"

    @classmethod
    def poll_drop(cls, context):
        """Only accept drops in OpenComp Node Editor."""
        if context.area is None or context.area.type != 'NODE_EDITOR':
            return False
        space = context.space_data
        if not space or space.tree_type != 'OC_NT_compositor':
            return False
        return True



# ─── Frame Change Handler ─────────────────────────────────────────────────

@bpy.app.handlers.persistent
def _on_frame_change(scene):
    """Handle frame changes to update sequence Read nodes."""
    current_frame = scene.frame_current

    # Find all OpenComp node trees
    has_sequences = False
    for tree in bpy.data.node_groups:
        if tree.bl_idname != "OC_NT_compositor":
            continue

        # Check for sequence Read nodes
        for node in tree.nodes:
            if node.bl_idname == "OC_N_read" and getattr(node, 'is_sequence', False):
                # Invalidate cache for this node so it reloads on next evaluate
                if node.name in _read_cache:
                    del _read_cache[node.name]
                has_sequences = True

    # If we have sequences, trigger re-evaluation and redraw
    if has_sequences:
        try:
            from ...node_graph.tree import request_evaluate
            request_evaluate()
        except ImportError as e:
            print(f"[OpenComp] Frame change import error: {e}")

        # Tag all relevant areas for redraw (including timeline for cache bar)
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'NODE_EDITOR', 'IMAGE_EDITOR', 'VIEW_3D', 'DOPESHEET_EDITOR'}:
                    area.tag_redraw()


def register():
    bpy.utils.register_class(OC_OT_read_browse)
    bpy.utils.register_class(OC_OT_read_drop)
    bpy.utils.register_class(ReadNode)

    # Register file drop handler
    try:
        bpy.utils.register_class(OC_FH_image_drop)
    except Exception as e:
        print(f"[OpenComp] Could not register file handler: {e}")

    # Register frame change handler for sequence playback
    if _on_frame_change not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_on_frame_change)


def unregister():
    # Remove frame change handler
    if _on_frame_change in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_on_frame_change)

    # Clean up thumbnail images
    for name, (_, img) in list(_thumbnail_cache.items()):
        try:
            if img and img.name in bpy.data.images:
                bpy.data.images.remove(img)
        except Exception:
            pass
    _thumbnail_cache.clear()
    _read_cache.clear()

    # Unregister file handler first
    try:
        bpy.utils.unregister_class(OC_FH_image_drop)
    except RuntimeError:
        pass

    try:
        bpy.utils.unregister_class(ReadNode)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(OC_OT_read_drop)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(OC_OT_read_browse)
    except RuntimeError:
        pass
