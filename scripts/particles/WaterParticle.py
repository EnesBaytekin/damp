"""
Water particle — falls, spreads, flows across chunk boundaries transparently.

Uses can_occupy() / swap() for cross-chunk movement.  No local bounds checks.
"""

from scripts.Chunk import Chunk as Grid, CHUNK_SIZE


def _in_chunk(grid: Grid, x: int, y: int) -> bool:
    return 0 <= x < grid.width and 0 <= y < grid.height


def _get_type(grid: Grid, x: int, y: int) -> int:
    """Get cell type.  Cross-chunk safe."""
    if _in_chunk(grid, x, y):
        return grid.grid[y][x]
    m = getattr(grid, 'manager', None)
    if m:
        return m.get_cell(grid._world_x(x), y)
    return 0


def _is_sand(grid: Grid, x: int, y: int) -> bool:
    """True if cell contains sand.  Cross-chunk safe."""
    if _in_chunk(grid, x, y):
        return grid.grid[y][x] == 1
    m = getattr(grid, 'manager', None)
    if m:
        return m.get_cell(grid._world_x(x), y) == 1
    return False


def _sand_not_full(grid: Grid, x: int, y: int) -> bool:
    """True if sand cell with wetness < 3.0.  Cross-chunk safe."""
    if _in_chunk(grid, x, y):
        return grid.grid[y][x] == 1 and grid.wetness[y][x] < 3.0
    m = getattr(grid, 'manager', None)
    if m:
        wx = grid._world_x(x)
        return m.get_cell(wx, y) == 1 and m.get_wetness(wx, y) < 3.0
    return False


def _wet_cell(grid: Grid, x: int, y: int) -> None:
    """Add 0.5 wetness to sand at (x, y).  Cross-chunk safe."""
    if _in_chunk(grid, x, y):
        grid.wetness[y][x] += 0.5
        grid.dirty.append((x, y))
    else:
        m = getattr(grid, 'manager', None)
        if m:
            wx = grid._world_x(x)
            cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
            tg = m.get_chunk(cx, create=False)
            if tg and 0 <= y < 90 and tg.grid[y][lx] == 1:
                tg.wetness[y][lx] += 0.5
                tg.dirty.append((lx, y))


# ── charge dump helpers ──────────────────────────────────

def _try_wet(grid: Grid, x: int, y: int) -> bool:
    """Dump 1 charge into adjacent sand.  Returns True if exhausted."""
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if _sand_not_full(grid, nx, ny):
                grid.water_charge[y][x] -= 1
                _wet_cell(grid, nx, ny)
                if grid.water_charge[y][x] == 0:
                    grid.grid[y][x] = 0
                    grid.water_charge[y][x] = 0
                    grid.dirty.append((x, y))
                    return True
                break
    return False


def _flow(grid: Grid, x: int, y: int) -> bool:
    """Try to move water.  Returns True if moved."""
    if y + 1 < grid.height:
        below = _get_type(grid, x, y + 1)
        if below == 0 or grid.can_occupy(x, y + 1, 2):
            grid.swap(x, y, x, y + 1)
            return True

    prefer_left = (grid.rng.random() < 0.5)
    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx = x + dx
        if _get_type(grid, nx, y) == 0:
            grid.swap(x, y, nx, y)
            return True

    for dx in ([-1, 1] if prefer_left else [1, -1]):
        nx, ny = x + dx, y + 1
        if ny < grid.height and _get_type(grid, nx, ny) == 0:
            grid.swap(x, y, nx, ny)
            return True
        if ny < grid.height and grid.can_occupy(nx, ny, 2):
            grid.swap(x, y, nx, ny)
            return True

    return False


def _dump_charge(grid: Grid, x: int, y: int) -> None:
    """Dump all charge into adjacent sand."""
    charge = grid.water_charge[y][x]
    if charge <= 0:
        return
    dumped = True
    while charge > 0 and dumped:
        dumped = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if _sand_not_full(grid, x + dx, y + dy):
                    grid.water_charge[y][x] -= 1
                    charge -= 1
                    _wet_cell(grid, x + dx, y + dy)
                    dumped = True
                    break
            if dumped:
                break
    if grid.water_charge[y][x] == 0:
        grid.grid[y][x] = 0
        grid.water_charge[y][x] = 0
        grid.dirty.append((x, y))


def update(grid: Grid, x: int, y: int) -> None:
    if grid.water_charge[y][x] > 0 and _try_wet(grid, x, y):
        return
    if _flow(grid, x, y):
        return
    _dump_charge(grid, x, y)
