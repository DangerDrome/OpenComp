"""OpenComp node tree type — the custom compositor node graph.

Registered as OC_NT_compositor. Appears in Node Editor dropdown.
Includes deferred evaluation: when links or properties change,
a draw callback picks up the dirty flag and walks the graph
in topological order, calling each node's evaluate().

NOTE: Evaluation MUST happen inside a draw callback to have GPU context.
"""

import bpy
from .evaluator import topological_sort, CycleDetectedError
from ..gpu_pipeline.texture_pool import TexturePool
from .. import console


# ── Texture cache ─────────────────────────────────────────────────────
# Blender creates new Python wrappers for nodes each time you access them
# through different paths (e.g. socket.node vs tree.nodes["name"]).
# Instance attributes like _output_texture don't survive across wrappers.
# Store textures here, keyed by node name, so sockets can look them up.
_node_textures = {}

# ── Pixel cache (workaround for GPU readback issues in headless mode) ──
# Stores raw numpy pixel arrays for nodes that produce them (e.g. Read).
# Used for SHM output when GPU texture.read() is unreliable.
# Format: {node_name: (width, height, numpy_array)}
_node_pixels = {}


# ── Deferred evaluation ───────────────────────────────────────────────

_eval_needed = False
_eval_handler = None


def _evaluate_tree(tree):
    """Walk tree in topological order and evaluate each node."""
    graph = {}
    node_map = {}
    for node in tree.nodes:
        node_map[node.name] = node
        inputs = []
        for inp in node.inputs:
            if inp.is_linked:
                for link in inp.links:
                    inputs.append(link.from_node.name)
        graph[node.name] = {"inputs": inputs}

    if not graph:
        return

    try:
        order = topological_sort(graph)
    except CycleDetectedError:
        console.warning("Cycle detected — evaluation skipped", "Evaluator")
        return

    # Create texture pool for this evaluation pass
    pool = TexturePool()

    for node_name in order:
        node = node_map[node_name]
        try:
            result = node.evaluate(pool)
            _node_textures[node_name] = result
        except NotImplementedError:
            pass
        except Exception as e:
            console.error(f"{node_name} evaluate error: {e}", "Node")


_gpu_context_verified = False

def _eval_draw_callback():
    """Draw callback for evaluation — runs with GPU context available."""
    global _eval_needed, _gpu_context_verified
    if not _eval_needed:
        return

    # Verify we're in a proper drawing context
    context = bpy.context
    if context.area is None or context.area.type != 'VIEW_3D':
        return

    # Test GPU context by trying to create a simple shader once
    if not _gpu_context_verified:
        try:
            import gpu
            # Try to create a minimal shader to verify context
            test_vert = "void main() { gl_Position = vec4(0.0); }"
            test_frag = "out vec4 fragColor; void main() { fragColor = vec4(1.0); }"
            test_shader = gpu.types.GPUShader(test_vert, test_frag)
            del test_shader
            _gpu_context_verified = True
        except Exception:
            # GPU not ready yet, try again next frame (silently)
            return

    _eval_needed = False
    try:
        for tree in bpy.data.node_groups:
            if tree.bl_idname == "OC_NT_compositor":
                _evaluate_tree(tree)
    except Exception as e:
        console.error(f"Evaluation error: {e}", "Evaluator")


def request_evaluate():
    """Flag the graph for re-evaluation on the next draw."""
    global _eval_needed
    _eval_needed = True
    # Tag for redraw so our draw callback runs
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass


# ── Node Tree ─────────────────────────────────────────────────────────

class OpenCompNodeTree(bpy.types.NodeTree):
    """Custom node tree for the OpenComp compositor."""

    bl_idname = "OC_NT_compositor"
    bl_label = "OpenComp Compositor"
    bl_icon = "NODE_COMPOSITING"

    # Connection line style
    connection_style: bpy.props.EnumProperty(
        name="Connection Style",
        description="Visual style for node connections",
        items=[
            ('BEZIER', "Bezier", "Classic smooth bezier curves"),
            ('STRAIGHT', "Straight", "Direct straight lines"),
            ('DIRECTIONAL', "Directional", "Bezier that follows connection direction"),
            ('STEP', "Step", "Right-angle orthogonal lines"),
            ('SMOOTH_STEP', "Smooth Step", "Right-angles with rounded corners"),
        ],
        default='BEZIER'
    )

    def update(self):
        """Called on link/node changes. Flag for deferred evaluation."""
        # NOTE: Don't clear frame cache here - update() is called for node movement too
        # Cache should only be cleared when graph STRUCTURE changes (links added/removed)
        # which affects the output. Node movement doesn't change output.
        request_evaluate()

    @classmethod
    def draw_add(cls, layout):
        """Draw the Add menu for OpenComp node tree (Blender 4.0+ API)."""
        # Input nodes
        layout.label(text="Input", icon='IMPORT')
        layout.operator("node.add_node", text="Read", icon='IMAGE_DATA').type = "OC_N_read"
        layout.operator("node.add_node", text="Constant", icon='COLOR').type = "OC_N_constant"
        layout.separator()

        # Output nodes
        layout.label(text="Output", icon='EXPORT')
        layout.operator("node.add_node", text="Write", icon='FILE_IMAGE').type = "OC_N_write"
        layout.operator("node.add_node", text="Viewer", icon='RESTRICT_VIEW_OFF').type = "OC_N_viewer"
        layout.separator()

        # Color nodes
        layout.label(text="Color", icon='COLOR')
        layout.operator("node.add_node", text="Grade", icon='SEQ_LUMA_WAVEFORM').type = "OC_N_grade"
        layout.operator("node.add_node", text="CDL", icon='OPTIONS').type = "OC_N_cdl"
        layout.separator()

        # Merge nodes
        layout.label(text="Merge", icon='SELECT_EXTEND')
        layout.operator("node.add_node", text="Over", icon='IMAGE_ALPHA').type = "OC_N_over"
        layout.operator("node.add_node", text="Merge", icon='NODE_COMPOSITING').type = "OC_N_merge"
        layout.operator("node.add_node", text="Shuffle", icon='LIGHTPROBE_VOLUME').type = "OC_N_shuffle"
        layout.separator()

        # Filter nodes
        layout.label(text="Filter", icon='MATFLUID')
        layout.operator("node.add_node", text="Blur", icon='MATFLUID').type = "OC_N_blur"
        layout.operator("node.add_node", text="Sharpen", icon='NODE').type = "OC_N_sharpen"
        layout.separator()

        # Transform nodes
        layout.label(text="Transform", icon='ORIENTATION_GLOBAL')
        layout.operator("node.add_node", text="Transform", icon='OBJECT_ORIGIN').type = "OC_N_transform"
        layout.operator("node.add_node", text="Crop", icon='VIEW_ORTHO').type = "OC_N_crop"
        layout.separator()

        # Draw nodes
        layout.label(text="Draw", icon='MESH_CIRCLE')
        layout.operator("node.add_node", text="Roto", icon='MESH_CIRCLE').type = "OC_N_roto"
        layout.separator()

        # Utility nodes
        layout.label(text="Utility", icon='ARROW_LEFTRIGHT')
        layout.operator("node.add_node", text="Reroute", icon='ARROW_LEFTRIGHT').type = "OC_N_reroute"


def register():
    # Guard against double registration
    try:
        bpy.utils.register_class(OpenCompNodeTree)
    except ValueError:
        pass  # Already registered

    # Register evaluation draw handler (needs GPU context)
    # POST_PIXEL ensures GPU context is available for shader compilation
    global _eval_handler
    if not bpy.app.background and _eval_handler is None:
        _eval_handler = bpy.types.SpaceView3D.draw_handler_add(
            _eval_draw_callback, (), 'WINDOW', 'POST_PIXEL'
        )


def unregister():
    global _eval_handler, _gpu_context_verified
    _gpu_context_verified = False
    if _eval_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_eval_handler, 'WINDOW')
        _eval_handler = None
    try:
        bpy.utils.unregister_class(OpenCompNodeTree)
    except RuntimeError:
        pass
