"""
Chunk — 32×90 column slice of the horizontally-infinite world.

Each chunk spans the full 90-pixel height but only 32 pixels wide.
Chunks are indexed only by cx (horizontal chunk coordinate); cy is
always 0 since the world only extends horizontally.
"""

import random

CHUNK_SIZE = 80   # width
CHUNK_HEIGHT = 90 # full height
EMPTY = 0


class Chunk:
    """A 32-wide × 90-tall column. Interface-compatible with old Grid."""

    __slots__ = (
        "cx", "cy",
        "grid", "updated", "frame", "rng", "particle_types",
        "dirty", "width", "height",
        "wetness", "asleep", "wake_frame", "water_charge", "disturbed",
        "manager", "filled_count",
    )

    def __init__(self, cx: int, manager=None):
        self.cx = cx
        self.cy = 0
        self.width = CHUNK_SIZE
        self.height = CHUNK_HEIGHT
        self.manager = manager

        self.grid = [[EMPTY] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.updated = [[0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.frame = 0
        self.rng = random.Random()
        self.particle_types: dict[int, dict] = {}
        self.dirty: list[tuple[int, int]] = []

        self.wetness      = [[0.0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.asleep       = [[0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.wake_frame   = [[0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.water_charge = [[0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]
        self.disturbed    = [[0] * CHUNK_SIZE for _ in range(CHUNK_HEIGHT)]

        self.filled_count = 0

    def register(self, type_id: int, props: dict) -> None:
        self.particle_types[type_id] = props

    # ── coordinate helpers ────────────────────────────────

    def _world_x(self, lx: int) -> int:
        return self.cx * CHUNK_SIZE + lx

    def _local_x(self, wx: int) -> int:
        return wx % CHUNK_SIZE

    # ── mutation helpers ────────────────────────────────────

    def spawn(self, lx: int, ly: int, type_id: int) -> bool:
        if not (0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_HEIGHT):
            return False
        if self.grid[ly][lx] != EMPTY:
            return False
        self.grid[ly][lx] = type_id
        self.wetness[ly][lx] = 0.0
        self.asleep[ly][lx] = 0
        self.wake_frame[ly][lx] = 0
        self.water_charge[ly][lx] = 6 if type_id == 2 else 0
        self.dirty.append((lx, ly))
        self.filled_count += 1
        return True

    def swap(self, lx1: int, ly1: int, lx2: int, ly2: int) -> None:
        """Swap two cells. Cross-chunk moves delegated to manager."""
        if 0 <= lx2 < CHUNK_SIZE and 0 <= ly2 < CHUNK_HEIGHT:
            self._swap_local(lx1, ly1, lx2, ly2)
        elif self.manager:
            wx1, wy1 = self._world_x(lx1), ly1
            wx2, wy2 = wx1 + (lx2 - lx1), ly1 + (ly2 - ly1)
            self.manager.add_cross_chunk_move(wx1, wy1, wx2, wy2)

    def _swap_local(self, lx1: int, ly1: int, lx2: int, ly2: int) -> None:
        t1, t2 = self.grid[ly1][lx1], self.grid[ly2][lx2]
        self.grid[ly1][lx1], self.grid[ly2][lx2] = t2, t1
        self.wetness[ly1][lx1], self.wetness[ly2][lx2] = self.wetness[ly2][lx2], self.wetness[ly1][lx1]
        self.asleep[ly1][lx1], self.asleep[ly2][lx2] = self.asleep[ly2][lx2], self.asleep[ly1][lx1]
        self.wake_frame[ly1][lx1], self.wake_frame[ly2][lx2] = self.wake_frame[ly2][lx2], self.wake_frame[ly1][lx1]
        self.water_charge[ly1][lx1], self.water_charge[ly2][lx2] = self.water_charge[ly2][lx2], self.water_charge[ly1][lx1]

        self.updated[ly1][lx1] = self.frame
        self.updated[ly2][lx2] = self.frame
        self.dirty.append((lx1, ly1))
        self.dirty.append((lx2, ly2))

        has_sand = (t1 == 1) or (t2 == 1)
        if has_sand:
            if ly1 > 0:
                self.disturbed[ly1 - 1][lx1] = self.frame
            if ly2 > 0:
                self.disturbed[ly2 - 1][lx2] = self.frame

    def can_occupy(self, lx: int, ly: int, mover_id: int) -> bool:
        if not (0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_HEIGHT):
            if self.manager:
                wx = self._world_x(lx)
                return self.manager.can_occupy_world(wx, ly, mover_id)
            return False
        target = self.grid[ly][lx]
        if target == EMPTY:
            return True
        mover = self.particle_types.get(mover_id)
        target_t = self.particle_types.get(target)
        if mover and target_t:
            return mover["density"] > target_t["density"]
        return False

    def support_count(self, lx: int, ly: int) -> int:
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = lx + dx, ly + dy
                if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_HEIGHT:
                    if self.grid[ny][nx] != EMPTY:
                        count += 1
                elif self.manager:
                    wx = self._world_x(nx)
                    if self.manager.get_cell(wx, ny) != EMPTY:
                        count += 1
        return count

    def _drying_step(self) -> None:
        DRY_RATE = 1/12000
        for ly in range(CHUNK_HEIGHT):
            for lx in range(CHUNK_SIZE):
                if self.grid[ly][lx] != 1:
                    continue
                w = self.wetness[ly][lx]
                if w <= 0.0:
                    continue
                if self.rng.random() < DRY_RATE:
                    self.wetness[ly][lx] = max(0.0, w - 0.25)
                    self.dirty.append((lx, ly))
                    if w - 0.25 <= 0.0 and self.asleep[ly][lx]:
                        self.asleep[ly][lx] = 0
                        self.wake_frame[ly][lx] = self.frame

    def _diffusion_step(self) -> None:
        for ly in range(CHUNK_HEIGHT):
            for lx in range(CHUNK_SIZE):
                if self.grid[ly][lx] != 1:
                    continue
                w = self.wetness[ly][lx]
                if w < 1.0:
                    continue
                if self.rng.random() > w * 0.1:
                    continue
                candidates = []
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = lx + dx, ly + dy
                        if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_HEIGHT:
                            nw = self.wetness[ny][nx]
                            if self.grid[ny][nx] == 1 and w - nw >= 1.0:
                                candidates.append((nx, ny))
                        elif self.manager:
                            wx = self._world_x(nx)
                            nw = self.manager.get_wetness(wx, ny)
                            if self.manager.get_cell(wx, ny) == 1 and w - nw >= 1.0:
                                self.manager.add_diffusion_transfer(
                                    self.cx, 0, lx, ly, wx, ny, w)
                if not candidates:
                    continue
                tx, ty = self.rng.choice(candidates)
                self.wetness[ly][lx] -= 0.5
                self.wetness[ty][tx] += 0.5
                self.dirty.append((lx, ly))
                self.dirty.append((tx, ty))

    def step(self) -> None:
        """Advance this chunk by one frame."""
        self.frame += 1

        for ly in range(CHUNK_HEIGHT - 1, -1, -1):
            if self.frame & 1:
                x_range = range(CHUNK_SIZE - 1, -1, -1)
            else:
                x_range = range(CHUNK_SIZE)

            for lx in x_range:
                type_id = self.grid[ly][lx]
                if type_id == EMPTY or self.updated[ly][lx] == self.frame:
                    continue
                if type_id == 1 and self.asleep[ly][lx] and self.disturbed[ly][lx] != self.frame:
                    if self.wetness[ly][lx] >= 3.0 or (self.frame - self.wake_frame[ly][lx]) <= 1800:
                        self.updated[ly][lx] = self.frame
                        continue
                fn = self.particle_types.get(type_id, {}).get("update")
                if fn is None:
                    self.updated[ly][lx] = self.frame
                else:
                    fn(self, lx, ly)

        self._drying_step()
        self._diffusion_step()
