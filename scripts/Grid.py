"""
Grid — the core simulation data structure.

Manages a 2D grid of particle types (320x180), tracks per-frame updates
via a frame-counter marking system (avoids resetting a full boolean array),
and maintains a dirty-rect list for efficient rendering.
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
    )

    def __init__(self, width: int = WIDTH, height: int = HEIGHT):
        self.width = width
        self.height = height
        # grid[y][x] = particle type ID (0 = EMPTY)
        self.grid = [[EMPTY] * width for _ in range(height)]
        # Frame-number marker: updated[y][x] == self.frame means "already processed"
        self.updated = [[0] * width for _ in range(height)]
        self.frame = 0
        self.rng = random.Random()
        # Particle type registry: {type_id: {"name": str, "color": tuple, "density": int, "update": callable}}
        self.particle_types: dict[int, dict] = {}
        # Cells that changed this frame — list of (x, y)
        self.dirty: list[tuple[int, int]] = []

    # ── Registry ──────────────────────────────────────────────

    def register(self, type_id: int, props: dict) -> None:
        """Register a particle type."""
        self.particle_types[type_id] = props

    # ── Mutation helpers ──────────────────────────────────────

    def spawn(self, x: int, y: int, type_id: int) -> bool:
        """Place a single particle at (x, y). Returns False if occupied or out of bounds."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        if self.grid[y][x] != EMPTY:
            return False
        self.grid[y][x] = type_id
        self.dirty.append((x, y))
        return True

    def swap(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Swap two cells (handles displacement)."""
        self.grid[y1][x1], self.grid[y2][x2] = self.grid[y2][x2], self.grid[y1][x1]
        self.updated[y1][x1] = self.frame
        self.updated[y2][x2] = self.frame
        self.dirty.append((x1, y1))
        self.dirty.append((x2, y2))

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

    # ── Simulation step ──────────────────────────────────────

    def step(self) -> None:
        """Advance the simulation by one frame."""
        self.frame += 1

        for y in range(self.height - 1, -1, -1):
            # Alternate scan direction every frame to avoid bias
            if self.frame & 1:
                x_range = range(self.width - 1, -1, -1)   # right → left
            else:
                x_range = range(self.width)                # left → right

            for x in x_range:
                type_id = self.grid[y][x]
                if type_id == EMPTY or self.updated[y][x] == self.frame:
                    continue
                fn = self.particle_types.get(type_id, {}).get("update")
                if fn is None:
                    self.updated[y][x] = self.frame
                else:
                    fn(self, x, y)
