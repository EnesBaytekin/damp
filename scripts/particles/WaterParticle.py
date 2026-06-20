"""
Water particle — falls down, spreads sideways, fills gaps.

Wets adjacent sand: each water has 6 charge, dumps ALL remaining charge
into adjacent sand in one go (each charge = 0.5 wetness).  This creates
concentrated wet spots that then diffuse through the pile.
"""

from scripts.Grid import Grid


def update(grid: Grid, x: int, y: int) -> None:
    charge = grid.water_charge[y][x]

    # ── 0 — dump all charge into adjacent sand at once ──────
    if charge > 0:
        targets = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < grid.width and 0 <= ny < grid.height:
                    if grid.grid[ny][nx] == 1 and grid.wetness[ny][nx] < 3.0:
                        targets.append((nx, ny, grid.wetness[ny][nx]))

        if targets:
            targets.sort(key=lambda t: t[2])  # driest first

            for nx, ny, _ in targets:
                while grid.wetness[ny][nx] < 3.0 and grid.water_charge[y][x] > 0:
                    grid.wetness[ny][nx] += 0.5
                    grid.water_charge[y][x] -= 1
                    grid.dirty.append((nx, ny))

                if grid.water_charge[y][x] == 0:
                    grid.grid[y][x] = 0
                    grid.water_charge[y][x] = 0
                    grid.dirty.append((x, y))
                    return

    # ── 1 — fall straight down ──────────────────────────────
    if y + 1 < grid.height:
        if grid.can_occupy(x, y + 1, 2):
            grid.swap(x, y, x, y + 1)
            return

    # ── 2 — spread sideways ────────────────────────────────
    left = x - 1
    right = x + 1
    prefer_left = (grid.rng.random() < 0.5)

    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        if 0 <= nx < grid.width and grid.grid[y][nx] == 0:
            grid.swap(x, y, nx, y)
            return

    # ── 3 — diagonal down ──────────────────────────────────
    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        ny = y + 1
        if 0 <= nx < grid.width and ny < grid.height and grid.can_occupy(nx, ny, 2):
            grid.swap(x, y, nx, ny)
            return
