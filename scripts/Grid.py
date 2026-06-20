"""
Grid — the core simulation data structure.

Manages a 2D grid of particle types (160x90), per-particle state fields
(wetness, asleep, water_charge), a frame-counter marking system for
double-processing prevention, and a dirty-rect list for efficient rendering.
"""

import random

WIDTH = 160
HEIGHT = 90
EMPTY = 0


class Grid:
    """The simulation grid. Owns no rendering state — just data + update orchestration."""

    __slots__ = (
        "grid", "updated", "frame", "rng", "particle_types",
        "dirty", "width", "height",
        "wetness",       # [y][x] → 0-3 (SAND only)
        "asleep",        # [y][x] → bool (SAND only)
        "wake_frame",    # [y][x] → frame# of last wake (SAND only)
        "water_charge",  # [y][x] → 0-4 (WATER only, spawn=4)
        "disturbed",     # [y][x] → frame# when last disturbed
    )

    def __init__(self, width: int = WIDTH, height: int = HEIGHT):
        self.width = width
        self.height = height
        self.grid = [[EMPTY] * width for _ in range(height)]
        self.updated = [[0] * width for _ in range(height)]
        self.frame = 0
        self.rng = random.Random()
        self.particle_types: dict[int, dict] = {}
        self.dirty: list[tuple[int, int]] = []

        # Per-particle state arrays
        self.wetness      = [[0] * width for _ in range(height)]
        self.asleep       = [[0] * width for _ in range(height)]
        self.wake_frame   = [[0] * width for _ in range(height)]
        self.water_charge = [[0] * width for _ in range(height)]
        self.disturbed    = [[0] * width for _ in range(height)]

    # ── Registry ──────────────────────────────────────────────

    def register(self, type_id: int, props: dict) -> None:
        """Register a particle type."""
        self.particle_types[type_id] = props

    # ── Mutation helpers ──────────────────────────────────────

    def spawn(self, x: int, y: int, type_id: int) -> bool:
        """Place a single particle at (x, y). Returns False if occupied or OOB."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self.grid[y][x] != EMPTY:
            return False

        self.grid[y][x] = type_id
        self.wetness[y][x] = 0
        self.asleep[y][x] = 0
        self.wake_frame[y][x] = 0
        self.water_charge[y][x] = 4 if type_id == 2 else 0
        self.dirty.append((x, y))
        return True

    def swap(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Swap two cells — all state fields follow the particle."""
        # Types
        self.grid[y1][x1], self.grid[y2][x2] = self.grid[y2][x2], self.grid[y1][x1]
        # Extra fields (swap so they stay with the moving particle)
        self.wetness[y1][x1], self.wetness[y2][x2] = self.wetness[y2][x2], self.wetness[y1][x1]
        self.asleep[y1][x1], self.asleep[y2][x2] = self.asleep[y2][x2], self.asleep[y1][x1]
        self.wake_frame[y1][x1], self.wake_frame[y2][x2] = self.wake_frame[y2][x2], self.wake_frame[y1][x1]
        self.water_charge[y1][x1], self.water_charge[y2][x2] = self.water_charge[y2][x2], self.water_charge[y1][x1]

        self.updated[y1][x1] = self.frame
        self.updated[y2][x2] = self.frame
        self.dirty.append((x1, y1))
        self.dirty.append((x2, y2))

        # Mark cells above as disturbed (avalanche / wake-up propagation)
        if y1 > 0:
            self.disturbed[y1 - 1][x1] = self.frame
        if y2 > 0:
            self.disturbed[y2 - 1][x2] = self.frame

    # ── Per-type helpers used by particle update functions ─────

    def can_occupy(self, x: int, y: int, mover_id: int) -> bool:
        """Can a particle of *mover_id* move into cell (x, y)?"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        target = self.grid[y][x]
        if target == EMPTY:
            return True
        mover = self.particle_types.get(mover_id)
        target_t = self.particle_types.get(target)
        if mover and target_t:
            return mover["density"] > target_t["density"]
        return False

    # ── Support query (used by particle scripts) ──────────────

    def support_count(self, x: int, y: int) -> int:
        """Count non-empty cells in the 8-way Moore neighbourhood."""
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.grid[ny][nx] != EMPTY:
                        count += 1
        return count

    # ── Drying ────────────────────────────────────────────────

    def _drying_step(self) -> None:
        """Desynchronised drying — each particle rolls its own chance.

        Higher wetness dries more slowly (more stable), lower wetness
        dries faster.  Expected level lifetime at 60 fps:
          wetness 3 → 2:  ~60 s  (1/3600 per frame)
          wetness 2 → 1:  ~30 s  (1/1800)
          wetness 1 → 0:  ~15 s  (1/900)
          full 3 → 0:     ~105 s
        """
        DRY_CHANCE = [0, 1/900, 1/1800, 1/3600]
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] != 1:
                    continue
                w = self.wetness[y][x]
                if w <= 0:
                    continue
                if self.rng.random() < DRY_CHANCE[w]:
                    self.wetness[y][x] -= 1
                    self.dirty.append((x, y))
                    if w == 1 and self.asleep[y][x]:
                        self.asleep[y][x] = 0
                        self.wake_frame[y][x] = self.frame

    # ── Wetness diffusion ─────────────────────────────────────

    def _diffusion_step(self) -> None:
        """Desynchronised slow wetness transfer.

        Each particle has a ~1.7% chance per frame to attempt diffusion
        (natural desync — no global timer).  Only transfers when
        wetness *difference >= 2*, so 3→3, 3→2, and 1→0 never happen.
        """
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] != 1:
                    continue
                w = self.wetness[y][x]
                if w < 2:          # at least 2 needed to donate
                    continue
                if self.rng.random() > 1/60:   # ~1.7% this frame
                    continue

                # Collect neighbours that are at least 2 levels drier
                candidates = []
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if self.grid[ny][nx] == 1 and w - self.wetness[ny][nx] >= 2:
                                candidates.append((nx, ny))
                if not candidates:
                    continue
                tx, ty = self.rng.choice(candidates)
                self.wetness[y][x] -= 1
                self.wetness[ty][tx] += 1
                self.dirty.append((x, y))
                self.dirty.append((tx, ty))

    # ── Simulation step ──────────────────────────────────────

    def step(self) -> None:
        """Advance the simulation by one frame."""
        self.frame += 1

        for y in range(self.height - 1, -1, -1):
            if self.frame & 1:
                x_range = range(self.width - 1, -1, -1)
            else:
                x_range = range(self.width)

            for x in x_range:
                type_id = self.grid[y][x]
                if type_id == EMPTY or self.updated[y][x] == self.frame:
                    continue
                fn = self.particle_types.get(type_id, {}).get("update")
                if fn is None:
                    self.updated[y][x] = self.frame
                else:
                    fn(self, x, y)

        self._drying_step()
        self._diffusion_step()
