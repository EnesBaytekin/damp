"""
Player.py — character controller with infinite-world physics.
Uses ChunkManager for collision instead of a fixed Grid.
"""

import pygame
from pygaminal.screen import Screen
from pygaminal.input_manager import InputManager

# ── physics constants ─────────────────────────────────────
GRAVITY = 0.35
MOVE_SPEED = 1.0
JUMP_VEL = -3.0
MAX_FALL = 7.0
COYOTE_FRAMES = 6


class Player:
    """2D character in an infinite world."""

    def __init__(self, chunk_manager):
        self.cm = chunk_manager

        self.idle_img = pygame.image.load("assets/player-idle.png")
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

        self.x = 0.0
        self.y = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0
        self.anim = "idle"
        self.anim_frame = 0.0
        self.interact_trigger = False

    # ── physics ────────────────────────────────────────────

    def _solid(self, wx: int, wy: int) -> bool:
        if wy >= 90:
            return True
        if wy < 0:
            return False
        return self.cm.get_cell(wx, wy) == 1

    def _hitbox_free(self, rx: float, ry: float) -> bool:
        """True if the 4×6 hitbox (offset +2,+2) at (rx, ry) is clear."""
        x1, y1 = int(rx + 2), int(ry + 2)
        x2, y2 = x1 + 3, y1 + 5
        for gy in range(y1, y2 + 1):
            for gx in range(x1, x2 + 1):
                if self._solid(gx, gy):
                    return False
        return True

    def update(self, _obj=None):
        im = InputManager()

        dx = 0
        if pygame.K_a in im.pressed_keys:
            dx -= 1; self.facing = -1
        if pygame.K_d in im.pressed_keys:
            dx += 1; self.facing = 1

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
            nx = self.x + dx * MOVE_SPEED
            if self._hitbox_free(nx, self.y):
                self.x = nx
            elif self.on_ground and self._hitbox_free(nx, self.y - 1):
                self.x = nx
                self.y -= 1
                self.vy = 0

        # ── vertical ───────────────────────────────────────
        self.vy += GRAVITY
        if self.vy > MAX_FALL:
            self.vy = MAX_FALL

        self.y += self.vy
        if not self._hitbox_free(self.x, self.y):
            if self.vy > 0:  # landing
                self.y = int(self.y)
                for _ in range(8):
                    if self._hitbox_free(self.x, self.y):
                        break
                    self.y -= 1
                self.vy = 0
                self.on_ground = True
            else:  # hit head
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

        # ── ground check + coyote ────────────────────────────
        self.on_ground = not self._hitbox_free(self.x, self.y + 1)
        self.coyote = COYOTE_FRAMES if self.on_ground else max(0, self.coyote - 1)

        # ── animation ──────────────────────────────────────
        moving = dx != 0
        self.anim = "interact" if self.interact_trigger else ("walk" if moving and self.on_ground else "idle")
        speed_map = {"idle": 0, "walk": 0.12, "interact": 0.10}
        fc_map = {"idle": 1, "walk": 4, "interact": 2}
        self.anim_frame += speed_map[self.anim]
        if self.anim_frame >= fc_map[self.anim]:
            self.anim_frame -= fc_map[self.anim]

    def current_sprite(self):
        opt = {"walk": self.walk_frames, "interact": self.interact_frames}
        frames = opt.get(self.anim, [self.idle_img])
        sf = frames[min(int(self.anim_frame), len(frames) - 1)]
        if self.facing < 0:
            sf = pygame.transform.flip(sf, True, False)
        return sf

    def draw(self, camera=None):
        if camera:
            sx, sy = camera.world_to_screen(self.x, self.y)
        else:
            sx, sy = int(self.x), int(self.y)
        Screen().surface.blit(self.current_sprite(), (sx, sy))
