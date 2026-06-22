"""
Sand particle — clean state machine:

  Awake → down if empty → diagonal if RNG passes → sleep if support enough
  Dry sand (level 0) never sleeps — always tries diagonals.
  Wet sand has lower diagonal chance and higher sleep threshold.

   Level | Diagonal | Sleep threshold | Max sleep frames
   ------|----------|-----------------|-----------------
   0 dry | 100%     | never sleeps    | —
   1     | 60%      | ≥4 neighbours   | 1800 (30s)
   2     | 20%      | ≥2 neighbours   | 9000 (150s)
   3     | 5%       | ≥1 neighbour    | ∞
"""

from scripts.Chunk import Chunk as Grid

DIAGONAL_CHANCE   = [1.0, 0.6, 0.2, 0.05]
SUPPORT_THRESHOLD = [999,   4,   2,    1]
MAX_SLEEP_FRAMES  = [0, 1800, 9000, 2_000_000_000]


def update(grid: Grid, x: int, y: int) -> None:
    wet = grid.wetness[y][x]
    level = min(int(wet), 3)
    h = grid.height

    # ── ASLEEP ─────────────────────────────────────────────
    if grid.asleep[y][x]:
        # Wake conditions (cheapest first)
        if grid.disturbed[y][x] == grid.frame:
            pass  # wake
        elif level < 3 and (grid.frame - grid.wake_frame[y][x]) > MAX_SLEEP_FRAMES[level]:
            pass  # timer expired
        elif grid.support_count(x, y) >= SUPPORT_THRESHOLD[level]:
            return  # stay sleeping
        # Wake up
        grid.asleep[y][x] = 0
        grid.wake_frame[y][x] = grid.frame

    # ── AWAKE — MOVEMENT ──────────────────────────────────

    # 1. Fall straight down
    if y + 1 < h and grid.can_occupy(x, y + 1, 1):
        grid.swap(x, y, x, y + 1)
        return

    # 2. Diagonal slides (gated by wetness)
    if grid.rng.random() < DIAGONAL_CHANCE[level]:
        prefer_left = grid.rng.random() < 0.5
        left = x - 1
        right = x + 1
        can_left  = x > 0 and y + 1 < h and grid.can_occupy(left, y + 1, 1)
        can_right = right < grid.width and y + 1 < h and grid.can_occupy(right, y + 1, 1)

        if can_left or can_right:
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

    # 3. Couldn't move → try to sleep
    if level > 0 and grid.support_count(x, y) >= SUPPORT_THRESHOLD[level]:
        grid.asleep[y][x] = 1
