"""
Player.py — character controller with physics, animation, and grid collision.

Embedded inside Simulation (not a standalone scene object) so it has
direct access to the Grid for collision and displacement.
"""

import pygame
from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager
from scripts.Grid import WIDTH, HEIGHT

# ── physics constants ─────────────────────────────────────
GRAVITY = 0.35
MOVE_SPEED = 1.0
JUMP_VEL = -3.0
MAX_FALL = 7.0
COYOTE_FRAMES = 6


class Player:
    """2D character that walks on sand, jumps, and interacts."""

    def __init__(self, grid):
        self.grid = grid

        self.idle_img = pygame.image.load("assets/player-idle.png")
        self.hitbox_img = pygame.image.load("assets/player_hitbox.png")

        walk_sheet = pygame.image.load("assets/player-walk.png")
        self.walk_frames = []
        for i in range(4):
            f = pygame.Surface((8, 8), pygame.SRCALPHA)
            f.blit(walk_sheet, (0, 0), (i * 8, 0, 8, 8))
            self.walk_frames.append(f)

        interact_sheet = pygame.image.load("assets/player-interact.png")
        self.interact_frames = []
        for i in range(2):
            f = pygame.Surface((8, 8), pygame.SRCALPHA)
            f.blit(interact_sheet, (0, 0), (i * 8, 0, 8, 8))
            self.interact_frames.append(f)

        # ── state ──────────────────────────────────────────
        self.x = 140.0
        self.y = 75.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0

        self.anim = "idle"
        self.anim_frame = 0.0
        self.interact_trigger = False

    # ── physics ────────────────────────────────────────────

    def _solid(self, x, y):
        if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
            return True
        return self.grid.grid[y][x] == 1

    def _hitbox_free(self, rx, ry):
        hit_x1 = int(rx + 2)
        hit_y1 = int(ry + 2)
        hit_x2 = hit_x1 + 3
        hit_y2 = hit_y1 + 5
        if hit_x2 >= WIDTH or hit_y2 >= HEIGHT:
            return False
        if hit_x1 < 0:
            return False
        for gy in range(max(0, hit_y1), hit_y2 + 1):
            for gx in range(hit_x1, hit_x2 + 1):
                if self._solid(gx, gy):
                    return False
        return True

    def update(self, _obj):
        im = InputManager()

        dx = 0
        if pygame.K_a in im.pressed_keys:
            dx -= 1
            self.facing = -1
        if pygame.K_d in im.pressed_keys:
            dx += 1
            self.facing = 1

        want_jump = (pygame.K_w in im.just_pressed_keys or
                     pygame.K_SPACE in im.just_pressed_keys)
        if want_jump and (self.on_ground or self.coyote > 0):
            self.vy = JUMP_VEL
            self.on_ground = False
            self.coyote = 0

        self.interact_trigger = (im.is_mouse_pressed(1) or
                                  im.is_mouse_pressed(3))

        # ── horizontal ─────────────────────────────────────
        if dx != 0:
            new_x = self.x + dx * MOVE_SPEED
            if self._hitbox_free(new_x, self.y):
                self.x = new_x
            elif self.on_ground and self._hitbox_free(new_x, self.y - 1):
                self.x = new_x
                self.y -= 1
                self.vy = 0

        # ── vertical ───────────────────────────────────────
        self.vy += GRAVITY
        if self.vy > MAX_FALL:
            self.vy = MAX_FALL

        self.y += self.vy
        if not self._hitbox_free(self.x, self.y):
            if self.vy > 0:
                self.y = int(self.y)
                for _ in range(8):
                    if self._hitbox_free(self.x, self.y):
                        break
                    self.y -= 1
                self.vy = 0
                if self._hitbox_free(self.x, self.y):
                    self.on_ground = True
            else:
                self.y = int(self.y)
                for _ in range(8):
                    if self._hitbox_free(self.x, self.y):
                        break
                    self.y += 1
                self.vy = 0

        # ── push-out ──────────────────────────────────────
        if not self._hitbox_free(self.x, self.y):
            found = False
            for r in range(1, 5):
                for d in (r, -r):
                    if self._hitbox_free(self.x + d, self.y):
                        self.x += d; found = True; break
                if found: break
                if self._hitbox_free(self.x, self.y - r):
                    self.y -= r; found = True; break
                for d in (r, -r):
                    if self._hitbox_free(self.x + d, self.y - r):
                        self.x += d; self.y -= r; found = True; break
                if found: break
                for d in (r, -r):
                    if self._hitbox_free(self.x + d, self.y + r):
                        self.x += d; self.y += r; found = True; break
                if found: break
                for dy in range(1, r):
                    for d in (r, -r):
                        if self._hitbox_free(self.x + d, self.y - dy):
                            self.x += d; self.y -= dy; found = True; break
                        if self._hitbox_free(self.x + d, self.y + dy):
                            self.x += d; self.y += dy; found = True; break
                    if found: break
                if found: break
            if found:
                self.vy = 0
                self.on_ground = not self._hitbox_free(self.x, self.y + 1)

        # ── ground check + coyote time ──────────────────────
        self.on_ground = not self._hitbox_free(self.x, self.y + 1)
        self.coyote = COYOTE_FRAMES if self.on_ground else max(0, self.coyote - 1)

        # ── animation ──────────────────────────────────────
        moving = dx != 0
        self.anim = "interact" if self.interact_trigger else ("walk" if moving and self.on_ground else "idle")
        speed_map = {"idle": 0, "walk": 0.12, "interact": 0.10}
        frame_count = {"idle": 1, "walk": 4, "interact": 2}
        self.anim_frame += speed_map[self.anim]
        if self.anim_frame >= frame_count[self.anim]:
            self.anim_frame -= frame_count[self.anim]

    def current_sprite(self):
        options = {"walk": self.walk_frames, "interact": self.interact_frames}
        frames = options.get(self.anim, [self.idle_img])
        frame = min(int(self.anim_frame), len(frames) - 1)
        surf = frames[frame]
        if self.facing < 0:
            surf = pygame.transform.flip(surf, True, False)
        return surf

    def draw(self, _obj):
        Screen().surface.blit(self.current_sprite(), (self.x, self.y))
