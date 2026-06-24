"""
Template — quest building templates for the player to construct.
Only generates chunky blob-like shapes (no checkerboard, no stripes).
"""

import random
import math


class Template:
    def __init__(self, seed: int = 0):
        self.seed = seed
        self.width = 0
        self.height = 0
        self.grid = []
        self.name = ""

    def generate(self, area: int = 60):
        rng = random.Random(self.seed)
        w = rng.randint(10, 35)
        h = rng.randint(10, 30)
        self.width = w
        self.height = h
        self.grid = [[0] * w for _ in range(h)]
        names = ["castle", "tower", "fort", "keep", "bastion", "citadel", "stronghold", "outpost"]
        self.name = rng.choice(names)

        # Pick a chunky generation method
        rng.choice([self._gen_blobs, self._gen_blobs_and_bridge, self._gen_thick_walls])(rng)

        # Ensure at least some cells are filled
        if sum(row.count(1) for row in self.grid) < 8:
            for _ in range(30):
                x, y = rng.randint(0, w-1), rng.randint(0, h-1)
                self.grid[y][x] = 1

        # Shift each column to bottom
        for x in range(w):
            col = [self.grid[y][x] for y in range(h)]
            if 1 not in col:
                continue
            bottom_sand = max(y for y in range(h) if col[y] == 1)
            shift = (h - 1) - bottom_sand
            if shift > 0:
                for y in range(h - 1, shift - 1, -1):
                    self.grid[y][x] = self.grid[y - shift][x]
                for y in range(shift):
                    self.grid[y][x] = 0

        # Trim fully empty bottom rows
        while self.height > 3 and all(self.grid[self.height - 1][x] == 0 for x in range(self.width)):
            self.grid.pop()
            self.height -= 1

        return self

    def _gen_blobs(self, rng):
        w, h = self.width, self.height
        n = rng.randint(3, 7)
        for _ in range(n):
            cx, cy = rng.randint(0, w-1), rng.randint(0, h-1)
            r = rng.uniform(2.5, 6)
            for y in range(h):
                for x in range(w):
                    if (x - cx)*(x - cx) + (y - cy)*(y - cy) <= r*r:
                        self.grid[y][x] = 1

    def _gen_blobs_and_bridge(self, rng):
        w, h = self.width, self.height
        n = rng.randint(3, 6)
        blobs = []
        for _ in range(n):
            cx, cy = rng.randint(0, w-1), rng.randint(0, h-1)
            r = rng.uniform(2, 5)
            blobs.append((cx, cy, r))
            for y in range(h):
                for x in range(w):
                    if (x - cx)*(x - cx) + (y - cy)*(y - cy) <= r*r:
                        self.grid[y][x] = 1
        # Connect some blobs with thick bridges
        for i in range(len(blobs) - 1):
            x1, y1, r1 = blobs[i]
            x2, y2, r2 = blobs[i + 1]
            steps = max(abs(x2 - x1), abs(y2 - y1))
            if steps == 0: continue
            for t in range(steps + 1):
                px = int(x1 + (x2 - x1) * t / steps)
                py = int(y1 + (y2 - y1) * t / steps)
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            self.grid[ny][nx] = 1

    def _gen_thick_walls(self, rng):
        w, h = self.width, self.height
        n = rng.randint(2, 4)
        for _ in range(n):
            if rng.random() < 0.5:
                y = rng.randint(0, h-1)
                for x in range(w):
                    if rng.random() < 0.65:
                        for dy in range(-1, 2):
                            ny = y + dy
                            if 0 <= ny < h:
                                self.grid[ny][x] = 1
            else:
                x = rng.randint(0, w-1)
                for y in range(h):
                    if rng.random() < 0.65:
                        for dx in range(-1, 2):
                            nx = x + dx
                            if 0 <= nx < w:
                                self.grid[y][nx] = 1

    def get_rect(self):
        return self.width, self.height

    def score(self, world_get_cell, world_x, world_y):
        correct, total = 0, self.width * self.height
        if total == 0: return (0, 0, 0)
        for ty in range(self.height):
            for tx in range(self.width):
                want = self.grid[ty][tx] == 1
                cell = world_get_cell(world_x + tx, world_y + ty)
                if want == (cell == 1):
                    correct += 1
        return (correct, total, int(correct * 100 / total))
