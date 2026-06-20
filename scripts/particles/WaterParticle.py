"""
Water particle — falls down, spreads sideways, fills gaps.

Wets adjacent sand (charge system): each water has 4 charge. Every frame
it can wet one adjacent sand particle (charge -= 1, sand.wetness += 1).
When charge hits 0 the water disappears.
"""

from scripts.Grid import Grid, HEIGHT


def update(grid: Grid, x: int, y: int) -> None:
    # ── 0 — wet adjacent sand ──────────────────────────────
    charge = grid.water_charge[y][x]
    if charge > 0:
        # Check all 8 neighbours — water can wet sand from any contact side
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < grid.width and 0 <= ny < grid.height:
                    if grid.grid[ny][nx] == 1 and grid.wetness[ny][nx] < 3:
                        # Wet this sand
                        grid.wetness[ny][nx] += 1
                        grid.water_charge[y][x] -= 1
                        grid.dirty.append((nx, ny))

                        if grid.water_charge[y][x] == 0:
                            # Water exhausted — disappear
                            grid.grid[y][x] = 0
                            grid.water_charge[y][x] = 0
                            grid.dirty.append((x, y))
                            return
                        break
            else:
                continue
            break

    # ── 1 — fall straight down ──────────────────────────────
    if y + 1 < HEIGHT:
        if grid.can_occupy(x, y + 1, 2):
            grid.swap(x, y, x, y + 1)
            return

    # ── 2 — spread sideways (alternating priority each frame) ──
    left = x - 1
    right = x + 1

    prefer_left = (grid.rng.random() < 0.5)

    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        if 0 <= nx < grid.width and grid.grid[y][nx] == 0:
            grid.swap(x, y, nx, y)
            return

    # ── 3 — diagonal down (fill corners) ──────────────────
    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        ny = y + 1
        if 0 <= nx < grid.width and ny < HEIGHT and grid.can_occupy(nx, ny, 2):
            grid.swap(x, y, nx, ny)
            return
