"""
Sand particle — clean state machine.

Sleeping particles only wake when:
  a) Disturbed from above (something moved below them) AND support lost, OR
  b) Timer expired (level 1/2), OR
  c) Support count drops below threshold.

When disturbance wakes a particle that still has side support,
it immediately goes back to sleep.
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
        should_wake = False

        # Cheapest checks first
        if grid.disturbed[y][x] == grid.frame:
            should_wake = True  # disturbance detected
        elif level < 3 and (grid.frame - grid.wake_frame[y][x]) > MAX_SLEEP_FRAMES[level]:
            should_wake = True  # timer expired
        elif grid.support_count(x, y) < SUPPORT_THRESHOLD[level]:
            should_wake = True  # lost support
        else:
            return  # still sleeping peacefully

        if should_wake and level > 0 and grid.support_count(x, y) >= SUPPORT_THRESHOLD[level]:
            # Disturbance was below us, but side support still holds → stay asleep
            return

        # Really wake up
        grid.asleep[y][x] = 0
        grid.wake_frame[y][x] = grid.frame

    # ── AWAKE — MOVEMENT ──────────────────────────────────

    # 1. Fall straight down
    if y + 1 < h and grid.can_occupy(x, y + 1, 1):
        grid.swap(x, y, x, y + 1)
        return

    # 2. Diagonal slides (gated by wetness level)
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
