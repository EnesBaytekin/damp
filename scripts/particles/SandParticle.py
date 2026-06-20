"""
Sand particle — falls down, slides on diagonals, supports sleep/wake mechanics.

Behaviour is driven by the particle's *wetness* level (float → int floor):

  Level | Fall  | Diagonal | Sleep threshold | Max sleep | Re-sleep delay
  ------|-------|----------|-----------------|-----------|---------------
  0 dry | always | 100%    | never sleeps    | —         | —
  1     | always |  60%    | ≥4 neighbours   | 30 s      | 1.5 s
  2     | always |  20%    | ≥2 neighbours   | 150 s     | 3 s
  3     | always |   0%    | ≥1 neighbour    | infinite  | 6 s
"""

from scripts.Grid import Grid

# ── wetness-level tables ──────────────────────────────────────
# Indexed by int wetness level (0-3)
DIAGONAL_CHANCE   = [1.0, 0.6, 0.2, 0.0]
SUPPORT_THRESHOLD = [999,   4,   2,   1]
MAX_SLEEP_FRAMES  = [0, 1800, 9000, 2_000_000_000]  # 30s / 150s / ∞
RESLEEP_DELAY     = [0,   90,  180,  360]             # 1.5s / 3s / 6s


def update(grid: Grid, x: int, y: int) -> None:
    """One simulation step for a sand particle at (x, y)."""
    wet = grid.wetness[y][x]          # float
    level = min(int(wet), 3)          # 0-3 for table lookups
    h = grid.height

    # ── SLEEP CHECK ─────────────────────────────────────────
    if grid.asleep[y][x]:
        support = grid.support_count(x, y)
        wake = False
        if grid.disturbed[y][x] == grid.frame:
            wake = True                         # disturbance above
        elif support < SUPPORT_THRESHOLD[level]:
            wake = True                         # lost support
        elif level < 3 and (grid.frame - grid.wake_frame[y][x]) > MAX_SLEEP_FRAMES[level]:
            wake = True                         # timer expired

        if not wake:
            return  # stay asleep

        # Wake up
        grid.asleep[y][x] = 0
        grid.wake_frame[y][x] = grid.frame
        # fall through to movement

    # ── MOVEMENT ────────────────────────────────────────────

    # 1 — fall straight down (always try, regardless of wetness)
    if y + 1 < h and grid.can_occupy(x, y + 1, 1):
        grid.swap(x, y, x, y + 1)
        return

    # 2 — diagonal slides (chance decreases with wetness level)
    if grid.rng.random() < DIAGONAL_CHANCE[level]:
        left = x - 1
        right = x + 1
        can_left  = x > 0 and y + 1 < h and grid.can_occupy(left, y + 1, 1)
        can_right = right < grid.width and y + 1 < h and grid.can_occupy(right, y + 1, 1)

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
    if level >= 1:
        support = grid.support_count(x, y)
        if support >= SUPPORT_THRESHOLD[level]:
            frames_awake = grid.frame - grid.wake_frame[y][x]
            if frames_awake >= RESLEEP_DELAY[level]:
                grid.asleep[y][x] = 1
