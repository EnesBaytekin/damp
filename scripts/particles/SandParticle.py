"""
Sand particle — falls down, slides on diagonals, supports sleep/wake mechanics.

Behaviour is driven by the particle's *wetness* level (0-3):

  Level | Fall  | Diagonal | Sleep threshold | Max sleep | Re-sleep delay
  ------|-------|----------|-----------------|-----------|---------------
  0 dry | always | 100%    | never sleeps    | —         | —
  1     | always |  60%    | ≥4 neighbours   | 60 fr     | 5 fr
  2     | always |  20%    | ≥2 neighbours   | 300 fr    | 15 fr
  3     | always |   0%    | ≥1 neighbour    | infinite  | 30 fr
"""

from scripts.Grid import Grid, HEIGHT

# ── wetness-level tables ──────────────────────────────────────
# Indexed by wetness value (0-3)
DIAGONAL_CHANCE   = [1.0, 0.6, 0.2, 0.0]
SUPPORT_THRESHOLD = [999,   4,   2,   1]
MAX_SLEEP_FRAMES  = [0,   60, 300, 2_000_000_000]
RESLEEP_DELAY     = [0,    5,  15,  30]


def update(grid: Grid, x: int, y: int) -> None:
    """One simulation step for a sand particle at (x, y)."""
    wet = grid.wetness[y][x]
    wet = min(wet, 3)  # clamp

    # ── SLEEP CHECK ─────────────────────────────────────────
    if grid.asleep[y][x]:
        support = grid.support_count(x, y)
        wake = False
        if grid.disturbed[y][x] == grid.frame:
            wake = True                         # disturbance above
        elif support < SUPPORT_THRESHOLD[wet]:
            wake = True                         # lost support
        elif wet < 3 and (grid.frame - grid.wake_frame[y][x]) > MAX_SLEEP_FRAMES[wet]:
            wake = True                         # timer expired

        if not wake:
            return  # stay asleep

        # Wake up
        grid.asleep[y][x] = 0
        grid.wake_frame[y][x] = grid.frame
        # fall through to movement

    # ── MOVEMENT ────────────────────────────────────────────

    # 1 — fall straight down (always try, regardless of wetness)
    if y + 1 < HEIGHT and grid.can_occupy(x, y + 1, 1):
        grid.swap(x, y, x, y + 1)
        return

    # 2 — diagonal slides (chance decreases with wetness)
    if grid.rng.random() < DIAGONAL_CHANCE[wet]:
        left = x - 1
        right = x + 1
        can_left  = x > 0 and y + 1 < HEIGHT and grid.can_occupy(left, y + 1, 1)
        can_right = right < grid.width and y + 1 < HEIGHT and grid.can_occupy(right, y + 1, 1)

        if can_left or can_right:
            prefer_left = grid.rng.random() < 0.5
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
            return

    # ── COULDN'T MOVE → try to sleep ──────────────────────
    if wet >= 1:
        support = grid.support_count(x, y)
        if support >= SUPPORT_THRESHOLD[wet]:
            frames_awake = grid.frame - grid.wake_frame[y][x]
            if frames_awake >= RESLEEP_DELAY[wet]:
                grid.asleep[y][x] = 1
