"""
WorldController — the game scene with 2x zoom, 80×45 viewport.
"""

import importlib
import json
import os
import random
import pygame

from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager
from pygaminal.app import App

from scripts.Chunk import CHUNK_SIZE, CHUNK_HEIGHT, EMPTY
from scripts.ChunkManager import ChunkManager
from scripts.Camera import Camera
from scripts.Template import Template
from scripts.Player import Player

SAND_COLORS = [(194, 178, 128), (170, 150, 100), (140, 120, 80), (100, 80, 50)]
WATER_COLOR = (64, 164, 223, 160)
INTERACT_RADIUS = 20


class WorldController:
    def __init__(self, seed: int = None):
        if seed is None:
            import random as _rnd
            seed = _rnd.randint(0, 999999)
        self.seed = seed
        self.cm = ChunkManager(seed=seed)

        self.view_surf = pygame.Surface((80, 45), pygame.SRCALPHA)
        self.water_surf = pygame.Surface((80, 45), pygame.SRCALPHA)
        self._load_particle_types()

        self.player = Player(self.cm)
        self.camera = Camera()

        self.current_type = 1
        self.brush_radius = 3
        self.spawn_rate = 8
        self._cursor_pos = (0, 0)

        self._line_start = None
        self._line_end = None
        self._line_button = 0

        self._tool_icons = {}
        for tid, color in {1: (194, 178, 128), 2: (64, 164, 223), 3: (100, 80, 50), 4: (90, 90, 90), 5: (180, 160, 100)}.items():
            s = pygame.Surface((3, 3)); s.fill(color); self._tool_icons[tid] = s

        self._cursor_surf = pygame.Surface((160, 90), pygame.SRCALPHA)
        self._radius_surf = pygame.Surface((160, 90), pygame.SRCALPHA)
        self._quest_surf = pygame.Surface((160, 90), pygame.SRCALPHA)

        # Quest state
        self.quest_active = False
        self.quest_placed = False
        self.quest_template = None
        self.quest_wx = 0
        self.quest_wy = 0
        self.quest_placing = False
        self.quest_rng = random.Random()
        self.quest_score = 0
        self.quest_score_timer = 0
        self.quest_score_text = ""
        self.quest_scored = False
        # Quest panel state
        self._show_debug = False
        self.quit_to_menu = False
        self.quest_panel_open = False
        self.quest_panel_mode = "menu"  # "menu" | "score"
        self.quest_panel_score = ""
        self.quest_candidates = []
        self.quest_candidate_idx = 0
        self.quest_hover_btn = ""

        spawn_x, spawn_y = self._find_spawn()
        self.player.x = spawn_x
        self.player.y = spawn_y
        self._generated_around = False

    def _load_particle_types(self):
        pdir = "objects/particles"
        if not os.path.isdir(pdir): return
        for fname in sorted(os.listdir(pdir)):
            if not fname.endswith(".obj"): continue
            try:
                with open(os.path.join(pdir, fname)) as f:
                    data = json.load(f)
            except: continue
            type_id = data.get("type_id")
            if not type_id: continue
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
        """Find spawn at sand surface — shortest sand column, on the surface."""
        for test_cx in (0, -1, 1):
            self.cm.generate_terrain(test_cx)
            chunk = self.cm.chunks.get(test_cx)
            if not chunk: continue
            for lx in range(CHUNK_SIZE):
                for ly in range(10, CHUNK_HEIGHT):
                    if chunk.grid[ly][lx] == 1:
                        # ly is the surface row (first sand from top)
                        wx = test_cx * CHUNK_SIZE + lx
                        return float(wx), float(ly - 8)
        return 80.0, 40.0

    def _get_world_pos(self):
        """Mouse position in world coordinates (rounded to int)."""
        mx, my = InputManager().get_mouse_position()
        wx, wy = self.camera.screen_to_world(mx, my)
        return int(wx), int(wy)

    def _dist_to_player(self, wx: int, wy: int) -> float:
        cx, cy = self.player.x + 4, self.player.y + 5
        return ((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5

    def _paint(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS: return
        t = self.current_type
        iw = 3.0 if t == 3 else 0.0
        if t == 3: t = 1
        for _ in range(self.spawn_rate):
            dx = self.cm.rng.randint(-r, r)
            dy = self.cm.rng.randint(-r, r)
            if dx * dx + dy * dy <= r * r:
                if iw: self.cm.set_cell_with_wetness(wx+dx, wy+dy, t, iw)
                else: self.cm.set_cell(wx+dx, wy+dy, t)

    def _erase(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS: return
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if dx*dx+dy*dy <= r*r:
                    ex, ey = wx+dx, wy+dy
                    cx, lx = ex // CHUNK_SIZE, ex % CHUNK_SIZE
                    chunk = self.cm.get_chunk(cx, create=False)
                    if chunk and 0 <= ey < CHUNK_HEIGHT and chunk.grid[ey][lx] != EMPTY:
                        chunk.grid[ey][lx] = EMPTY
                        chunk.dirty.append((lx, ey))
                        chunk.filled_count -= 1
                        if ey > 0: chunk.disturbed[ey-1][lx] = chunk.frame + 1

    def _water_erase(self, wx: int, wy: int, r: int):
        if self._dist_to_player(wx, wy) > INTERACT_RADIUS: return
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if dx*dx+dy*dy <= r*r:
                    ex, ey = wx+dx, wy+dy
                    cx, lx = ex // CHUNK_SIZE, ex % CHUNK_SIZE
                    chunk = self.cm.get_chunk(cx, create=False)
                    if chunk and 0 <= ey < CHUNK_HEIGHT and chunk.grid[ey][lx] == 2:
                        chunk.grid[ey][lx] = EMPTY
                        chunk.water_charge[ey][lx] = 0
                        chunk.dirty.append((lx, ey))
                        chunk.filled_count -= 1
                        if ey > 0: chunk.disturbed[ey-1][lx] = chunk.frame + 1

    def _line_cells(self, x0, y0, x1, y1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
        err = dx + dy; x, y = x0, y0
        while True:
            yield x, y
            if x == x1 and y == y1: break
            e2 = 2 * err
            if e2 >= dy: err += dy; x += sx
            if e2 <= dx: err += dx; y += sy

    def _apply_brush_at(self, wx: int, wy: int):
        r = self.brush_radius
        if self._line_button == 3: self._erase(wx, wy, r)
        elif self.current_type == 4: self._water_erase(wx, wy, r)
        else: self._paint(wx, wy, r)

    def _handle_input(self):
        im = InputManager()
        if hasattr(self, "_quest_btn_rect") and im.is_mouse_just_pressed(1):
            bx, by, bw, bh = self._quest_btn_rect
            mx, my = im.get_mouse_position()
            if bx <= mx <= bx+bw and by <= my <= by+bh:
                if self.quest_placed and not self.quest_scored:
                    self._quest_placed_done()
                elif not self.quest_scored:
                    self.quest_panel_open = not self.quest_panel_open
                    if self.quest_panel_open and not self.quest_candidates:
                        self._quest_new_candidates()
        if self.quest_panel_open and im.is_mouse_just_pressed(1):
            mx, my = im.get_mouse_position()
            self._handle_panel_click(mx, my)
            return
        if self.quest_panel_open:
            return
        elif pygame.K_1 in im.just_pressed_keys: self.current_type = 1
        elif pygame.K_2 in im.just_pressed_keys: self.current_type = 2
        elif pygame.K_3 in im.just_pressed_keys: self.current_type = 3
        elif pygame.K_4 in im.just_pressed_keys: self.current_type = 4
        elif pygame.K_5 in im.just_pressed_keys: self._quest_toggle()
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
            if self._line_start:
                self._line_end = (wx, wy)
            if (self._line_button == 1 and im.is_mouse_released(1)) or \
               (self._line_button == 3 and im.is_mouse_released(3)):
                for lx, ly in self._line_cells(*self._line_start, *self._line_end):
                    self._apply_brush_at(lx, ly)
                self._line_start = self._line_end = None; self._line_button = 0
        else:
            self._line_start = self._line_end = None; self._line_button = 0
            if self.current_type == 5 and im.is_mouse_just_pressed(1) and self._dist_to_player(wx, wy) <= INTERACT_RADIUS:
                self.quest_panel_open = True
                self.quest_panel_mode = "menu"
            elif self.quest_placing and im.is_mouse_just_pressed(1):
                self._place_quest(wx, wy)
            elif im.is_mouse_pressed(1) and self._dist_to_player(wx, wy) <= INTERACT_RADIUS:
                (self._water_erase if self.current_type == 4 else self._paint)(wx, wy, r)
            if im.is_mouse_pressed(3) and self._dist_to_player(wx, wy) <= INTERACT_RADIUS:
                self._erase(wx, wy, r)

    def update(self, obj):
        self._handle_input()
        if self.quest_score_timer > 0:
            self.quest_score_timer -= 1
            if self.quest_score_timer == 0:
                self.quest_template = None
                self.quest_score_text = ""
                self.quest_scored = False
        px = int(self.player.x)
        if not self._generated_around:
            self.cm.generate_around(px, 2); self._generated_around = True
        else:
            self.cm.generate_around(px, 2)
        # Step both visible chunks
        self.cm.frame += 1
        stepped = set()
        for cx in self.camera.get_visible_chunks():
            ch = self.cm.get_chunk(cx, create=False)
            if ch and ch.filled_count > 0:
                ch.frame = self.cm.frame
                ch.step()
                stepped.add(cx)
        self.cm._apply_cross_moves()
        self.player.update()
        self.camera.follow(self.player.x, self.player.y, 0.12)
        self._render()

    def _render(self):
        self.view_surf.fill((140, 170, 200, 255))
        self.water_surf.fill((0, 0, 0, 0))

        cx0, cx1 = self.camera.get_visible_chunks()
        for cx in (cx0, cx1):
            chunk = self.cm.get_chunk(cx, create=False)
            if chunk is None or chunk.filled_count == 0:
                continue
            base_wx = cx * CHUNK_SIZE
            vp_x0 = int(self.camera.x)
            vp_y0 = int(self.camera.y)
            vp_x1 = vp_x0 + 80
            vp_y1 = vp_y0 + 45

            lx0 = max(0, vp_x0 - base_wx)
            lx1 = min(CHUNK_SIZE, vp_x1 - base_wx)
            ly0 = max(0, vp_y0)
            ly1 = min(CHUNK_HEIGHT, vp_y1)

            for ly in range(ly0, ly1):
                row = chunk.grid[ly]
                for lx in range(lx0, lx1):
                    tid = row[lx]
                    if tid == EMPTY:
                        continue
                    vx = base_wx + lx - vp_x0
                    vy = ly - vp_y0
                    if 0 <= vx < 80 and 0 <= vy < 45:
                        if tid == 1:

                                w = min(int(chunk.wetness[ly][lx] + 0.99), 3)
                                self.view_surf.set_at((vx, vy), SAND_COLORS[w])
                        elif tid == 2:
                            self.water_surf.set_at((vx, vy), WATER_COLOR)

        # ── bedrock (row 90+) — purely cosmetic grey bar ──
        vp_bottom = int(self.camera.y) + 45
        if vp_bottom > CHUNK_HEIGHT:
            bed_start = max(0, CHUNK_HEIGHT - int(self.camera.y))
            for vy in range(bed_start, 45):
                for vx in range(80):
                    self.view_surf.set_at((vx, vy), (40, 40, 45))

    def draw(self, obj):
        screen = Screen()
        scaled_view = pygame.transform.scale(self.view_surf, (160, 90))
        scaled_water = pygame.transform.scale(self.water_surf, (160, 90))
        screen.surface.blit(scaled_view, (0, 0))
        self.player.draw(self.camera)
        self._draw_radius()
        self._draw_quest()
        screen.surface.blit(scaled_water, (0, 0))
        self._draw_toolbar()
        self._draw_quest_btn()
        self._draw_cursor()
        if self.quest_panel_open:
            self._draw_panel()
        if self._show_debug:
            self._draw_debug()

    def _draw_radius(self):
        px, py = int(self.player.x) + 4, int(self.player.y) + 5
        sx = int((px - self.camera.x) * 2)
        sy = int((py - self.camera.y) * 2)
        self._radius_surf.fill((0, 0, 0, 0))
        if 0 <= sx < 160 and 0 <= sy < 90:
            pygame.draw.circle(self._radius_surf, (255, 255, 255), (sx, sy), INTERACT_RADIUS * 2, 1)
        self._radius_surf.set_alpha(180)
        Screen().surface.blit(self._radius_surf, (0, 0))

    def _draw_toolbar(self):
        screen = Screen()
        for tid in (1, 2, 3, 4, 5):
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
        sx = int((wx - self.camera.x) * 2)
        sy = int((wy - self.camera.y) * 2)
        color = (255, 240, 200)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    base_px, base_py = sx + dx * 2, sy + dy * 2
                    for by in range(2):
                        for bx in range(2):
                            cx, cy = base_px + bx, base_py + by
                            if 0 <= cx < 160 and 0 <= cy < 90:
                                self._cursor_surf.set_at((cx, cy), color)
        if self._line_start and self._line_end:
            lsx, lsy = self._line_start
            lex, ley = self._line_end
            for lx, ly in self._line_cells(lsx, lsy, lex, ley):
                slx = int((lx - self.camera.x) * 2)
                sly = int((ly - self.camera.y) * 2)
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r:
                            base_px, base_py = slx + dx * 2, sly + dy * 2
                            for by in range(2):
                                for bx in range(2):
                                    cx, cy = base_px + bx, base_py + by
                                    if 0 <= cx < 160 and 0 <= cy < 90:
                                        self._cursor_surf.set_at((cx, cy), color)
        self._cursor_surf.set_alpha(80)
        Screen().surface.blit(self._cursor_surf, (0, 0))


    def _quest_new_candidates(self):
        import time
        from scripts.Template import Template
        self.quest_candidates = []
        for i in range(6):
            self.quest_candidates.append(Template(seed=int(time.time())+(i*1000)).generate())
        self.quest_candidate_idx = 0

    def _quest_placed_done(self):
        if self.quest_placed and not self.quest_scored:
            w, h = self.quest_template.get_rect()
            c, t, p = self.quest_template.score(
                lambda x, y: self.cm.get_cell(x, y),
                self.quest_wx, self.quest_wy
            )
            self.quest_score = p
            self.quest_panel_score = f'{p}%'
            self.quest_panel_mode = "score"
            self.quest_panel_open = True
            self.quest_scored = True
            self.quest_placed = False
            self.quest_active = False

    def _render_preview(self, t, surf, ox, oy, scale=1):
        w, h = t.width, t.height
        for ty in range(h):
            for tx in range(w):
                if t.grid[ty][tx] == 1:
                    for by in range(scale):
                        for bx in range(scale):
                            px = ox + tx * scale + bx
                            py = oy + ty * scale + by
                            if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                                surf.set_at((px, py), (180, 220, 255, 200))

    def _render_text(self, text, surf, x, y, color=(255, 240, 200)):
        from scripts.Template import Template
        rows = Template.render_text(text)
        for row in range(Template.FONT_H):
            for col in range(len(rows[row])):
                if rows[row][col] == '1':
                    px, py = x + col, y + row
                    if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                        surf.set_at((px, py), color)

    def _panel_btn(self, surf, x, y, w, h, text, hover=False):
        import pygame
        bg = (80, 72, 58) if not hover else (110, 100, 80)
        bd = (120, 110, 90) if not hover else (160, 150, 130)
        pygame.draw.rect(surf, bg, (x, y, w, h))
        pygame.draw.rect(surf, bd, (x, y, w, h), 1)
        tw = len(text) * 6
        self._render_text(text, surf, x + (w - tw) // 2, y + (h - 7) // 2, (255, 240, 200))

    def _draw_panel_mode_select(self, screen):
        pw, ph = 130, 62
        px0 = (160 - pw) // 2
        py0 = (90 - ph) // 2
        import pygame
        bg = pygame.Surface((pw, ph))
        bg.fill((22, 20, 35))
        screen.surface.blit(bg, (px0, py0))
        pygame.draw.rect(screen.surface, (100, 90, 80), (px0, py0, pw, ph), 1)
        inner = pygame.Surface((pw-4, ph-4))
        inner.fill((28, 25, 42))
        screen.surface.blit(inner, (px0+2, py0+2))
        from pygaminal.input_manager import InputManager
        im = InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ""
        if self.quest_candidates:
            t = self.quest_candidates[self.quest_candidate_idx]
            pv = pygame.Surface((40, 30))
            sc = max(1, min(3, 38 // max(1, t.width), 28 // max(1, t.height)))
            self._render_preview(t, pv, 1, 1, sc)
            screen.surface.blit(pv, (px0+6, py0+8))
            self._render_text(t.name.upper(), screen.surface, px0+50, py0+8)
            self._render_text(str(t.width)+'x'+str(t.height), screen.surface, px0+50, py0+16, (160, 180, 200))
            nbw, nbh = 24, 10
            nbx, nby = px0+50, py0+28
            h_prev = nbx <= mx <= nbx+nbw and nby <= my <= nby+nbh
            self._panel_btn(screen.surface, nbx, nby, nbw, nbh, '<--', h_prev)
            if h_prev: self.quest_hover_btn = 'prev'
            h_next = nbx+nbw+4 <= mx <= nbx+nbw*2+4 and nby <= my <= nby+nbh
            self._panel_btn(screen.surface, nbx+nbw+4, nby, nbw, nbh, '-->', h_next)
            if h_next: self.quest_hover_btn = 'next'
            sbx, sby = px0+50, py0+42
            sbw, sbh = 52, 10
            h_sel = sbx <= mx <= sbx+sbw and sby <= my <= sby+sbh
            self._panel_btn(screen.surface, sbx, sby, sbw, sbh, 'SELECT', h_sel)
            if h_sel: self.quest_hover_btn = 'select'

    def _draw_panel_mode_score(self, screen):
        pw, ph = 130, 50
        px0 = (160 - pw) // 2
        py0 = (90 - ph) // 2
        import pygame
        bg = pygame.Surface((pw, ph))
        bg.fill((22, 20, 35))
        screen.surface.blit(bg, (px0, py0))
        pygame.draw.rect(screen.surface, (100, 90, 80), (px0, py0, pw, ph), 1)
        inner = pygame.Surface((pw-4, ph-4))
        inner.fill((28, 25, 42))
        screen.surface.blit(inner, (px0+2, py0+2))
        self._render_text('BLUEPRINT COMPLETE', screen.surface, px0+8, py0+6, (200, 200, 200))
        self._render_text(self.quest_panel_score, screen.surface, px0+12, py0+22, (255, 240, 200))
        from pygaminal.input_manager import InputManager
        im = InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ''
        bx, by, bw, bh = px0+30, py0+37, 60, 9
        h_ok = bx <= mx <= bx+bw and by <= my <= by+bh
        self._panel_btn(screen.surface, bx, by, bw, bh, 'OK', h_ok)
        if h_ok: self.quest_hover_btn = 'ok'

    def _quest_toggle(self):
        if self.quest_scored:
            return
        if self.quest_score_timer > 0:
            return
        if not self.quest_active:
            # Just open the menu panel
            self.quest_panel_open = True
            self.quest_panel_mode = "menu"
        elif self.quest_placed:
            # Score it and show panel
            w, h = self.quest_template.get_rect()
            c, t, p = self.quest_template.score(
                lambda x, y: self.cm.get_cell(x, y),
                self.quest_wx, self.quest_wy
            )
            self.quest_score = p
            self.quest_panel_score = f"{p}%"
            self.quest_panel_mode = "score"
            self.quest_panel_open = True
            self.quest_scored = True
            self.quest_placed = False
            self.quest_active = False
        elif self.quest_placing:
            self.quest_active = False
            self.quest_placing = False
            self.quest_template = None

    def _place_quest(self, wx, wy):
        w, h = self.quest_template.get_rect()
        self.quest_wx = wx - w // 2
        self.quest_wy = wy - h // 2
        self.quest_placed = True
        self.quest_placing = False
        print(f'Quest placed at ({self.quest_wx},{self.quest_wy})')

    def _draw_quest(self):
        if not self.quest_template and not self.quest_scored:
            return
        
        # Score display mode (countdown)
        if self.quest_score_timer > 0 and self.quest_template:
            wx, wy = self.quest_wx, self.quest_wy
            w, h = self.quest_template.get_rect()
            self._quest_surf.fill((0, 0, 0, 0))

            # Draw dimmed template outline at world pos
            for ty in range(h):
                for tx in range(w):
                    if self.quest_template.grid[ty][tx] == 1:
                        sx = int((wx + tx - self.camera.x) * 2)
                        sy = int((wy + ty - self.camera.y) * 2)
                        for by in range(2):
                            for bx in range(2):
                                px, py = sx + bx, sy + by
                                if 0 <= px < 160 and 0 <= py < 90:
                                    self._quest_surf.set_at((px, py), (180, 220, 255, 100))

            # Score label at world pos below template using bitmap font
            text_rows = self.quest_template.render_text(self.quest_score_text)
            score_x = int((wx - self.camera.x) * 2)
            score_y = int((wy - 2 - self.camera.y) * 2)
            mfw, mfh = Template.FONT_W, Template.FONT_H
            for row in range(mfh):
                for col in range(len(text_rows[row])):
                    if text_rows[row][col] == '1':
                        px, py = score_x + col, score_y + row
                        if 0 <= px < 160 and 0 <= py < 90:
                            self._quest_surf.set_at((px, py), (255, 240, 200))

            Screen().surface.blit(self._quest_surf, (0, 0))
            return

        if not self.quest_template:
            return

        w, h = self.quest_template.get_rect()

        if self.quest_placing:
            wx, wy = self._get_world_pos()
            wx -= w // 2
            wy -= h // 2
        elif self.quest_placed:
            wx, wy = self.quest_wx, self.quest_wy
        else:
            return

        self._quest_surf.fill((0, 0, 0, 0))

        # Draw template content (blue)
        for ty in range(h):
            for tx in range(w):
                if self.quest_template.grid[ty][tx] == 1:
                    sx = int((wx + tx - self.camera.x) * 2)
                    sy = int((wy + ty - self.camera.y) * 2)
                    for by in range(2):
                        for bx in range(2):
                            px, py = sx + bx, sy + by
                            if 0 <= px < 160 and 0 <= py < 90:
                                self._quest_surf.set_at((px, py), (180, 220, 255, 100))

        # Corner markers (gold, 2px outside)
        margin = 1
        for cwx, cwy in [
            (wx - margin, wy - margin),
            (wx + w - 1 + margin, wy - margin),
            (wx - margin, wy + h - 1 + margin),
            (wx + w - 1 + margin, wy + h - 1 + margin),
        ]:
            sx = int((cwx - self.camera.x) * 2)
            sy = int((cwy - self.camera.y) * 2)
            for by in range(2):
                for bx in range(2):
                    px, py = sx + bx, sy + by
                    if 0 <= px < 160 and 0 <= py < 90:
                        self._quest_surf.set_at((px, py), (255, 60, 60, 180))

        Screen().surface.blit(self._quest_surf, (0, 0))

    def _draw_quest_btn(self):
        import pygame
        screen = Screen()
        im = InputManager()
        mx, my = im.get_mouse_position()
        bx, by = 155, 35
        self._quest_btn_rect = (bx, by, 5, 15)
        if self.quest_scored or self.quest_placing or self.quest_placed:
            color = (80, 90, 60) if not (bx <= mx <= bx+5 and by <= my <= by+15) else (110, 130, 80)
        else:
            color = (60, 60, 70) if not (bx <= mx <= bx+5 and by <= my <= by+15) else (90, 90, 100)
        pygame.draw.rect(screen.surface, color, (bx, by, 5, 15))


    def _draw_panel(self):
        screen = Screen()
        if self.quest_panel_mode == "menu":
            self._draw_panel_mode_select(screen)
        elif self.quest_panel_mode == "score":
            self._draw_panel_mode_score(screen)

    def _handle_panel_click(self, mx, my):
        if self.quest_panel_mode == "menu":
            pw, ph = 130, 62
            px0 = (160 - pw) // 2
            py0 = (90 - ph) // 2
            nbw, nbh = 24, 10
            nbx, nby = px0+50, py0+28
            sbx, sby = px0+50, py0+42
            sbw, sbh = 52, 10
            if nbx <= mx <= nbx+nbw and nby <= my <= nby+nbh and self.quest_candidates:
                self.quest_candidate_idx = (self.quest_candidate_idx - 1) % len(self.quest_candidates)
            if nbx+nbw+4 <= mx <= nbx+nbw*2+4 and nby <= my <= nby+nbh and self.quest_candidates:
                self.quest_candidate_idx = (self.quest_candidate_idx + 1) % len(self.quest_candidates)
            if sbx <= mx <= sbx+sbw and sby <= my <= sby+sbh and self.quest_candidates:
                self.quest_template = self.quest_candidates[self.quest_candidate_idx]
                self.quest_active = True
                self.quest_placing = True
                self.quest_placed = False
                self.quest_panel_open = False
                self.quest_scored = False
        elif self.quest_panel_mode == "score":
            pw, ph = 130, 50
            px0 = (160 - pw) // 2
            py0 = (90 - ph) // 2
            bx, by, bw, bh = px0+30, py0+37, 60, 9
            if bx <= mx <= bx+bw and by <= my <= by+bh:
                self.quest_panel_open = False
                self.quest_panel_mode = "menu"
                self.quest_template = None
                self.quest_panel_score = ""
                self.quest_scored = False
                self.quest_placed = False
                self.quest_hover_btn = ""

    def _draw_debug(self):
        font = pygame.font.SysFont("monospace", 10)
        total = sum(c.filled_count for c in self.cm.chunks.values())
        lines = [
            f"frame {self.cm.frame}", f"particles {total}",
            f"player ({int(self.player.x)},{int(self.player.y)})",
            f"cam ({int(self.camera.x)},{int(self.camera.y)})",
            f"chunks {len(self.cm.chunks)}",
            f"brush: {["sand","water","wet","eraser","quest"][self.current_type-1]} r={self.brush_radius}",
            f"fps: {App().clock.get_fps():.0f}" if App().clock else "fps: ?",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (255, 255, 200))
            Screen().surface.blit(surf, (2, 2 + i * 12))
