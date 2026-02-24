# Adding Nodes to Custom NodeTree Menus

## The Problem
Blender's built-in `node.add_node` operator does NOT work with custom NodeTree types like `OC_NT_compositor`. It only works with Blender's native node systems (Shader, Compositor, Geometry Nodes).

Using `node.add_node` in menus will silently fail - the menu appears but clicking items does nothing.

## The Solution
Use the custom `oc.add_node` operator which calls `tree.nodes.new(node_type)` directly.

### Wrong (doesn't work):
```python
layout.operator("node.add_node", text="Roto").type = "OC_N_roto"
```

### Correct:
```python
layout.operator("oc.add_node", text="Roto").node_type = "OC_N_roto"
```

## Key Differences
- `node.add_node` uses `.type` property
- `oc.add_node` uses `.node_type` property
- `oc.add_node` is defined in `opencomp_core/node_canvas/operators.py`

## When Adding New Nodes
1. Create the node class in `opencomp_core/nodes/<category>/<name>.py`
2. Add it to the category's `__init__.py` imports
3. Add menu entry using `oc.add_node` in:
   - `opencomp_core/__init__.py` (NODE_MT_add override and OC_MT_add_* classes)
   - `opencomp_core/node_canvas/operators.py` (OC_MT_add_node menu)
4. For NodeGraphQt: add to `opencomp_core/qt_canvas/canvas/nodes.py`
