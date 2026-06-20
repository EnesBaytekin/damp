"""
Water particle — falls down, spreads sideways, fills gaps.

Wets adjacent sand as it flows: each frame water tries to dump 1 charge
into any adjacent unsaturated sand *before* moving, so it leaves a trail
of wet sand behind as it flows.  The remaining charge keeps it flowing.
Edge-flow: when below is empty, water checks diagonals — if there's sand
forming a wall, water flows *along* the wall instead of falling straight.
"""

from scripts.Grid import Grid


def _wet_adjacent(grid: Grid, x: int, y: int) -> bool:
    """Dump 1 charge into an adjacent unsaturated sand.  Returns True if
    the water was exhausted (charge hit 0)."""
    if grid.water_charge[y][x] <= 0:
        return False
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < grid.width and 0 <= ny < grid.height:
                if grid.grid[ny][nx] == 1 and grid.wetness[ny][nx] < 3.0:
                    grid.wetness[ny][nx] += 0.5
                    grid.water_charge[y][x] -= 1
                    grid.dirty.append((nx, ny))
                    if grid.water_charge[y][x] == 0:
                        grid.grid[y][x] = 0
                        grid.water_charge[y][x] = 0
                        grid.dirty.append((x, y))
                        return True
                    break
        else:
            continue
        break
    return False


def _flow(grid: Grid, x: int, y: int) -> bool:
    """Try to move the water particle.  Returns True if it moved."""
    # ── 1 — fall with edge-flow ─────────────────────────────
    if y + 1 < grid.height:
        below = grid.grid[y + 1][x]

        if below == 0:  # empty below — check for edge-flow
            prefer_left = (grid.rng.random() < 0.5)
            for dx in ([-1, 1] if prefer_left else [1, -1]):
                nx = x + dx
                ny = y + 1
                if 0 <= nx < grid.width and grid.grid[ny][nx] == 0:
                    wall_x = nx + dx
                    has_wall = False
                    if 0 <= wall_x < grid.width:
                        if grid.grid[ny][wall_x] == 1 or grid.grid[y][wall_x] == 1:
                            has_wall = True
                    if grid.grid[y][nx] == 1:
                        has_wall = True

                    if has_wall:
                        grid.swap(x, y, nx, ny)
                        return True

            grid.swap(x, y, x, y + 1)
            return True

        if grid.can_occupy(x, y + 1, 2):
            grid.swap(x, y, x, y + 1)
            return True

    # ── 2 — spread sideways ────────────────────────────────
    prefer_left = (grid.rng.random() < 0.5)

    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        if 0 <= nx < grid.width and grid.grid[y][nx] == 0:
            grid.swap(x, y, nx, y)
            return True

    # ── 3 — diagonal down ──────────────────────────────────
    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        ny = y + 1
        if 0 <= nx < grid.width and ny < grid.height and grid.can_occupy(nx, ny, 2):
            grid.swap(x, y, nx, ny)
            return True

    return False  # couldn't move


def update(grid: Grid, x: int, y: int) -> None:
    # ── 0 — wet adjacent sand (1 charge per frame while flowing) ─
    if grid.water_charge[y][x] > 0:
        if _wet_adjacent(grid, x, y):
            return  # exhausted — vanished

    # ── 1 — try to flow ─────────────────────────────────────
    if _flow(grid, x, y):
        return  # moved

    # ── 2 — can't move → dump remaining charge into sand ────
    charge = grid.water_charge[y][x]
    if charge > 0:
        while charge > 0:
            dumped = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < grid.width and 0 <= ny < grid.height:
                        if grid.grid[ny][nx] == 1 and grid.wetness[ny][nx] < 3.0:
                            grid.wetness[ny][nx] += 0.5
                            grid.water_charge[y][x] -= 1
                            grid.dirty.append((nx, ny))
                            charge -= 1
                            dumped = True
                            break
                if dumped:
                    break
            if not dumped:
                break

        if grid.water_charge[y][x] == 0:
            grid.grid[y][x] = 0
            grid.water_charge[y][x] = 0
            grid.dirty.append((x, y))
