"""
Simulation.py — Pygaminal ScriptComponent.

Owns the Grid, loads particle type definitions from .obj files,
handles mouse / keyboard input, runs the simulation step, and
renders the result to Screen() every frame.

Scene logical resolution is 160×90 — pygaminal's SCALED flag
handles scaling to the actual display.
"""

import importlib
import json
import os
import pygame

from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager
from pygaminal.app import App

from scripts.Grid import Grid, WIDTH, HEIGHT, EMPTY


# ── colour palette ──────────────────────────────────────────
BG_COLOR = (0x1a, 0x1a, 0x2e)       # dark navy (empty cells)

# Sand colour per wetness level (0 → 3)
SAND_COLORS = [
    (194, 178, 128),   # 0 dry
    (170, 150, 100),   # 1 damp
    (140, 120,  80),   # 2 wet
    (100,  80,  50),   # 3 soggy
]


class Simulation:
    """Main simulation controller — one instance, attached to the scene object."""

    def __init__(self):
        self.grid = Grid()
        self.sim_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._load_particle_types()

        # Brush state
        self.current_type = 1          # 1=sand, 2=water, 3=wet sand
        self.brush_radius = 3
        self.spawn_rate = 8
        self._cursor_pos = (0, 0)      # for cursor drawing

        # Eraser state
        self.eraser_active = False

        # Line-drag state
        self._line_start = None   # (x, y) when ctrl+click started
        self._line_end = None     # current mouse during drag
        self._line_button = 0     # 1=paint, 3=erase

        # Cursor overlay surface (per-pixel alpha)
        self._cursor_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        # ── tool icons (3×3 squares, no gap) ─────────────────
        self._tool_icons = {}
        icon_colors = {
            1: (194, 178, 128),   # sand
            2: (64, 164, 223),    # water
            3: (100, 80, 50),     # wet sand
            4: (90, 90, 90),      # water eraser
        }
        for tid, color in icon_colors.items():
            surf = pygame.Surface((3, 3))
            surf.fill(color)
            self._tool_icons[tid] = surf

        # ── menu state ──────────────────────────────────────
        self._menu_active = True
        self._menu_options = ["PLAY", "QUIT"]
        self._menu_index = 0
        self._menu_drip_timer = 0

        # ── graffiti ────────────────────────────────────────
        self._write_graffiti()

        self._show_debug = False
        self.sim_surf.fill((0, 0, 0, 0))  # transparent

    # ── graffiti writer ────────────────────────────────────

    def _write_graffiti(self) -> None:
        """Read menu.png template, fill opaque pixels with wet sleeping sand."""
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

    # ── particle-type registry from .obj files ───────────────

    def _load_particle_types(self) -> None:
        """Scan ``objects/particles/*.obj`` and register each type."""
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
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[Simulation] skip {path}: {exc}")
                continue

            type_id = data.get("type_id")
            if not type_id:
                continue

            update_fn = None
            script_ref = data.get("script")
            if script_ref:
                mod_path = script_ref.replace(".py", "").replace("/", ".")
                try:
                    mod = importlib.import_module(mod_path)
                    update_fn = getattr(mod, "update", None)
                except (ImportError, AttributeError) as exc:
                    print(f"[Simulation] cannot load {script_ref}: {exc}")

            self.grid.register(type_id, {
                "name": data.get("name", "?"),
                "color": tuple(data.get("color", (255, 255, 255))),
                "density": data.get("density", 1),
                "update": update_fn,
            })
            print(f"[Simulation] registered particle type {type_id}: {data.get('name')}")

    # ── helpers ────────────────────────────────────────────

    def _get_brush_pos(self) -> tuple[int, int]:
        """Return the sim-grid coordinates under the mouse cursor, clamped."""
        mx, my = InputManager().get_mouse_position()
        return (
            max(0, min(WIDTH - 1, mx)),
            max(0, min(HEIGHT - 1, my)),
        )

    def _paint(self, gx: int, gy: int, r: int) -> None:
        """Spawn particles in a circle of radius *r* centred on (gx, gy)."""
        t = self.current_type
        initial_wet = 0
        if t == 3:
            t = 1
            initial_wet = 3.0

        for _ in range(self.spawn_rate):
            dx = self.grid.rng.randint(-r, r)
            dy = self.grid.rng.randint(-r, r)
            if dx * dx + dy * dy <= r * r:
                if self.grid.spawn(gx + dx, gy + dy, t):
                    if initial_wet:
                        self.grid.wetness[gy + dy][gx + dx] = initial_wet

    def _erase(self, gx: int, gy: int, r: int) -> None:
        """Remove any particles within the brush circle."""
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    nx, ny = gx + dx, gy + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                        if self.grid.grid[ny][nx] != EMPTY:
                            self.grid.grid[ny][nx] = EMPTY
                            self.grid.dirty.append((nx, ny))

    def _water_erase(self, gx: int, gy: int, r: int) -> None:
        """Remove only water within the brush circle — sand stays."""
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    nx, ny = gx + dx, gy + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                        if self.grid.grid[ny][nx] == 2:
                            self.grid.grid[ny][nx] = EMPTY
                            self.grid.water_charge[ny][nx] = 0
                            self.grid.dirty.append((nx, ny))

    def _line_cells(self, x0, y0, x1, y1):
        """Bresenham line — yield (x, y) for every cell on the line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            yield x, y
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def _apply_brush_at(self, gx, gy):
        r = self.brush_radius
        if self._line_button == 3:
            self._erase(gx, gy, r)
        elif self.current_type == 4:
            self._water_erase(gx, gy, r)
        else:
            self._paint(gx, gy, r)

    # ── input ──────────────────────────────────────────────

    def _handle_input(self) -> None:
        im = InputManager()

        if self._menu_active:
            self._handle_menu_input(im)
            return

        if pygame.K_1 in im.just_pressed_keys:
            self.current_type = 1
        elif pygame.K_2 in im.just_pressed_keys:
            self.current_type = 2
        elif pygame.K_3 in im.just_pressed_keys:
            self.current_type = 3
        elif pygame.K_4 in im.just_pressed_keys:
            self.current_type = 4
        elif pygame.K_d in im.just_pressed_keys:
            self._show_debug = not self._show_debug
        elif pygame.K_ESCAPE in im.just_pressed_keys:
            self._menu_active = True
            return

        shrink = (pygame.K_LEFTBRACKET in im.just_pressed_keys or
                  pygame.K_MINUS in im.just_pressed_keys or
                  pygame.K_KP_MINUS in im.just_pressed_keys or
                  im.wheel_y < 0)
        grow   = (pygame.K_RIGHTBRACKET in im.just_pressed_keys or
                  pygame.K_EQUALS in im.just_pressed_keys or
                  pygame.K_KP_PLUS in im.just_pressed_keys or
                  im.wheel_y > 0)
        if shrink:
            self.brush_radius = max(0, self.brush_radius - 1)
        elif grow:
            self.brush_radius = min(10, self.brush_radius + 1)

        gx, gy = self._get_brush_pos()
        self._cursor_pos = (gx, gy)
        r = self.brush_radius

        ctrl = pygame.K_LCTRL in im.pressed_keys or pygame.K_RCTRL in im.pressed_keys

        if ctrl:
            if im.is_mouse_just_pressed(1) or im.is_mouse_just_pressed(3):
                self._line_start = (gx, gy)
                self._line_end = (gx, gy)
                self._line_button = 3 if im.is_mouse_just_pressed(3) else 1
            if self._line_start is not None:
                self._line_end = (gx, gy)
            if (self._line_button == 1 and im.is_mouse_released(1)) or \
               (self._line_button == 3 and im.is_mouse_released(3)):
                for lx, ly in self._line_cells(*self._line_start, *self._line_end):
                    self._apply_brush_at(lx, ly)
                self._line_start = None
                self._line_end = None
                self._line_button = 0
        else:
            self._line_start = None
            self._line_end = None
            self._line_button = 0

            if im.is_mouse_pressed(1):
                if self.current_type == 4:
                    self._water_erase(gx, gy, r)
                else:
                    self._paint(gx, gy, r)

            if im.is_mouse_pressed(3):
                self._erase(gx, gy, r)

    # ── menu input ─────────────────────────────────────────

    def _handle_menu_input(self, im) -> None:
        if pygame.K_UP in im.just_pressed_keys or pygame.K_w in im.just_pressed_keys:
            self._menu_index = (self._menu_index - 1) % len(self._menu_options)
        elif pygame.K_DOWN in im.just_pressed_keys or pygame.K_s in im.just_pressed_keys:
            self._menu_index = (self._menu_index + 1) % len(self._menu_options)
        elif pygame.K_RETURN in im.just_pressed_keys or pygame.K_SPACE in im.just_pressed_keys:
            self._menu_select()
        elif im.is_mouse_just_pressed(1):
            mx, my = im.get_mouse_position()
            # Buttons are right-aligned, bottom area
            mfw, mfh = 5, 7
            mgap = 1
            for i, opt in enumerate(self._menu_options):
                total_w = len(opt) * (mfw + mgap) - mgap
                bx = WIDTH - total_w - 4          # same as draw
                by = HEIGHT - 18 + i * 9
                if bx - 2 <= mx <= bx + total_w + 2 and by - 2 <= my <= by + mfh + 2:
                    self._menu_index = i
                    self._menu_select()
                    return

    def _menu_select(self) -> None:
        if self._menu_options[self._menu_index] == "PLAY":
            self._menu_active = False
        elif self._menu_options[self._menu_index] == "QUIT":
            App().stop()

    # ── per-frame update / render ──────────────────────────

    def update(self, obj) -> None:
        """Called by pygaminal every frame."""
        self._handle_input()

        if self._menu_active:
            self._menu_drip()

        self.grid.step()
        self._render()

    def _render(self) -> None:
        """Redraw only dirty cells onto our 160×90 surface."""
        for (x, y) in self.grid.dirty:
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                continue
            tid = self.grid.grid[y][x]
            if tid == EMPTY:
                self.sim_surf.set_at((x, y), (0, 0, 0, 0))
            elif tid == 1:
                raw = self.grid.wetness[y][x]
                w = 0 if raw <= 0.0 else min(int(raw + 0.99), 3)
                self.sim_surf.set_at((x, y), SAND_COLORS[w])
            else:
                info = self.grid.particle_types.get(tid)
                color = info["color"] if info else (255, 255, 255)
                if tid == 2:
                    color = color[:3] + (160,)
                self.sim_surf.set_at((x, y), color)
        self.grid.dirty.clear()

    def _menu_drip(self) -> None:
        """Spawn random blobs of sand/water from the top during menu."""
        self._menu_drip_timer -= 1
        if self._menu_drip_timer > 0:
            return

        self._menu_drip_timer = self.grid.rng.randint(15, 40)

        is_water = self.grid.rng.random() < 0.25
        ptype = 2 if is_water else 1
        wet = 2.0 if ptype == 1 else 0
        r = self.grid.rng.randint(3, 6)  # radius

        cx = self.grid.rng.randint(r, WIDTH - 1 - r)
        # Spawn a circle of radius r at top
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    x, y = cx + dx, dy
                    if 0 <= x < WIDTH and y < HEIGHT:
                        if self.grid.grid[y][x] == 0:
                            if self.grid.spawn(x, y, ptype):
                                if wet:
                                    self.grid.wetness[y][x] = wet

    def draw(self, obj) -> None:
        """Blit sim surface → Screen surface (both 160×90). SCALED handles display."""
        Screen().surface.blit(self.sim_surf, (0, 0))

        if self._menu_active:
            self._draw_menu()
        else:
            self._draw_toolbar()
            self._draw_cursor()

        if self._show_debug:
            self._draw_debug()

    # ── menu ──────────────────────────────────────────────

    def _draw_menu(self) -> None:
        """Overlay menu UI on top of the running simulation."""
        screen = Screen()

        # ── menu options (pixel font, bottom-right) ──
        MENU_FONT = {
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

        for i, opt in enumerate(self._menu_options):
            color = (255, 240, 200) if i == self._menu_index else (120, 110, 80)
            total_w = len(opt) * (mfw + mgap) - mgap
            ox = WIDTH - total_w - 4          # right-aligned, 4px padding
            oy = HEIGHT - 18 + i * 9          # bottom area, 2px bottom padding

            for ci, ch in enumerate(opt):
                glyph = MENU_FONT.get(ch)
                if not glyph:
                    continue
                for row in range(mfh):
                    for col in range(mfw):
                        if glyph[row][col] == '1':
                            px = ox + ci * (mfw + mgap) + col
                            py = oy + row
                            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                screen.surface.set_at((px, py), color)

    # ── toolbar ───────────────────────────────────────────

    def _draw_toolbar(self) -> None:
        """Draw tool selector icons (3×3 squares, no gap, +2 offset)."""
        screen = Screen()
        ox, oy = 2, 2

        for tid in (1, 2, 3, 4):
            tx = ox + (tid - 1) * 3
            screen.surface.blit(self._tool_icons[tid], (tx, oy))

        sel = self.current_type
        sx = ox + (sel - 1) * 3
        pygame.draw.rect(screen.surface, (200, 200, 200),
                         (sx - 1, oy - 1, 5, 5), 1)

    # ── cursor ────────────────────────────────────────────

    def _draw_cursor(self) -> None:
        """Draw brush pattern + line-drag preview."""
        self._cursor_surf.fill((0, 0, 0, 0))
        color = (255, 240, 200)
        cx, cy = self._cursor_pos
        r = self.brush_radius

        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        self._cursor_surf.set_at((px, py), color)

        if self._line_start is not None and self._line_end is not None:
            for lx, ly in self._line_cells(*self._line_start, *self._line_end):
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx * dx + dy * dy <= r * r:
                            px, py = lx + dx, ly + dy
                            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                                self._cursor_surf.set_at((px, py), color)

        self._cursor_surf.set_alpha(80)
        Screen().surface.blit(self._cursor_surf, (0, 0))

    # ── debug ─────────────────────────────────────────────

    def _draw_debug(self) -> None:
        """Simple stats overlay."""
        font = pygame.font.SysFont("monospace", 10)
        total = sum(1 for row in self.grid.grid for c in row if c != EMPTY)
        asleep = sum(row.count(1) for row in self.grid.asleep)
        type_names = {1: "sand", 2: "water", 3: "wet_sand", 4: "water_eraser"}
        lines = [
            f"frame {self.grid.frame}",
            f"particles {total}  asleep {asleep}",
            f"brush: {type_names.get(self.current_type, '?')} r={self.brush_radius}",
            f"fps: {App().clock.get_fps():.0f}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (255, 255, 200))
            Screen().surface.blit(surf, (2, 2 + i * 12))
