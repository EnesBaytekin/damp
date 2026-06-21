"""
Camera — follows the player horizontally, world is fixed height (90px).
"""

from scripts.Chunk import CHUNK_SIZE


class Camera:
    """Camera with horizontal scrolling only. Y is fixed (world is 90 tall)."""

    def __init__(self, screen_w: int = 160, screen_h: int = 90):
        self.x = 0.0
        self.y = 0.0  # always 0 — world is full-screen height
        self.w = screen_w
        self.h = screen_h

    def follow(self, target_x: float, target_y: float, smooth: float = 0.1):
        desired_x = target_x - self.w / 2
        self.x += (desired_x - self.x) * smooth
        self.y = 0.0  # locked

    def snap(self, target_x: float, target_y: float):
        self.x = target_x - self.w / 2
        self.y = 0.0

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return wx - self.x, wy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return sx + self.x, sy

    def get_visible_chunks(self) -> set[int]:
        min_cx = int(self.x // CHUNK_SIZE)
        max_cx = int((self.x + self.w) // CHUNK_SIZE)
        return set(range(min_cx - 1, max_cx + 2))

    def is_visible(self, wx: float, wy: float, margin: int = 8) -> bool:
        return (-margin <= wx - self.x < self.w + margin and
                -margin <= wy < self.h + margin)
