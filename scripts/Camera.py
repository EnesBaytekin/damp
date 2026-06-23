"""
Camera — 2x zoom, 80×45 viewport, follows player in X and Y.

Rendered viewport is 80×45 cells, each rendered as 2×2 pixels
on the 160×90 screen surface.
"""

from scripts.Chunk import CHUNK_SIZE


class Camera:
    def __init__(self):
        self.x = 0.0        # world coord of viewport top-left
        self.y = 0.0
        self.w = 80         # viewport width (logical cells)
        self.h = 45         # viewport height (logical cells)
        self.zoom = 2       # each cell = 2×2 screen pixels

    def follow(self, target_x: float, target_y: float, smooth: float = 0.1):
        desired_x = target_x - self.w / 2
        desired_y = target_y - self.h / 2
        self.x += (desired_x - self.x) * smooth
        self.y += (desired_y - self.y) * smooth
        # Snap to integer grid for pixel-perfect alignment
        self.x = round(self.x)
        self.y = round(self.y)

    def snap(self, target_x: float, target_y: float):
        self.x = target_x - self.w / 2
        self.y = target_y - self.h / 2

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """World → screen pixel (×2 zoom)."""
        return (wx - self.x) * self.zoom, (wy - self.y) * self.zoom

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Screen pixel → world coord."""
        return sx / self.zoom + self.x, sy / self.zoom + self.y

    def get_visible_chunks(self) -> list[int]:
        """Return the 2 chunk indices that are visible on screen."""
        left_cx = int(self.x // CHUNK_SIZE)
        right_cx = int((self.x + self.w - 1) // CHUNK_SIZE)
        return left_cx, right_cx
