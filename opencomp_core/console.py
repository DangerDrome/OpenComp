"""OpenComp Console — Stylish terminal output with colors and formatting.

Provides beautiful ASCII art logo, colored output, and formatted displays
for professional-quality console feedback.
"""

import sys
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# ANSI Color Codes
# ═══════════════════════════════════════════════════════════════════════════════

class Color:
    """ANSI escape codes for terminal colors."""

    # Reset
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # OpenComp brand colors (approximated in ANSI)
    BRAND = "\033[38;5;77m"      # Green (#4CCC73 approximation)
    BRAND_ALT = "\033[38;5;208m" # Orange accent
    ACCENT = "\033[38;5;39m"     # Bright blue accent


# Check if colors should be disabled
_colors_enabled = True
try:
    import bpy
    # Disable colors in Blender's console (doesn't support ANSI well)
    if hasattr(bpy.app, 'background') and not bpy.app.background:
        _colors_enabled = sys.stdout.isatty()
except ImportError:
    _colors_enabled = sys.stdout.isatty()


def _c(color: str) -> str:
    """Return color code if colors are enabled, empty string otherwise."""
    return color if _colors_enabled else ""


# ═══════════════════════════════════════════════════════════════════════════════
# ASCII Art Logo
# ═══════════════════════════════════════════════════════════════════════════════

LOGO_SMALL = r"""
   ___                   ___
  / _ \ _ __   ___ _ __ / __\___  _ __ ___  _ __
 | | | | '_ \ / _ \ '_ \/ /  / _ \| '_ ` _ \| '_ \
 | |_| | |_) |  __/ | | / /__| (_) | | | | | | |_) |
  \___/| .__/ \___|_| |_\____/\___/|_| |_| |_| .__/
       |_|                                   |_|
"""

LOGO_LARGE = r"""
  ╔═══════════════════════════════════════════════════════════════════════╗
  ║                                                                       ║
  ║    ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄        ▄                 ║
  ║   ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░▌      ▐░▌                ║
  ║   ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░▌░▌     ▐░▌                ║
  ║   ▐░▌       ▐░▌▐░▌       ▐░▌▐░▌          ▐░▌▐░▌    ▐░▌                ║
  ║   ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌ ▐░▌   ▐░▌                ║
  ║   ▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌  ▐░▌  ▐░▌                ║
  ║   ▐░▌       ▐░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀▀▀ ▐░▌   ▐░▌ ▐░▌                ║
  ║   ▐░▌       ▐░▌▐░▌          ▐░▌          ▐░▌    ▐░▌▐░▌                ║
  ║   ▐░█▄▄▄▄▄▄▄█░▌▐░▌          ▐░█▄▄▄▄▄▄▄▄▄ ▐░▌     ▐░▐░▌                ║
  ║   ▐░░░░░░░░░░░▌▐░▌          ▐░░░░░░░░░░░▌▐░▌      ▐░░▌                ║
  ║    ▀▀▀▀▀▀▀▀▀▀▀  ▀            ▀▀▀▀▀▀▀▀▀▀▀  ▀        ▀▀                 ║
  ║                                                                       ║
  ║     ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄       ▄▄  ▄▄▄▄▄▄▄▄▄▄▄                ║
  ║    ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░▌     ▐░░▌▐░░░░░░░░░░░▌               ║
  ║    ▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░▌░▌   ▐░▐░▌▐░█▀▀▀▀▀▀▀█░▌               ║
  ║    ▐░▌          ▐░▌       ▐░▌▐░▌▐░▌ ▐░▌▐░▌▐░▌       ▐░▌               ║
  ║    ▐░▌          ▐░▌       ▐░▌▐░▌ ▐░▐░▌ ▐░▌▐░█▄▄▄▄▄▄▄█░▌               ║
  ║    ▐░▌          ▐░▌       ▐░▌▐░▌  ▐░▌  ▐░▌▐░░░░░░░░░░░▌               ║
  ║    ▐░▌          ▐░▌       ▐░▌▐░▌   ▀   ▐░▌▐░█▀▀▀▀▀▀▀▀▀                ║
  ║    ▐░▌          ▐░▌       ▐░▌▐░▌       ▐░▌▐░▌                         ║
  ║    ▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌▐░▌       ▐░▌▐░▌                         ║
  ║    ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░▌                         ║
  ║     ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀  ▀                          ║
  ║                                                                       ║
  ╚═══════════════════════════════════════════════════════════════════════╝
"""

LOGO_MINIMAL = r"""
 ╭───────────────────────────────────────╮
 │  ◆ O P E N C O M P                    │
 │    GPU Compositor for Blender         │
 ╰───────────────────────────────────────╯
"""

LOGO_BANNER = r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗ ██████╗ ███╗   ███╗██████╗      ║
║  ██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔═══██╗████╗ ████║██╔══██╗     ║
║  ██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║     ██║   ██║██╔████╔██║██████╔╝     ║
║  ██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║     ██║   ██║██║╚██╔╝██║██╔═══╝      ║
║  ╚██████╔╝██║     ███████╗██║ ╚████║╚██████╗╚██████╔╝██║ ╚═╝ ██║██║          ║
║   ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝          ║
║                                                                              ║
║                    ◆ GPU Compositor for Blender ◆                            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Output Formatting
# ═══════════════════════════════════════════════════════════════════════════════

# Message type icons
class Icon:
    """Unicode icons for different message types."""
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "⚠"
    INFO = "●"
    DEBUG = "○"
    ARROW = "→"
    NODE = "◆"
    CONNECT = "⟷"
    DISCONNECT = "⊘"
    SHADER = "◈"
    TEXTURE = "▣"
    GPU = "▲"
    SYNC = "⟳"
    REGISTER = "◉"
    UNREGISTER = "○"
    LAUNCH = "▶"
    CLOSE = "■"
    LOADING = "◌"
    COMPLETE = "◉"


def _timestamp() -> str:
    """Get formatted timestamp."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def _format_prefix(icon: str, color: str, label: str = "OpenComp") -> str:
    """Format a message prefix with icon and label."""
    return f"{_c(Color.BRIGHT_BLACK)}[{_timestamp()}]{_c(Color.RESET)} {_c(color)}{icon}{_c(Color.RESET)} {_c(Color.BOLD)}{_c(Color.BRAND)}{label}{_c(Color.RESET)}"


def print_logo(style: str = "banner") -> None:
    """Print the OpenComp ASCII logo.

    Args:
        style: Logo style - 'banner', 'small', 'large', or 'minimal'
    """
    logos = {
        "banner": LOGO_BANNER,
        "small": LOGO_SMALL,
        "large": LOGO_LARGE,
        "minimal": LOGO_MINIMAL,
    }
    logo = logos.get(style, LOGO_BANNER)
    print(f"{_c(Color.BRAND)}{logo}{_c(Color.RESET)}")


def print_header(title: str, width: int = 60) -> None:
    """Print a styled section header.

    Args:
        title: Header title text
        width: Total width of the header line
    """
    padding = (width - len(title) - 4) // 2
    line = "═" * padding
    print(f"\n{_c(Color.BRAND)}{line}╣ {_c(Color.BOLD)}{title}{_c(Color.RESET)}{_c(Color.BRAND)} ╠{line}{_c(Color.RESET)}\n")


def print_subheader(title: str) -> None:
    """Print a styled subsection header.

    Args:
        title: Subsection title text
    """
    print(f"{_c(Color.CYAN)}  ╭─ {title}{_c(Color.RESET)}")


def print_divider(char: str = "─", width: int = 60) -> None:
    """Print a horizontal divider line.

    Args:
        char: Character to use for the line
        width: Width of the divider
    """
    print(f"{_c(Color.BRIGHT_BLACK)}{char * width}{_c(Color.RESET)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Message Functions
# ═══════════════════════════════════════════════════════════════════════════════

def info(message: str, component: Optional[str] = None) -> None:
    """Print an info message.

    Args:
        message: The message to print
        component: Optional component name (e.g., 'Bridge', 'GPU')
    """
    prefix = _format_prefix(Icon.INFO, Color.CYAN)
    comp = f"{_c(Color.BRIGHT_BLACK)}[{component}]{_c(Color.RESET)} " if component else ""
    print(f"{prefix} {comp}{message}")


def success(message: str, component: Optional[str] = None) -> None:
    """Print a success message.

    Args:
        message: The message to print
        component: Optional component name
    """
    prefix = _format_prefix(Icon.SUCCESS, Color.GREEN)
    comp = f"{_c(Color.BRIGHT_BLACK)}[{component}]{_c(Color.RESET)} " if component else ""
    print(f"{prefix} {comp}{_c(Color.GREEN)}{message}{_c(Color.RESET)}")


def warning(message: str, component: Optional[str] = None) -> None:
    """Print a warning message.

    Args:
        message: The message to print
        component: Optional component name
    """
    prefix = _format_prefix(Icon.WARNING, Color.YELLOW)
    comp = f"{_c(Color.BRIGHT_BLACK)}[{component}]{_c(Color.RESET)} " if component else ""
    print(f"{prefix} {comp}{_c(Color.YELLOW)}{message}{_c(Color.RESET)}")


def error(message: str, component: Optional[str] = None) -> None:
    """Print an error message.

    Args:
        message: The message to print
        component: Optional component name
    """
    prefix = _format_prefix(Icon.ERROR, Color.RED)
    comp = f"{_c(Color.BRIGHT_BLACK)}[{component}]{_c(Color.RESET)} " if component else ""
    print(f"{prefix} {comp}{_c(Color.RED)}{message}{_c(Color.RESET)}")


def debug(message: str, component: Optional[str] = None) -> None:
    """Print a debug message (dimmed).

    Args:
        message: The message to print
        component: Optional component name
    """
    prefix = _format_prefix(Icon.DEBUG, Color.BRIGHT_BLACK)
    comp = f"[{component}] " if component else ""
    print(f"{prefix} {_c(Color.DIM)}{comp}{message}{_c(Color.RESET)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Node & Graph Output
# ═══════════════════════════════════════════════════════════════════════════════

def node_created(node_name: str, node_type: str, position: Optional[tuple] = None) -> None:
    """Print node creation message.

    Args:
        node_name: Name of the created node
        node_type: Type/class of the node
        position: Optional (x, y) position tuple
    """
    pos_str = f" @ ({position[0]:.0f}, {position[1]:.0f})" if position else ""
    print(f"{_format_prefix(Icon.NODE, Color.BRAND)} "
          f"{_c(Color.GREEN)}+ {_c(Color.BOLD)}{node_name}{_c(Color.RESET)} "
          f"{_c(Color.BRIGHT_BLACK)}({node_type}){pos_str}{_c(Color.RESET)}")


def node_deleted(node_name: str) -> None:
    """Print node deletion message.

    Args:
        node_name: Name of the deleted node
    """
    print(f"{_format_prefix(Icon.NODE, Color.BRAND)} "
          f"{_c(Color.RED)}- {node_name}{_c(Color.RESET)}")


def node_selected(node_names: list) -> None:
    """Print node selection message.

    Args:
        node_names: List of selected node names
    """
    if not node_names:
        return
    count = len(node_names)
    names = ", ".join(node_names[:3])
    if count > 3:
        names += f" +{count - 3} more"
    print(f"{_format_prefix(Icon.NODE, Color.BRAND)} "
          f"{_c(Color.CYAN)}◇ Selected: {_c(Color.BOLD)}{names}{_c(Color.RESET)}")


def connection_made(from_node: str, from_port: str, to_node: str, to_port: str) -> None:
    """Print connection created message.

    Args:
        from_node: Source node name
        from_port: Source port name
        to_node: Destination node name
        to_port: Destination port name
    """
    print(f"{_format_prefix(Icon.CONNECT, Color.BRIGHT_BLUE)} "
          f"{_c(Color.BOLD)}{from_node}{_c(Color.RESET)}"
          f"{_c(Color.BRIGHT_BLACK)}.{from_port}{_c(Color.RESET)} "
          f"{_c(Color.GREEN)}{Icon.ARROW}{_c(Color.RESET)} "
          f"{_c(Color.BOLD)}{to_node}{_c(Color.RESET)}"
          f"{_c(Color.BRIGHT_BLACK)}.{to_port}{_c(Color.RESET)}")


def connection_removed(from_node: str, from_port: str, to_node: str, to_port: str) -> None:
    """Print connection removed message.

    Args:
        from_node: Source node name
        from_port: Source port name
        to_node: Destination node name
        to_port: Destination port name
    """
    print(f"{_format_prefix(Icon.DISCONNECT, Color.BRIGHT_BLACK)} "
          f"{_c(Color.DIM)}{from_node}.{from_port} {Icon.ARROW} {to_node}.{to_port}{_c(Color.RESET)}")


def param_changed(node_name: str, param: str, value) -> None:
    """Print parameter change message.

    Args:
        node_name: Node name
        param: Parameter name
        value: New parameter value
    """
    # Format value nicely
    if isinstance(value, float):
        val_str = f"{value:.3f}"
    elif isinstance(value, (list, tuple)):
        val_str = ", ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in value)
        val_str = f"[{val_str}]"
    else:
        val_str = str(value)

    print(f"{_format_prefix(Icon.NODE, Color.BRAND)} "
          f"{_c(Color.BOLD)}{node_name}{_c(Color.RESET)}"
          f"{_c(Color.BRIGHT_BLACK)}.{_c(Color.RESET)}{param} "
          f"{_c(Color.BRIGHT_BLACK)}={_c(Color.RESET)} "
          f"{_c(Color.BRAND_ALT)}{val_str}{_c(Color.RESET)}")


# ═══════════════════════════════════════════════════════════════════════════════
# GPU & Shader Output
# ═══════════════════════════════════════════════════════════════════════════════

def shader_compiled(shader_name: str) -> None:
    """Print shader compilation message.

    Args:
        shader_name: Name of the compiled shader
    """
    print(f"{_format_prefix(Icon.SHADER, Color.MAGENTA)} "
          f"Compiled: {_c(Color.BOLD)}{shader_name}{_c(Color.RESET)}")


def texture_allocated(width: int, height: int, format_str: str = "RGBA32F") -> None:
    """Print texture allocation message.

    Args:
        width: Texture width
        height: Texture height
        format_str: Texture format string
    """
    print(f"{_format_prefix(Icon.TEXTURE, Color.BLUE)} "
          f"Allocated: {_c(Color.BOLD)}{width}x{height}{_c(Color.RESET)} "
          f"{_c(Color.BRIGHT_BLACK)}({format_str}){_c(Color.RESET)}")


def gpu_operation(operation: str, details: str = "") -> None:
    """Print GPU operation message.

    Args:
        operation: Operation description
        details: Optional additional details
    """
    det = f" {_c(Color.BRIGHT_BLACK)}{details}{_c(Color.RESET)}" if details else ""
    print(f"{_format_prefix(Icon.GPU, Color.BRIGHT_MAGENTA)} {operation}{det}")


# ═══════════════════════════════════════════════════════════════════════════════
# System & Lifecycle Output
# ═══════════════════════════════════════════════════════════════════════════════

def registered(component: str) -> None:
    """Print registration message.

    Args:
        component: Name of the registered component
    """
    print(f"{_format_prefix(Icon.REGISTER, Color.GREEN)} "
          f"Registered: {_c(Color.BOLD)}{component}{_c(Color.RESET)}")


def unregistered(component: str) -> None:
    """Print unregistration message.

    Args:
        component: Name of the unregistered component
    """
    print(f"{_format_prefix(Icon.UNREGISTER, Color.BRIGHT_BLACK)} "
          f"{_c(Color.DIM)}Unregistered: {component}{_c(Color.RESET)}")


def launched(component: str) -> None:
    """Print launch message.

    Args:
        component: Name of the launched component
    """
    print(f"{_format_prefix(Icon.LAUNCH, Color.GREEN)} "
          f"Launched: {_c(Color.BOLD)}{component}{_c(Color.RESET)}")


def closed(component: str) -> None:
    """Print close message.

    Args:
        component: Name of the closed component
    """
    print(f"{_format_prefix(Icon.CLOSE, Color.BRIGHT_BLACK)} "
          f"{_c(Color.DIM)}Closed: {component}{_c(Color.RESET)}")


def synced(item_count: int, item_type: str = "items") -> None:
    """Print sync completion message.

    Args:
        item_count: Number of items synced
        item_type: Type of items (e.g., 'nodes', 'connections')
    """
    print(f"{_format_prefix(Icon.SYNC, Color.CYAN)} "
          f"Synced: {_c(Color.BOLD)}{item_count}{_c(Color.RESET)} {item_type}")


# ═══════════════════════════════════════════════════════════════════════════════
# Progress & Status
# ═══════════════════════════════════════════════════════════════════════════════

def progress_bar(current: int, total: int, width: int = 30, prefix: str = "") -> str:
    """Generate a text-based progress bar string.

    Args:
        current: Current progress value
        total: Total/maximum value
        width: Width of the progress bar in characters
        prefix: Optional prefix text

    Returns:
        Formatted progress bar string
    """
    if total == 0:
        percent = 100
    else:
        percent = (current / total) * 100

    filled = int(width * current / total) if total > 0 else width
    bar = "█" * filled + "░" * (width - filled)

    return (f"{prefix}{_c(Color.BRAND)}[{bar}]{_c(Color.RESET)} "
            f"{_c(Color.BOLD)}{percent:5.1f}%{_c(Color.RESET)} "
            f"{_c(Color.BRIGHT_BLACK)}({current}/{total}){_c(Color.RESET)}")


def print_progress(current: int, total: int, label: str = "Progress") -> None:
    """Print a progress bar.

    Args:
        current: Current progress value
        total: Total/maximum value
        label: Progress label
    """
    print(f"\r{_format_prefix(Icon.LOADING, Color.CYAN)} {label}: {progress_bar(current, total)}", end="")
    if current >= total:
        print()  # Newline when complete


def print_complete(message: str = "Complete") -> None:
    """Print a completion message.

    Args:
        message: Completion message
    """
    print(f"{_format_prefix(Icon.COMPLETE, Color.GREEN)} "
          f"{_c(Color.GREEN)}{_c(Color.BOLD)}{message}{_c(Color.RESET)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Table Output
# ═══════════════════════════════════════════════════════════════════════════════

def print_table(headers: list, rows: list, title: Optional[str] = None) -> None:
    """Print a formatted table.

    Args:
        headers: List of column header strings
        rows: List of rows, each row is a list of values
        title: Optional table title
    """
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Build format string
    total_width = sum(widths) + (len(widths) - 1) * 3 + 4

    # Print title
    if title:
        print(f"\n{_c(Color.BOLD)}{_c(Color.BRAND)}  {title}{_c(Color.RESET)}")

    # Print top border
    print(f"{_c(Color.BRIGHT_BLACK)}  ╭{'─' * (total_width - 2)}╮{_c(Color.RESET)}")

    # Print headers
    header_str = "  │ "
    for i, (header, width) in enumerate(zip(headers, widths)):
        header_str += f"{_c(Color.BOLD)}{header:<{width}}{_c(Color.RESET)}"
        if i < len(headers) - 1:
            header_str += " │ "
    header_str += " │"
    print(header_str)

    # Print separator
    print(f"{_c(Color.BRIGHT_BLACK)}  ├{'─' * (total_width - 2)}┤{_c(Color.RESET)}")

    # Print rows
    for row in rows:
        row_str = "  │ "
        for i, (cell, width) in enumerate(zip(row, widths)):
            row_str += f"{str(cell):<{width}}"
            if i < len(row) - 1:
                row_str += " │ "
        row_str += " │"
        print(row_str)

    # Print bottom border
    print(f"{_c(Color.BRIGHT_BLACK)}  ╰{'─' * (total_width - 2)}╯{_c(Color.RESET)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Startup Banner
# ═══════════════════════════════════════════════════════════════════════════════

def print_startup_banner(version: str = "0.1.0") -> None:
    """Print the full startup banner with logo and version info.

    Args:
        version: Version string to display
    """
    print(f"\n{_c(Color.BRAND)}{LOGO_BANNER}{_c(Color.RESET)}")
    print(f"  {_c(Color.BRIGHT_BLACK)}Version {version} │ Python GPU Compositor │ GPL-3.0{_c(Color.RESET)}")
    print(f"  {_c(Color.BRIGHT_BLACK)}{'─' * 58}{_c(Color.RESET)}\n")


def print_shutdown_banner() -> None:
    """Print the shutdown message."""
    print(f"\n{_c(Color.BRAND)}  ◆ OpenComp{_c(Color.RESET)} {_c(Color.BRIGHT_BLACK)}— Session ended{_c(Color.RESET)}\n")


# Convenience alias for backward compatibility
log = info
