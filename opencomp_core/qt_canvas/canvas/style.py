"""OpenComp Qt Canvas — Nuke-style dark theme.

Applies consistent dark styling matching OpenComp's Blender theme.
"""

# Dark theme colors matching OpenComp's Blender theme
STYLE = {
    # Graph background and grid
    'graph_bg_color': (25, 25, 25),
    'graph_grid_color': (35, 35, 35),
    'graph_grid_overlay_color': (45, 45, 45),

    # Node appearance
    'node_bg_color': (50, 50, 50),
    'node_border_color': (60, 60, 60),
    'node_selected_border_color': (255, 165, 0),  # Orange selection
    'node_text_color': (200, 200, 200),
    'node_header_color': (70, 70, 70),

    # Port/socket appearance
    'port_color': (160, 160, 160),
    'port_hover_color': (200, 200, 200),
    'port_active_color': (255, 165, 0),

    # Pipe/wire appearance
    'pipe_color': (160, 160, 160),
    'pipe_selected_color': (255, 165, 0),
    'pipe_active_color': (255, 200, 100),
    'pipe_disabled_color': (80, 80, 80),

    # Backdrop (frame) appearance
    'backdrop_color': (40, 40, 40, 150),
    'backdrop_border_color': (80, 80, 80),

    # Slicer (cut line)
    'slicer_color': (255, 50, 50),
}


def apply_style(graph):
    """Apply the OpenComp dark theme to a NodeGraphQt graph.

    Args:
        graph: OpenCompGraph instance to style.
    """
    # Set viewer (graph widget) colors
    viewer = graph.viewer()
    if viewer is None:
        return

    # Background color - try different API methods based on version
    try:
        viewer.set_background_color(*STYLE['graph_bg_color'])
    except AttributeError:
        # Older API - set via stylesheet or property
        pass

    # Grid colors
    try:
        viewer.set_grid_color(*STYLE['graph_grid_color'])
    except AttributeError:
        pass

    # Pipe/wire styling
    try:
        graph.set_pipe_style(0)  # 0 = curved bezier (Nuke style)
    except AttributeError:
        pass

    # Additional viewer settings
    try:
        viewer.set_zoom_range(-4.0, 4.0)
    except AttributeError:
        pass
