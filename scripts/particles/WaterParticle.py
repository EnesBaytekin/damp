"""
Water particle — falls down, spreads sideways, fills gaps, flows on surfaces.
"""

from scripts.Grid import Grid, HEIGHT


def update(grid: Grid, x: int, y: int) -> None:
    """One simulation step for a water particle at (x, y)."""
    # 1 — fall straight down
    if y + 1 < HEIGHT:
        if grid.can_occupy(x, y + 1, 2):
            grid.swap(x, y, x, y + 1)
            return

    # 2 — spread sideways (alternating priority each frame)
    left = x - 1
    right = x + 1

    prefer_left = (grid.rng.random() < 0.5)

    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        if 0 <= nx < grid.width and grid.grid[y][nx] == 0:
            grid.swap(x, y, nx, y)
            return

    # 3 — diagonal down (fill corners)
    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        ny = y + 1
        if 0 <= nx < grid.width and ny < HEIGHT and grid.can_occupy(nx, ny, 2):
            grid.swap(x, y, nx, ny)
            return
