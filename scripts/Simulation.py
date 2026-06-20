"""
Simulation.py — Pygaminal ScriptComponent.

Owns the Grid, loads particle type definitions from .obj files,
handles mouse / keyboard input, runs the simulation step, and
renders the result to Screen() every frame.

The scene logical resolution is 320×180 — pygaminal's SCALED flag
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


class Simulation:
    """Main simulation controller — one instance, attached to the scene object."""

    def __init__(self):
        self.grid = Grid()
        # Private surface at sim resolution (320×180)
        self.sim_surf = pygame.Surface((WIDTH, HEIGHT))
        self._load_particle_types()

        # Brush state
        self.current_type = 1          # default: sand
        self.brush_radius = 3
        self.spawn_rate = 8            # particles per frame while painting

        # Key state
        self._show_debug = False

        # Pre-fill sim surface
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

            # Import the particle update function
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

    # ── input ──────────────────────────────────────────────

    def _handle_input(self) -> None:
        im = InputManager()

        # Switch particle type with number keys
        if pygame.K_1 in im.just_pressed_keys:
            self.current_type = 1
        elif pygame.K_2 in im.just_pressed_keys:
            self.current_type = 2
        elif pygame.K_d in im.just_pressed_keys:
            self._show_debug = not self._show_debug

        # Brush radius with [ and ]
        if pygame.K_LEFTBRACKET in im.just_pressed_keys:
            self.brush_radius = max(1, self.brush_radius - 1)
        elif pygame.K_RIGHTBRACKET in im.just_pressed_keys:
            self.brush_radius = min(10, self.brush_radius + 1)

        # Paint with left mouse button
        # (mouse coords are already in 320×180 logical space thanks to SCALED)
        if im.is_mouse_pressed(1):
            gx, gy = im.get_mouse_position()
            gx = max(0, min(WIDTH - 1, gx))
            gy = max(0, min(HEIGHT - 1, gy))

            r = self.brush_radius
            for _ in range(self.spawn_rate):
                dx = self.grid.rng.randint(-r, r)
                dy = self.grid.rng.randint(-r, r)
                if dx * dx + dy * dy <= r * r:
                    self.grid.spawn(gx + dx, gy + dy, self.current_type)

    # ── per-frame update / render ──────────────────────────

    def update(self, obj) -> None:
        """Called by pygaminal every frame."""
        self._handle_input()
        self.grid.step()
        self._render()

    def _render(self) -> None:
        """Redraw only dirty cells onto our 320×180 surface."""
        for (x, y) in self.grid.dirty:
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                continue
            tid = self.grid.grid[y][x]
            if tid == EMPTY:
                self.sim_surf.set_at((x, y), BG_COLOR)
            else:
                info = self.grid.particle_types.get(tid)
                self.sim_surf.set_at((x, y), info["color"] if info else (255, 255, 255))
        self.grid.dirty.clear()

    def draw(self, obj) -> None:
        """Blit sim surface → Screen surface (both 320×180). SCALED handles display scaling."""
        Screen().surface.blit(self.sim_surf, (0, 0))

        if self._show_debug:
            self._draw_debug()

    def _draw_debug(self) -> None:
        """Simple stats overlay."""
        font = pygame.font.SysFont("monospace", 10)
        total = sum(1 for row in self.grid.grid for c in row if c != EMPTY)
        type_name = {1: "sand", 2: "water"}.get(self.current_type, "?")
        lines = [
            f"frame {self.grid.frame}",
            f"particles {total}",
            f"brush: {type_name} r={self.brush_radius}",
            f"fps: {App().clock.get_fps():.0f}",
        ]
        for i, line in enumerate(lines):
            surf = font.render(line, True, (255, 255, 200))
            Screen().surface.blit(surf, (2, 2 + i * 12))
