"""
Camera — follows the player, translates between world and screen coordinates.
"""

from scripts.Chunk import CHUNK_SIZE


class Camera:
    """World-space camera.  Screen is 160×90 logical pixels."""

    def __init__(self, screen_w: int = 160, screen_h: int = 90):
        self.x = 0.0          # world position of viewport top-left
        self.y = 0.0
        self.w = screen_w
        self.h = screen_h

    def follow(self, target_x: float, target_y: float, smooth: float = 0.1):
        """Centre the camera on a target (player)."""
        desired_x = target_x - self.w / 2
        desired_y = target_y - self.h / 2
        self.x += (desired_x - self.x) * smooth
        self.y += (desired_y - self.y) * smooth

    def snap(self, target_x: float, target_y: float):
        """Immediately centre on target."""
        self.x = target_x - self.w / 2
        self.y = target_y - self.h / 2

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return wx - self.x, wy - self.y

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return sx + self.x, sy + self.y

    def get_visible_chunks(self) -> set[tuple[int, int]]:
        """Return set of (cx, cy) for chunks intersecting the viewport."""
        min_cx = int(self.x // CHUNK_SIZE)
        min_cy = int(self.y // CHUNK_SIZE)
        max_cx = int((self.x + self.w) // CHUNK_SIZE)
        max_cy = int((self.y + self.h) // CHUNK_SIZE)
        result = set()
        for cy in range(min_cy - 1, max_cy + 2):
            for cx in range(min_cx - 1, max_cx + 2):
                result.add((cx, cy))
        return result

    def is_visible(self, wx: float, wy: float, margin: int = 8) -> bool:
        return (-margin <= wx - self.x < self.w + margin and
                -margin <= wy - self.y < self.h + margin)
