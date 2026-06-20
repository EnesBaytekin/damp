"""
Sand particle — falls down, slides on diagonals, displaces lighter particles (water).
"""

from scripts.Grid import Grid, HEIGHT


def update(grid: Grid, x: int, y: int) -> None:
    """One simulation step for a sand particle at (x, y)."""
    # 1 — fall straight down (swap with empty or water)
    if y + 1 < HEIGHT:
        if grid.can_occupy(x, y + 1, 1):
            grid.swap(x, y, x, y + 1)
            return

    # 2 — diagonal slides (alternate preference for natural cone shape)
    left = x - 1
    right = x + 1

    can_left = x > 0 and y + 1 < HEIGHT and grid.can_occupy(left, y + 1, 1)
    can_right = right < grid.width and y + 1 < HEIGHT and grid.can_occupy(right, y + 1, 1)

    if not can_left and not can_right:
        return

    prefer_left = (grid.rng.random() < 0.5)
    if prefer_left:
        if can_left:
            grid.swap(x, y, left, y + 1)
        elif can_right:
            grid.swap(x, y, right, y + 1)
    else:
        if can_right:
            grid.swap(x, y, right, y + 1)
        elif can_left:
            grid.swap(x, y, left, y + 1)
