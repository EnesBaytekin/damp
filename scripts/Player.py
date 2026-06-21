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
MOVE_SPEED = 1.2
JUMP_VEL = -4.5
MAX_FALL = 7.0
COYOTE_FRAMES = 6


class Player:
    """2D character that walks on sand, jumps, and interacts."""

    def __init__(self, grid):
        self.grid = grid

        # ── load sprites ───────────────────────────────────
        self.idle_img = pygame.image.load("assets/player-idle.png")
        self.hitbox_img = pygame.image.load("assets/player_hitbox.png")  # debug overlay

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
        self.x = 140.0          # bottom-right, clear of graffiti
        self.y = 75.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1          # 1 = right, -1 = left
        self.coyote = 0

        # animation (idle / walk / interact)
        self.anim = "idle"
        self.anim_frame = 0.0
        self.interact_trigger = False   # set by Simulation when painting

    # ── physics ────────────────────────────────────────────

    def _solid(self, x, y):
        """True if grid cell (x, y) is solid (sand) or out-of-bounds."""
        if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
            return True
        return self.grid.grid[y][x] == 1

    def _rect_free(self, rx, ry, w=8, h=8):
        """True if the 8×8 rect at (rx, ry) does NOT touch any solid cell."""
        x1, y1 = int(rx), int(ry)
        x2, y2 = int(rx + w - 1), int(ry + h - 1)

        if x1 < 0 or x2 >= WIDTH or y2 >= HEIGHT:
            return False
        if y1 < 0:
            y1 = 0  # allow jumping above the grid

        for gy in range(y1, y2 + 1):
            for gx in range(x1, x2 + 1):
                if self._solid(gx, gy):
                    return False
        return True

    def update(self, _obj):
        """Tick physics & animation. Called each frame by Simulation."""
        im = InputManager()

        # ── input ──────────────────────────────────────────
        dx = 0
        if pygame.K_a in im.pressed_keys:
            dx -= 1
            self.facing = -1
        if pygame.K_d in im.pressed_keys:
            dx += 1
            self.facing = 1

        # Jump
        want_jump = (pygame.K_w in im.just_pressed_keys or
                     pygame.K_SPACE in im.just_pressed_keys)
        if want_jump and (self.on_ground or self.coyote > 0):
            self.vy = JUMP_VEL
            self.on_ground = False
            self.coyote = 0

        # Interact check (used by Simulation to set anim trigger)
        self.interact_trigger = (im.is_mouse_pressed(1) or
                                  im.is_mouse_pressed(3))

        # ── horizontal ─────────────────────────────────────
        new_x = self.x + dx * MOVE_SPEED
        if self._rect_free(new_x, self.y):
            self.x = new_x

        # ── gravity ────────────────────────────────────────
        self.vy += GRAVITY
        if self.vy > MAX_FALL:
            self.vy = MAX_FALL

        # ── vertical ───────────────────────────────────────
        self.y += self.vy
        if not self._rect_free(self.x, self.y):
            if self.vy > 0:             # landing
                self.y = int(self.y)
                while not self._rect_free(self.x, self.y):
                    self.y -= 1
                self.vy = 0
                self.on_ground = True
            else:                         # hit head
                self.y = int(self.y)
                while not self._rect_free(self.x, self.y):
                    self.y += 1
                self.vy = 0

        # ── coyote time ────────────────────────────────────
        if self.on_ground:
            self.coyote = COYOTE_FRAMES
        else:
            self.coyote -= 1

        # ── ground check ───────────────────────────────────
        self.on_ground = not self._rect_free(self.x, self.y + 1)

        # ── animation ──────────────────────────────────────
        moving = dx != 0
        if self.interact_trigger:
            self.anim = "interact"
        elif moving and self.on_ground:
            self.anim = "walk"
        else:
            self.anim = "idle"

        # Advance frame
        speed_map = {"idle": 0, "walk": 0.12, "interact": 0.10}
        frame_count = {"idle": 1, "walk": 4, "interact": 2}
        self.anim_frame += speed_map.get(self.anim, 0.1)
        fc = frame_count.get(self.anim, 1)
        if self.anim_frame >= fc:
            self.anim_frame -= fc

    def current_sprite(self):
        """Return the current animation frame as a Surface."""
        frame = int(self.anim_frame)
        if self.anim == "walk":
            surf = self.walk_frames[frame]
        elif self.anim == "interact":
            surf = self.interact_frames[frame]
        else:
            surf = self.idle_img

        # Flip sprite if facing left
        if self.facing < 0:
            surf = pygame.transform.flip(surf, True, False)
        return surf

    def draw(self, _obj):
        """Draw the player on the screen surface."""
        sp = self.current_sprite()
        # Centre the 8×8 sprite on the player's float position
        Screen().surface.blit(sp, (self.x, self.y))
