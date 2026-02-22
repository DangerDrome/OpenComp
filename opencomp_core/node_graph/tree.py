"""OpenComp node tree type — the custom compositor node graph.

Registered as OC_NT_compositor. Appears in Node Editor dropdown.
Includes deferred evaluation: when links or properties change,
a persistent timer picks up the dirty flag and walks the graph
in topological order, calling each node's evaluate().
"""

import bpy
from .evaluator import topological_sort, CycleDetectedError


# ── Texture cache ─────────────────────────────────────────────────────
# Blender creates new Python wrappers for nodes each time you access them
# through different paths (e.g. socket.node vs tree.nodes["name"]).
# Instance attributes like _output_texture don't survive across wrappers.
# Store textures here, keyed by node name, so sockets can look them up.
_node_textures = {}


# ── Deferred evaluation ───────────────────────────────────────────────

_eval_needed = False
_timer_running = False


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
        print("[OpenComp] Cycle detected — evaluation skipped")
        return

    for node_name in order:
        node = node_map[node_name]
        try:
            result = node.evaluate(None)
            _node_textures[node_name] = result
        except NotImplementedError:
            pass
        except Exception as e:
            print(f"[OpenComp] {node_name} evaluate error: {e}")


def _persistent_eval_timer():
    """Persistent timer — checks for pending evaluation every 200ms."""
    global _eval_needed
    if _eval_needed:
        _eval_needed = False
        try:
            for tree in bpy.data.node_groups:
                if tree.bl_idname == "OC_NT_compositor":
                    _evaluate_tree(tree)

            # Tag VIEW_3D areas for redraw so the viewer picks up new texture
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception as e:
            print(f"[OpenComp] Evaluation error: {e}")

    return 0.2  # repeat every 200ms


def request_evaluate():
    """Flag the graph for re-evaluation on the next timer tick."""
    global _eval_needed
    _eval_needed = True


# ── Node Tree ─────────────────────────────────────────────────────────

class OpenCompNodeTree(bpy.types.NodeTree):
    """Custom node tree for the OpenComp compositor."""

    bl_idname = "OC_NT_compositor"
    bl_label = "OpenComp Compositor"
    bl_icon = "NODE_COMPOSITING"

    def update(self):
        """Called on link/node changes. Flag for deferred evaluation."""
        global _eval_needed
        _eval_needed = True


def register():
    bpy.utils.register_class(OpenCompNodeTree)
    # Start persistent evaluation timer in GUI mode
    global _timer_running
    if not bpy.app.background and not _timer_running:
        bpy.app.timers.register(_persistent_eval_timer, first_interval=0.5, persistent=True)
        _timer_running = True


def unregister():
    global _timer_running
    if _timer_running:
        try:
            bpy.app.timers.unregister(_persistent_eval_timer)
        except ValueError:
            pass
        _timer_running = False
    bpy.utils.unregister_class(OpenCompNodeTree)
