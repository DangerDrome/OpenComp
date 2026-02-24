# OpenComp Custom Node Canvas System

## Overview
OpenComp uses a **custom GPU-drawn node canvas**, NOT Blender's native node editor rendering. We draw our own nodes, links, and ports using GPU shaders.

## Key Files

- `opencomp_core/node_canvas/state.py` - Canvas state, NodeVisual, LinkVisual dataclasses
- `opencomp_core/node_canvas/renderer.py` - GPU drawing of nodes, links, ports, grid
- `opencomp_core/node_canvas/operators.py` - Modal operator for input handling, draw callbacks

## NodeVisual Dataclass (state.py)

```python
@dataclass
class NodeVisual:
    node_name: str          # Reference to bpy node by name
    x: float = 0.0          # Canvas position (Blender coords)
    y: float = 0.0
    width: float = 140.0
    height: float = 24.0    # 24 = collapsed, 80+ = expanded
    color: Tuple[float, float, float] = (0.3, 0.3, 0.3)
    selected: bool = False
    collapsed: bool = True  # Controls visual appearance
    input_ports: List[Tuple[float, float]]   # Computed positions
    output_ports: List[Tuple[float, float]]
```

## Collapsed vs Expanded Nodes

- **Collapsed** (`node.hide = True`): Height = 24px, draws only header bar
- **Expanded** (`node.hide = False`): Height = 80+px, draws header + body

The canvas reads `node.hide` from Blender nodes via `sync_from_tree()`:
```python
nv.collapsed = getattr(node, 'hide', True)
if nv.collapsed:
    nv.height = 24
else:
    nv.height = max(node.height, 80)
```

## Renderer (_draw_node method)

- Collapsed: Draws single colored rectangle (header color)
- Expanded: Draws body (grey) + header on top
- Always draws: border, node name text, ports

## Port Positions

- Input ports: Top of node (`nv.y + nv.height`)
- Output ports: Bottom of node (`nv.y`)
- Evenly distributed horizontally: `px = nv.x + (i + 1) * nv.width / (num_ports + 1)`

## sync_from_tree Function

Syncs Blender node tree → canvas state:
- Position from `node.location`
- Dimensions from `node.width`, `node.height`, `node.hide`
- Selection from `node.select`
- Port counts from `node.inputs`, `node.outputs`

## Color Constants (renderer.py)

```python
COLOR_NODE_BG = (0.18, 0.18, 0.18, 1.0)      # Body
COLOR_NODE_HEADER = (0.28, 0.28, 0.28, 1.0)  # Header
COLOR_NODE_BORDER = (0.1, 0.1, 0.1, 1.0)     # Border
COLOR_NODE_SELECTED = (0.8, 0.5, 0.1, 1.0)   # Selected highlight
NODE_HEADER_HEIGHT = 24  # Canvas units
```

## Base Node Class

All OpenComp nodes inherit from `OpenCompNode` (nodes/base.py):
- Sets `self.hide = True` in init() for collapsed default
- Child nodes must call `super().init(context)` first
