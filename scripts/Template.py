"""
Template — quest building templates.
Generates recognisable castle shapes with varied silhouettes.
"""

import random
import math


class Template:
    FONT = {
        '0':('11110','10001','10001','10001','10001','10001','11110'),
        '1':('00100','01100','00100','00100','00100','00100','11111'),
        '2':('11110','00001','00001','11110','10000','10000','11111'),
        '3':('11110','00001','00001','11110','00001','00001','11110'),
        '4':('10001','10001','10001','11111','00001','00001','00001'),
        '5':('11111','10000','11110','00001','00001','10001','01110'),
        '6':('01110','10000','10000','11110','10001','10001','01110'),
        '7':('11111','00001','00010','00100','01000','01000','01000'),
        '8':('01110','10001','10001','01110','10001','10001','01110'),
        '9':('01110','10001','10001','01111','00001','00001','01110'),
        '%':('10001','10010','00100','01000','10001','00010','00100'),
    }
    FONT_W, FONT_H = 5, 7

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.width = 0
        self.height = 0
        self.grid = []
        self.name = ""

    def generate(self):
        rng = random.Random(self.seed)
        w = rng.randint(14, 32)
        h = rng.randint(14, 28)
        self.width = w
        self.height = h
        self.grid = [[0] * w for _ in range(h)]
        self.name = rng.choice(["castle","keep","fortress","citadel","stronghold","tower","bastion","outpost"])

        rng.choice([
            self._gen_towers_and_walls,
            self._gen_stepped_castle,
            self._gen_outpost,
            self._gen_classic_castle,
        ])(rng)

        self._shift_to_bottom()
        return self

    # ── generators ───────────────────────────────────

    def _gen_towers_and_walls(self, rng):
        """Multiple towers with connecting walls between them."""
        w, h = self.width, self.height
        n_towers = rng.randint(2, 4)
        base_h = h - 3

        # Place towers along the width
        tower_positions = []
        for i in range(n_towers):
            if i == 0:
                tx = rng.randint(0, 2)
            elif i == n_towers - 1:
                tx = w - rng.randint(3, 5)
            else:
                margin = 3
                min_x = max(margin, tower_positions[-1][0] + tower_positions[-1][1] + 2)
                max_x = w - margin
                if min_x >= max_x:
                    continue
                tx = rng.randint(min_x, max_x)
            tw = rng.randint(3, 5)
            th = rng.randint(4, 8)
            tower_positions.append((tx, tw, th))

        if len(tower_positions) < 2:
            # Fallback to classic castle
            return self._gen_classic_castle(rng)

        # Draw towers
        for tx, tw, th in tower_positions:
            self._rect(base_h - th, base_h + 3, tx, tx + tw, fill=1)
            self._battlements(base_h - th, tx, tx + tw, thick=2)

        # Draw connecting walls between towers
        for i in range(len(tower_positions) - 1):
            x1 = tower_positions[i][0] + tower_positions[i][1]
            x2 = tower_positions[i + 1][0]
            if x2 > x1:
                wall_h = rng.randint(3, 5)
                self._rect(base_h - wall_h, base_h + 3, x1, x2, fill=1)
                self._battlements(base_h - wall_h, x1, x2, thick=1)

        # Gate at bottom of a wall section
        if len(tower_positions) >= 2:
            mid = (tower_positions[0][0] + tower_positions[1][0]) // 2
            gate_w = rng.randint(2, 3)
            self._rect(h - gate_w, h, mid, mid + gate_w, fill=0)

    def _gen_stepped_castle(self, rng):
        """Castle with stepped multi-height silhouette like a real castle skyline."""
        w, h = self.width, self.height
        n_levels = rng.randint(3, 6)
        base_y = h - 2

        # Divide the width into sections
        sections = []
        remaining_w = w
        for i in range(n_levels):
            if i == n_levels - 1:
                sw = remaining_w
            else:
                sw = rng.randint(3, 6)
                sw = min(sw, remaining_w - (n_levels - i - 1) * 2)
            if sw <= 1: break
            height = rng.randint(4, 10)
            sections.append((sw, height))
            remaining_w -= sw

        if len(sections) < 2:
            return self._gen_classic_castle(rng)

        # Draw each section with alternating heights
        x = 0
        for sw, height in sections:
            top = base_y - height
            self._rect(top, base_y + 2, x, x + sw, fill=1)
            self._battlements(top, x, x + sw, thick=2)

            # Some sections get extra stepped top
            if rng.random() < 0.4 and height > 5:
                step_h = rng.randint(2, 3)
                for sx in range(x, x + sw, 2):
                    self._rect(top - step_h, top, sx, min(sx + 1, x + sw), fill=1)

            # Add arrow loops
            if sw >= 4 and height >= 5:
                loop_x = x + rng.randint(1, sw - 2)
                loop_y = rng.randint(top + 2, base_y - 1)
                if rng.random() < 0.7:
                    self.grid[loop_y][loop_x] = 0
                    self.grid[loop_y + 1][loop_x] = 0

            x += sw

        # Gate somewhere
        sections_mid = len(sections) // 2
        x = sum(s[0] for s in sections[:sections_mid])
        gate_w = rng.randint(2, 3)
        self._rect(h - gate_w, h, x, x + gate_w, fill=0)

    def _gen_outpost(self, rng):
        """Asymmetric castle: large keep on one side, wall extending, tower on other."""
        w, h = self.width, self.height
        base_y = h - 3

        # Main keep (left or right)
        keep_side = rng.choice(["left", "right"])
        keep_w = rng.randint(5, 8)
        keep_h = rng.randint(7, 10)

        if keep_side == "left":
            kx = 0
            wall_x = keep_w
            wall_w = w - keep_w - rng.randint(3, 5)
        else:
            kx = w - keep_w
            wall_x = 0
            wall_w = kx - 1

        # Draw keep
        self._rect(base_y - keep_h, base_y + 2, kx, kx + keep_w, fill=1)
        self._battlements(base_y - keep_h, kx, kx + keep_w, thick=2)
        # Windows on keep
        for _ in range(rng.randint(1, 3)):
            wy = rng.randint(base_y - keep_h + 2, base_y - 1)
            wx = rng.randint(kx + 1, kx + keep_w - 2)
            self.grid[wy][wx] = 0
            self.grid[wy - 1][wx] = 0

        # Draw wall extending from keep
        if wall_w > 0:
            wall_h = rng.randint(3, 5)
            self._rect(base_y - wall_h, base_y + 2, wall_x, wall_x + wall_w, fill=1)
            self._battlements(base_y - wall_h, wall_x, wall_x + wall_w, thick=1)

        # Small tower at the end of the wall
        if wall_w > 3:
            tw = rng.randint(2, 4)
            th = rng.randint(4, 7)
            if keep_side == "left":
                tx = wall_x + wall_w - 1
            else:
                tx = wall_x
            self._rect(base_y - th, base_y + 2, tx, min(tx + tw, w), fill=1)
            self._battlements(base_y - th, tx, min(tx + tw, w), thick=2)

        # Gate in the wall
        if wall_w > 5:
            gx = wall_x + wall_w // 2
            gate_w = rng.randint(2, 3)
            self._rect(h - gate_w, h, gx, gx + gate_w, fill=0)

    def _gen_classic_castle(self, rng):
        """Classic castle: 2 towers with curtain wall, battlements."""
        w, h = self.width, self.height
        wall_h = min(h, rng.randint(8, 14))
        wall_top = h - wall_h

        self._rect(wall_top, h, 0, w, fill=1)
        self._battlements(wall_top, 0, w, thick=2)

        tw = rng.randint(3, 5)
        th = rng.randint(5, 9)
        self._rect(wall_top - th, wall_top + 2, 0, tw, fill=1)
        self._battlements(wall_top - th, 0, tw, thick=2)

        tw2 = rng.randint(3, 5)
        self._rect(wall_top - th, wall_top + 2, w - tw2, w, fill=1)
        self._battlements(wall_top - th, w - tw2, w, thick=2)

        gate_w = rng.randint(2, 3)
        gate_x = (w - gate_w) // 2
        self._rect(h - gate_w, h, gate_x, gate_x + gate_w, fill=0)

        # Windows
        win_count = rng.randint(1, 3)
        for _ in range(win_count):
            wx = rng.randint(tw + 2, w - tw2 - 2)
            wy = rng.randint(wall_top + 2, h - gate_w - 1)
            self.grid[wy][wx] = 0
            self.grid[wy - 1][wx] = 0

    # ── helpers ───────────────────────────────────────

    def _rect(self, y0, y1, x0, x1, fill=1):
        for y in range(max(0, y0), min(self.height, y1)):
            for x in range(max(0, x0), min(self.width, x1)):
                self.grid[y][x] = fill

    def _battlements(self, row, x0, x1, thick=1):
        x0 = max(0, x0)
        x1 = min(self.width, x1)
        for x in range(x0, x1):
            if (x - x0) % (thick * 2) < thick or (x - x0) == 0 or (x - x0) == x1 - x0 - 1:
                for d in range(thick):
                    yy = row - d
                    if 0 <= yy < self.height:
                        self.grid[yy][x] = 1

    def _shift_to_bottom(self):
        h = self.height
        bottom_row = max((y for y in range(h) if any(self.grid[y][x] for x in range(self.width))), default=0)
        shift = (h - 1) - bottom_row
        if shift > 0:
            for y in range(h - 1, shift - 1, -1):
                for x in range(self.width):
                    self.grid[y][x] = self.grid[y - shift][x]
            for y in range(shift):
                for x in range(self.width):
                    self.grid[y][x] = 0

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

    def render_text(self, text: str) -> list[str]:
        rows = [""] * self.FONT_H
        for ch in text:
            glyph = self.FONT.get(ch)
            if not glyph: continue
            for r in range(self.FONT_H):
                rows[r] += glyph[r]
                if ch != text[-1]:
                    rows[r] += "0"
        return rows
