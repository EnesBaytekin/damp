"""
Chunk — 32×32 cell tile of the infinite world.

Each chunk is self-contained with parallel arrays matching the old Grid
interface so existing particle update functions work unmodified.

Cross-chunk movement is handled transparently via the ChunkManager
reference: when a particle reaches a chunk edge, `swap()` and
`can_occupy()` delegate to the manager.
"""

import random

CHUNK_SIZE = 32
EMPTY = 0


class Chunk:
    """A single 32×32 chunk of the world. Interface-compatible with Grid."""

    __slots__ = (
        "cx", "cy",
        "grid", "updated", "frame", "rng", "particle_types",
        "dirty", "width", "height",
        "wetness", "asleep", "wake_frame", "water_charge", "disturbed",
        "manager",  # ChunkManager reference
        "filled_count",
    )

    def __init__(self, cx: int, cy: int, manager=None):
        self.cx = cx
        self.cy = cy
        self.width = CHUNK_SIZE
        self.height = CHUNK_SIZE
        self.manager = manager

        self.grid = [[EMPTY] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.updated = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.frame = 0
        self.rng = random.Random()
        self.particle_types: dict[int, dict] = {}
        self.dirty: list[tuple[int, int]] = []

        self.wetness      = [[0.0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.asleep       = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.wake_frame   = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.water_charge = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]
        self.disturbed    = [[0] * CHUNK_SIZE for _ in range(CHUNK_SIZE)]

        self.filled_count = 0

    # ── registry ────────────────────────────────────────────

    def register(self, type_id: int, props: dict) -> None:
        self.particle_types[type_id] = props

    # ── world coordinate helpers ────────────────────────────

    def _world(self, lx: int, ly: int) -> tuple[int, int]:
        """Convert local (lx, ly) to world (wx, wy)."""
        return self.cx * CHUNK_SIZE + lx, self.cy * CHUNK_SIZE + ly

    def _local(self, wx: int, wy: int) -> tuple[int, int, int, int]:
        """Convert world (wx, wy) to chunk coords and local coords."""
        return wx // CHUNK_SIZE, wy // CHUNK_SIZE, wx % CHUNK_SIZE, wy % CHUNK_SIZE

    # ── mutation helpers ────────────────────────────────────

    def spawn(self, lx: int, ly: int, type_id: int) -> bool:
        if not (0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE):
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
        """Swap two cells.  Cross-chunk moves are buffered via manager."""
        # Both in this chunk?
        if 0 <= lx2 < CHUNK_SIZE and 0 <= ly2 < CHUNK_SIZE:
            self._swap_local(lx1, ly1, lx2, ly2)
        else:
            # Cross-chunk — delegate to manager
            if self.manager:
                wx1, wy1 = self._world(lx1, ly1)
                wx2, wy2 = wx1 + (lx2 - lx1), wy1 + (ly2 - ly1)
                self.manager.add_cross_chunk_move(wx1, wy1, wx2, wy2)

    def _swap_local(self, lx1: int, ly1: int, lx2: int, ly2: int) -> None:
        """In-chunk swap."""
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

    # ── helpers used by particle update functions ───────────

    def can_occupy(self, lx: int, ly: int, mover_id: int) -> bool:
        if not (0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE):
            # Check cross-chunk via manager
            if self.manager:
                wx, wy = self._world(lx, ly)
                return self.manager.can_occupy_world(wx, wy, mover_id)
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
        """Count non-empty cells in 8-way neighbourhood (local + cross-chunk)."""
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = lx + dx, ly + dy
                if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE:
                    if self.grid[ny][nx] != EMPTY:
                        count += 1
                elif self.manager:
                    wx, wy = self._world(nx, ny)
                    if self.manager.get_cell(wx, wy) != EMPTY:
                        count += 1
        return count

    # ── drying ──────────────────────────────────────────────

    def _drying_step(self) -> None:
        DRY_RATE = 1/12000
        for ly in range(CHUNK_SIZE):
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

    # ── diffusion ───────────────────────────────────────────

    def _diffusion_step(self) -> None:
        for ly in range(CHUNK_SIZE):
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
                        if 0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE:
                            nw = self.wetness[ny][nx]
                            if self.grid[ny][nx] == 1 and w - nw >= 1.0:
                                candidates.append((nx, ny))
                        elif self.manager:
                            wx, wy = self._world(nx, ny)
                            nw = self.manager.get_wetness(wx, wy)
                            if self.manager.get_cell(wx, wy) == 1 and w - nw >= 1.0:
                                # Cross-chunk diffusion — record pending
                                self.manager.add_diffusion_transfer(
                                    self.cx, self.cy, lx, ly,
                                    wx, wy, w
                                )
                if not candidates:
                    continue
                tx, ty = self.rng.choice(candidates)
                self.wetness[ly][lx] -= 0.5
                self.wetness[ty][tx] += 0.5
                self.dirty.append((lx, ly))
                self.dirty.append((tx, ty))

    # ── simulation step ─────────────────────────────────────

    def step(self) -> None:
        """Advance this chunk by one frame."""
        self.frame += 1

        for ly in range(CHUNK_SIZE - 1, -1, -1):
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
