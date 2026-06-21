"""
WorldController — the game scene: horizontally-infinite chunked world.
"""

import importlib
import json
import os
import pygame

from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager
from pygaminal.app import App

from scripts.Chunk import CHUNK_SIZE, CHUNK_HEIGHT, EMPTY
from scripts.ChunkManager import ChunkManager, _height_at
from scripts.Camera import Camera
from scripts.Player import Player

SAND_COLORS = [(194, 178, 128), (170, 150, 100), (140, 120, 80), (100, 80, 50)]
WATER_COLOR = (64, 164, 223, 160)
INTERACT_RADIUS = 45


class WorldController:
    def __init__(self, seed: int = None):
        if seed is None:
            import random as _rnd
            seed = _rnd.randint(0, 999999)
        self.seed = seed
        self.cm = ChunkManager(seed=seed)

        self.sim_surf = pygame.Surface((160, 90), pygame.SRCALPHA)
        self.water_surf = pygame.Surface((160, 90), pygame.SRCALPHA)
        self._load_particle_types()

        self.player = Player(self.cm)
        self.camera = Camera()

        # Brush state
        self.current_type = 1
        self.brush_radius = 3
        self.spawn_rate = 8
        self._cursor_pos = (0, 0)

        # Line-drag
        self._line_start = None
        self._line_end = None
        self._line_button = 0

        # Tool icons
        self._tool_icons = {}
        for tid, color in {1: (194, 178, 128), 2: (64, 164, 223), 3: (100, 80, 50), 4: (90, 90, 90)}.items():
            s = pygame.Surface((3, 3)); s.fill(color); self._tool_icons[tid] = s

        self._cursor_surf = pygame.Surface((160, 90), pygame.SRCALPHA)
        self._show_debug = False
        self.quit_to_menu = False

        # Initialise
        spawn_x, spawn_y = self._find_spawn()
        self.player.x = spawn_x
        self.player.y = spawn_y
        self._generated_around = False

    # ── particle loading ─────────────────────────────────

    def _load_particle_types(self):
        pdir = "objects/particles"
        if not os.path.isdir(pdir):
            return
        for fname in sorted(os.listdir(pdir)):
            if not fname.endswith(".obj"):
                continue
            try:
                with open(os.path.join(pdir, fname)) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            type_id = data.get("type_id")
            if not type_id:
                continue
            update_fn = None
            scr = data.get("script")
            if scr:
                mod = importlib.import_module(scr.replace(".py", "").replace("/", "."))
                update_fn = getattr(mod, "update", None)
            self.cm.register(type_id, {
                "name": data.get("name", "?"),
                "color": tuple(data.get("color", (255, 255, 255))),
                "density": data.get("density", 1),
                "update": update_fn,
            })

    def _find_spawn(self) -> tuple[float, float]:
        """Find spawn on the sandiest column (not water)."""
        for test_cx in (0, -1, 1):
            self.cm.generate_terrain(test_cx)
            chunk = self.cm.chunks.get(test_cx)
            if not chunk:
                continue
            best_col, best_y = 0, 0
            for lx in range(CHUNK_SIZE):
                for ly in range(CHUNK_HEIGHT - 1, -1, -1):
                    if chunk.grid[ly][lx] == 1:
                        if ly > best_y:
                            best_y, best_col = ly, lx
                        break
            if best_y > 10:
                wx = test_cx * CHUNK_SIZE + best_col
                return float(wx), float(best_y - 5)
        return 80.0, 40.0

    # ── helpers ───────────────────────────────────────────

    def _get_world_pos(self):
        mx, my = InputManager().get_mouse_position()
        return int(mx + self.camera.x), int(my)

    def _dist_to_player(self, wx: int, wy: int) -> float:
        return ((wx - self.player.x) ** 2 + (wy - self.player.y) ** 2) ** 0.5

    def _paint(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS:
            return
        t = self.current_type
        iw = 3.0 if t == 3 else 0.0
        if t == 3:
            t = 1
        for _ in range(self.spawn_rate):
            dx = self.cm.rng.randint(-r, r)
            dy = self.cm.rng.randint(-r, r)
            if dx * dx + dy * dy <= r * r:
                tx, ty = wx + dx, wy + dy
                if iw:
                    self.cm.set_cell_with_wetness(tx, ty, t, iw)
                else:
                    self.cm.set_cell(tx, ty, t)

    def _erase(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS:
            return
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    ex, ey = wx + dx, wy + dy
                    cx, lx = ex // CHUNK_SIZE, ex % CHUNK_SIZE
                    chunk = self.cm.get_chunk(cx, create=False)
                    if chunk and 0 <= ey < CHUNK_HEIGHT and chunk.grid[ey][lx] != EMPTY:
                        chunk.grid[ey][lx] = EMPTY
                        chunk.dirty.append((lx, ey))
                        chunk.filled_count -= 1

    def _water_erase(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS:
            return
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    ex, ey = wx + dx, wy + dy
                    cx, lx = ex // CHUNK_SIZE, ex % CHUNK_SIZE
                    chunk = self.cm.get_chunk(cx, create=False)
                    if chunk and 0 <= ey < CHUNK_HEIGHT and chunk.grid[ey][lx] == 2:
                        chunk.grid[ey][lx] = EMPTY
                        chunk.water_charge[ey][lx] = 0
                        chunk.dirty.append((lx, ey))
                        chunk.filled_count -= 1

    def _line_cells(self, x0, y0, x1, y1):
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
        err = dx + dy; x, y = x0, y0
        while True:
            yield x, y
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x += sx
            if e2 <= dx:
                err += dx; y += sy

    def _apply_brush_at(self, wx, wy):
        r = self.brush_radius
        if self._line_button == 3:
            self._erase(wx, wy, r)
        elif self.current_type == 4:
            self._water_erase(wx, wy, r)
        else:
            self._paint(wx, wy, r)

    # ── input ──────────────────────────────────────────────

    def _handle_input(self):
        im = InputManager()

        if pygame.K_1 in im.just_pressed_keys: self.current_type = 1
        elif pygame.K_2 in im.just_pressed_keys: self.current_type = 2
        elif pygame.K_3 in im.just_pressed_keys: self.current_type = 3
        elif pygame.K_4 in im.just_pressed_keys: self.current_type = 4
        elif pygame.K_F3 in im.just_pressed_keys: self._show_debug = not self._show_debug
        elif pygame.K_ESCAPE in im.just_pressed_keys: self.quit_to_menu = True; return

        sl = (pygame.K_LEFTBRACKET in im.just_pressed_keys or pygame.K_MINUS in im.just_pressed_keys or
              pygame.K_KP_MINUS in im.just_pressed_keys or im.wheel_y < 0)
        gr = (pygame.K_RIGHTBRACKET in im.just_pressed_keys or pygame.K_EQUALS in im.just_pressed_keys or
              pygame.K_KP_PLUS in im.just_pressed_keys or im.wheel_y > 0)
        if sl: self.brush_radius = max(0, self.brush_radius - 1)
        elif gr: self.brush_radius = min(10, self.brush_radius + 1)

        wx, wy = self._get_world_pos()
        self._cursor_pos = (wx, wy)
        r = self.brush_radius

        ctrl = pygame.K_LCTRL in im.pressed_keys or pygame.K_RCTRL in im.pressed_keys

        if ctrl:
            if im.is_mouse_just_pressed(1) or im.is_mouse_just_pressed(3):
                self._line_start = (wx, wy); self._line_end = (wx, wy)
                self._line_button = 3 if im.is_mouse_just_pressed(3) else 1
            if self._line_start is not None:
                self._line_end = (wx, wy)
            if (self._line_button == 1 and im.is_mouse_released(1)) or \
               (self._line_button == 3 and im.is_mouse_released(3)):
                for lx, ly in self._line_cells(*self._line_start, *self._line_end):
                    self._apply_brush_at(lx, ly)
                self._line_start = None; self._line_end = None; self._line_button = 0
        else:
            self._line_start = None; self._line_end = None; self._line_button = 0
            if im.is_mouse_pressed(1) and self._dist_to_player(wx, wy) <= INTERACT_RADIUS:
                (self._water_erase if self.current_type == 4 else self._paint)(wx, wy, r)
            if im.is_mouse_pressed(3) and self._dist_to_player(wx, wy) <= INTERACT_RADIUS:
                self._erase(wx, wy, r)

    # ── update / render ───────────────────────────────────

    def update(self, obj):
        self._handle_input()
        px, py = int(self.player.x), int(self.player.y)
        if not self._generated_around:
            self.cm.generate_around(px, 4)
            self._generated_around = True
        else:
            self.cm.generate_around(px, 3)
        self.cm.step_active(px, 2)
        self.player.update()
        self.camera.follow(self.player.x, self.player.y, 0.12)
        self._render()

    def _render(self):
        self.sim_surf.fill((0, 0, 0, 0))
        self.water_surf.fill((0, 0, 0, 0))

        visible = self.camera.get_visible_chunks()
        for cx in visible:
            chunk = self.cm.get_chunk(cx, create=False)
            if chunk is None or chunk.filled_count == 0:
                continue
            ox = cx * CHUNK_SIZE - int(self.camera.x)
            for ly in range(CHUNK_HEIGHT):
                for lx in range(CHUNK_SIZE):
                    tid = chunk.grid[ly][lx]
                    if tid == EMPTY:
                        continue
                    sx = ox + lx
                    if not (0 <= sx < 160):
                        continue
                    if tid == 1:
                        w = min(int(chunk.wetness[ly][lx] + 0.99), 3)
                        self.sim_surf.set_at((sx, ly), SAND_COLORS[w])
                    elif tid == 2:
                        self.water_surf.set_at((sx, ly), WATER_COLOR)

    def draw(self, obj):
        screen = Screen()
        screen.surface.blit(self.sim_surf, (0, 0))
        self.player.draw(self.camera)
        screen.surface.blit(self.water_surf, (0, 0))
        self._draw_toolbar()
        self._draw_cursor()
        if self._show_debug:
            self._draw_debug()

    # ── UI ──────────────────────────────────────────────────

    def _draw_toolbar(self):
        screen = Screen()
        for tid in (1, 2, 3, 4):
            tx = 2 + (tid - 1) * 3
            screen.surface.blit(self._tool_icons[tid], (tx, 2))
        sx = 2 + (self.current_type - 1) * 3
        pygame.draw.rect(screen.surface, (200, 200, 200), (sx - 1, 1, 5, 5), 1)

    def _draw_cursor(self):
        self._cursor_surf.fill((0, 0, 0, 0))
        wx, wy = self._cursor_pos
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS:
            Screen().surface.blit(self._cursor_surf, (0, 0))
            return
        r = self.brush_radius
        sx, sy = wx - int(self.camera.x), wy
        color = (255, 240, 200)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = sx + dx, sy + dy
                    if 0 <= px < 160 and 0 <= py < 90:
                        self._cursor_surf.set_at((px, py), color)
        if self._line_start and self._line_end:
            for lx, ly in self._line_cells(*self._line_start, *self._line_end):
                slx, sly = lx - int(self.camera.x), ly
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r:
                            px, py = slx + dx, sly + dy
                            if 0 <= px < 160 and 0 <= py < 90:
                                self._cursor_surf.set_at((px, py), color)
        self._cursor_surf.set_alpha(80)
        Screen().surface.blit(self._cursor_surf, (0, 0))

    def _draw_debug(self):
        font = pygame.font.SysFont("monospace", 10)
        total = sum(c.filled_count for c in self.cm.chunks.values())
        lines = [
            f"frame {self.cm.frame}", f"particles {total}",
            f"player ({int(self.player.x)},{int(self.player.y)})",
            f"chunks {len(self.cm.chunks)}",
            f"brush: {['sand','water','wet','eraser'][self.current_type-1]} r={self.brush_radius}",
            f"fps: {App().clock.get_fps():.0f}" if App().clock else "fps: ?",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (255, 255, 200))
            Screen().surface.blit(surf, (2, 2 + i * 12))
