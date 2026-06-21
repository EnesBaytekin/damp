"""
MenuController — manages the menu scene with DAMP graffiti + drip effect.
"""

import os
import json
import importlib
import pygame
from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager
from pygaminal.app import App
from scripts.Grid import Grid, WIDTH, HEIGHT, EMPTY

BG_COLOR = (0x1a, 0x1a, 0x2e)
SAND_COLORS = [(194, 178, 128), (170, 150, 100), (140, 120, 80), (100, 80, 50)]


class MenuController:
    def __init__(self):
        self.grid = Grid()
        self.surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        self.menu_options = ["PLAY", "QUIT"]
        self.menu_index = 0
        self.drip_timer = 0
        self.transition_alpha = 0
        self.transition_dir = 0
        self.game_started = False   # signal for main.py

        self._load_particle_types()
        self._write_graffiti()
        self.surf.fill((0, 0, 0, 0))

    def _load_particle_types(self):
        pdir = "objects/particles"
        if not os.path.isdir(pdir):
            return
        for fname in sorted(os.listdir(pdir)):
            if not fname.endswith(".obj"):
                continue
            path = os.path.join(pdir, fname)
            try:
                with open(path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            type_id = data.get("type_id")
            if not type_id:
                continue
            update_fn = None
            script_ref = data.get("script")
            if script_ref:
                mod = importlib.import_module(script_ref.replace(".py", "").replace("/", "."))
                update_fn = getattr(mod, "update", None)
            self.grid.register(type_id, {
                "name": data.get("name", "?"),
                "color": tuple(data.get("color", (255, 255, 255))),
                "density": data.get("density", 1),
                "update": update_fn,
            })

    def _write_graffiti(self):
        template = pygame.image.load("assets/menu.png")
        w, h = template.get_size()
        for y in range(h):
            for x in range(w):
                _, _, _, a = template.get_at((x, y))
                if a > 128:
                    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                        self.grid.spawn(x, y, 1)
                        self.grid.wetness[y][x] = 3.0
                        self.grid.asleep[y][x] = 1

    def _drip(self):
        self.drip_timer -= 1
        if self.drip_timer > 0:
            return
        self.drip_timer = self.grid.rng.randint(15, 40)
        is_water = self.grid.rng.random() < 0.35
        ptype = 2 if is_water else 1
        r = self.grid.rng.randint(3, 6)
        cx = self.grid.rng.randint(r, WIDTH - 1 - r)
        fill_ratio = self.grid.rng.uniform(0.4, 0.8)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    if self.grid.rng.random() > fill_ratio:
                        continue
                    x, y = cx + dx, dy
                    if 0 <= x < WIDTH and y < HEIGHT:
                        if self.grid.grid[y][x] == 0:
                            self.grid.spawn(x, y, ptype)

    def update(self, obj):
        im = InputManager()
        self._handle_input(im)

        if self.transition_dir:
            self.transition_alpha += self.transition_dir * 8
            if self.transition_alpha >= 255:
                self.transition_alpha = 255
                self.transition_dir = -1
            elif self.transition_dir == -1 and self.transition_alpha <= 0:
                self.transition_alpha = 0
                self.transition_dir = 0
                self.game_started = True

        if not self.transition_dir:
            self._drip()

        self.grid.step()
        self._render()

    def _handle_input(self, im):
        if self.transition_dir:
            return
        if pygame.K_UP in im.just_pressed_keys or pygame.K_w in im.just_pressed_keys:
            self.menu_index = (self.menu_index - 1) % len(self.menu_options)
        elif pygame.K_DOWN in im.just_pressed_keys or pygame.K_s in im.just_pressed_keys:
            self.menu_index = (self.menu_index + 1) % len(self.menu_options)
        elif pygame.K_RETURN in im.just_pressed_keys or pygame.K_SPACE in im.just_pressed_keys:
            self._select()
        elif im.is_mouse_just_pressed(1):
            mx, my = im.get_mouse_position()
            pad, gap = 2, 2
            btn_w = max(len(o) for o in self.menu_options) * 6 + pad * 2 + 2
            btn_h = 9
            n = len(self.menu_options)
            base_y = HEIGHT - 2 - n * btn_h - (n - 1) * gap
            for i, opt in enumerate(self.menu_options):
                bx = WIDTH - btn_w - 2
                by = base_y + i * (btn_h + gap)
                if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
                    self.menu_index = i
                    self._select()
                    return

    def _select(self):
        if self.menu_options[self.menu_index] == "PLAY":
            self.transition_dir = 1
        elif self.menu_options[self.menu_index] == "QUIT":
            App().stop()

    def _render(self):
        for (x, y) in self.grid.dirty:
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                continue
            tid = self.grid.grid[y][x]
            if tid == EMPTY:
                self.surf.set_at((x, y), (0, 0, 0, 0))
            elif tid == 1:
                raw = self.grid.wetness[y][x]
                w = 0 if raw <= 0.0 else min(int(raw + 0.99), 3)
                self.surf.set_at((x, y), SAND_COLORS[w])
            else:
                info = self.grid.particle_types.get(tid)
                color = info["color"] if info else (255, 255, 255)
                if tid == 2:
                    color = color[:3] + (160,)
                self.surf.set_at((x, y), color)
        self.grid.dirty.clear()

    def draw(self, obj):
        screen = Screen()
        screen.surface.blit(self.surf, (0, 0))

        self._draw_menu(screen)

        if self.transition_alpha > 0:
            fade = pygame.Surface((WIDTH, HEIGHT))
            fade.set_alpha(self.transition_alpha)
            fade.fill((255, 255, 255))
            screen.surface.blit(fade, (0, 0))

    def _draw_menu(self, screen):
        font_chars = {
            'P': ('11110','10001','10001','11110','10000','10000','10000'),
            'L': ('10000','10000','10000','10000','10000','10000','11111'),
            'A': ('01110','10001','10001','11111','10001','10001','10001'),
            'Y': ('10001','10001','01010','00100','00100','00100','00100'),
            'Q': ('01110','10001','10001','10001','10101','10010','01101'),
            'U': ('10001','10001','10001','10001','10001','10001','01110'),
            'I': ('11111','00100','00100','00100','00100','00100','11111'),
            'T': ('11111','00100','00100','00100','00100','00100','00100'),
        }
        mfw, mfh = 5, 7
        mgap = 1
        pad, gap = 2, 2
        btn_w = max(len(o) for o in self.menu_options) * (mfw + mgap) - mgap + pad * 2 + 2
        btn_h = mfh + 2
        n = len(self.menu_options)
        base_y = HEIGHT - 2 - n * btn_h - (n - 1) * gap

        for i, opt in enumerate(self.menu_options):
            bx = WIDTH - btn_w - 2
            by = base_y + i * (btn_h + gap)

            tmp = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
            rgb = (15, 12, 30)
            r = 3
            pygame.draw.rect(tmp, rgb, (r, 0, btn_w - r*2, btn_h))
            pygame.draw.rect(tmp, rgb, (0, r, btn_w, btn_h - r*2))
            for px, py in ((r, r), (btn_w - r - 1, r), (r, btn_h - r - 1), (btn_w - r - 1, btn_h - r - 1)):
                pygame.draw.circle(tmp, rgb, (px, py), r)
            tmp.set_alpha(210)
            screen.surface.blit(tmp, (bx, by))

            color = (255, 240, 200) if i == self.menu_index else (150, 140, 110)
            ox = bx + pad + 1
            oy = by + (btn_h - mfh) // 2
            for ci, ch in enumerate(opt):
                glyph = font_chars.get(ch)
                if not glyph:
                    continue
                for row in range(mfh):
                    for col in range(mfw):
                        if glyph[row][col] == '1':
                            px = ox + ci * (mfw + mgap) + col
                            py = oy + row
                            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                screen.surface.set_at((px, py), color)
