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
        self.sim_surf = pygame.Surface((WIDTH, HEIGHT))
        self._load_particle_types()

        # Brush state
        self.current_type = 1          # 1=sand, 2=water, 3=wet sand
        self.brush_radius = 3
        self.spawn_rate = 8
        self._cursor_pos = (0, 0)      # for cursor drawing

        # Eraser state
        self.eraser_active = False

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

        self._show_debug = False
        self.sim_surf.fill(BG_COLOR)

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
        # Determine initial wetness for sand brush
        initial_wet = 0
        if t == 3:
            t = 1
            initial_wet = 3.0      # pre-wetted sand

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
        """Remove only water particles within the brush circle — sand stays."""
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    nx, ny = gx + dx, gy + dy
                    if 0 <= nx < WIDTH and 0 <= ny < HEIGHT:
                        if self.grid.grid[ny][nx] == 2:
                            self.grid.grid[ny][nx] = EMPTY
                            self.grid.water_charge[ny][nx] = 0
                            self.grid.dirty.append((nx, ny))

    # ── input ──────────────────────────────────────────────

    def _handle_input(self) -> None:
        im = InputManager()

        # Switch brush type
        if pygame.K_1 in im.just_pressed_keys:
            self.current_type = 1          # dry sand
        elif pygame.K_2 in im.just_pressed_keys:
            self.current_type = 2          # water
        elif pygame.K_3 in im.just_pressed_keys:
            self.current_type = 3          # wet sand (pre-wetted)
        elif pygame.K_4 in im.just_pressed_keys:
            self.current_type = 4          # water eraser
        elif pygame.K_d in im.just_pressed_keys:
            self._show_debug = not self._show_debug

        # Brush radius — [ ] - = wheel numpad+ numpad-
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

        # Left mouse → paint / water-erase
        if im.is_mouse_pressed(1):
            if self.current_type == 4:
                self._water_erase(gx, gy, r)
            else:
                self._paint(gx, gy, r)

        # Right mouse → erase
        if im.is_mouse_pressed(3):
            self._erase(gx, gy, r)

    # ── per-frame update / render ──────────────────────────

    def update(self, obj) -> None:
        """Called by pygaminal every frame."""
        self._handle_input()
        self.grid.step()
        self._render()

    def _render(self) -> None:
        """Redraw only dirty cells onto our 160×90 surface."""
        for (x, y) in self.grid.dirty:
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                continue
            tid = self.grid.grid[y][x]
            if tid == EMPTY:
                self.sim_surf.set_at((x, y), BG_COLOR)
            elif tid == 1:
                # Sand — colour depends on wetness
                raw = self.grid.wetness[y][x]
                w = 0 if raw <= 0.0 else min(int(raw + 0.99), 3)
                self.sim_surf.set_at((x, y), SAND_COLORS[w])
            else:
                info = self.grid.particle_types.get(tid)
                self.sim_surf.set_at((x, y), info["color"] if info else (255, 255, 255))
        self.grid.dirty.clear()

    def draw(self, obj) -> None:
        """Blit sim surface → Screen surface (both 160×90). SCALED handles display."""
        Screen().surface.blit(self.sim_surf, (0, 0))

        self._draw_toolbar()
        self._draw_cursor()

        if self._show_debug:
            self._draw_debug()

    def _draw_toolbar(self) -> None:
        """Draw tool selector icons (3×3 squares, no gap, +2 offset)."""
        screen = Screen()
        ox, oy = 2, 2

        for tid in (1, 2, 3, 4):
            tx = ox + (tid - 1) * 3
            screen.surface.blit(self._tool_icons[tid], (tx, oy))

        # highlight on top of everything
        sel = self.current_type
        sx = ox + (sel - 1) * 3
        pygame.draw.rect(screen.surface, (200, 200, 200),
                         (sx - 1, oy - 1, 5, 5), 1)

    def _draw_cursor(self) -> None:
        """Draw brush pattern matching spawn logic exactly (dx²+dy² ≤ r²)."""
        cx, cy = self._cursor_pos
        r = self.brush_radius

        self._cursor_surf.fill((0, 0, 0, 0))
        color = (255, 240, 200)

        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = cx + dx, cy + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        self._cursor_surf.set_at((px, py), color)

        self._cursor_surf.set_alpha(100)
        Screen().surface.blit(self._cursor_surf, (0, 0))

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
