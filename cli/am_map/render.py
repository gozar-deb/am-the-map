"""Terminal rendering helpers -- a coarse top-down ASCII/rich heatmap so
headless/SSH users (section 4: Raspberry Pi, Linux servers) can see the map
without the web dashboard."""
from __future__ import annotations

from rich.text import Text

SHADES = " .:-=+*#%@"


def render_topdown_heatmap(voxels: list[dict], bounds_m: tuple[float, float, float], cols: int = 40, rows: int = 20) -> Text:
    """Project all voxels onto the X/Y plane (max over Z) into a `cols` x
    `rows` character grid of density shading."""
    grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
    bx, by = bounds_m[0], bounds_m[1]
    for v in voxels:
        wx, wy, _ = v["world"]
        col = min(cols - 1, max(0, int((wx / bx) * cols)))
        row = min(rows - 1, max(0, int((wy / by) * rows)))
        density = max(v["occupancy_probability"], v["rf_intensity"] * 0.6)
        grid[row][col] = max(grid[row][col], density)

    text = Text()
    for row in reversed(grid):  # so +Y is "up" on screen
        for value in row:
            idx = min(len(SHADES) - 1, int(value * (len(SHADES) - 1)))
            char = SHADES[idx]
            style = None
            if value > 0.6:
                style = "bold red"
            elif value > 0.3:
                style = "yellow"
            elif value > 0.05:
                style = "cyan"
            text.append(char, style=style)
        text.append("\n")
    return text
