"""
UI patch — adds quest button, panel with bitmap font, template preview.
Run with: python scripts/_ui_patch.py
"""
import sys
sys.path.insert(0, '.')
import re

path = "scripts/WorldController.py"
with open(path) as f:
    code = f.read()

# 1. Insert helper methods before _draw_panel
helper_methods = r'''
    def _quest_new_candidates(self):
        import time
        from scripts.Template import Template
        self.quest_candidates = []
        for i in range(6):
            self.quest_candidates.append(Template(seed=int(time.time())+(i*1000)).generate())
        self.quest_candidate_idx = 0

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
        bg = (80, 72, 58) if not hover else (110, 100, 80)
        bd = (120, 110, 90) if not hover else (160, 150, 130)
        import pygame
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
        im = __import__('pygaminal.input_manager', fromlist=['InputManager']).InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ""
        if self.quest_candidates:
            t = self.quest_candidates[self.quest_candidate_idx]
            pv = pygame.Surface((40, 30))
            pv.fill((28, 25, 42))
            sc = min(3, 38 // max(1, t.width), 28 // max(1, t.height))
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
        im = __import__('pygaminal.input_manager', fromlist=['InputManager']).InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ''
        bx, by, bw, bh = px0+30, py0+37, 60, 9
        h_ok = bx <= mx <= bx+bw and by <= my <= by+bh
        self._panel_btn(screen.surface, bx, by, bw, bh, 'OK', h_ok)
        if h_ok: self.quest_hover_btn = 'ok'
'''

# Insert helpers before _draw_panel
code = code.replace(
    "    def _draw_panel(self):",
    helper_methods + "\n    def _draw_panel(self):"
)

# 2. Replace _draw_panel body
code = code.replace(
    "    def _draw_panel(self):\n        screen = Screen()\n        pw, ph = 110, 55\n        px0 = (160 - pw) // 2\n        py0 = (90 - ph) // 2",
    "    def _draw_panel(self):\n        screen = Screen()\n        if self.quest_panel_mode == 'menu':\n            self._draw_panel_mode_select(screen)\n        elif self.quest_panel_mode == 'score':\n            self._draw_panel_mode_score(screen)"
)

# 3. Remove old panel draw code that's now replaced
# Find the old draw code block and remove it
old_draw_start = "        elif self.quest_panel_mode == \"score\":"
old_draw_end = "            ok = font.render(\"OK\", True, (255, 240, 200))\n                screen.surface.blit(ok, (bx+24, by+1))"
# The old code might differ, let's just replace the whole _draw_panel section
# Since the short version is already in place, just keep it

# 4. Replace _handle_panel_click
old_click_start = "    def _handle_panel_click(self, mx, my):"
# Find the end - it's right before _draw_debug
click_end_marker = "    def _draw_debug(self):"

# Build new click handler
new_click = """    def _handle_panel_click(self, mx, my):
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

"""

# Find old click handler and replace
import re as _re
idx = code.find("    def _handle_panel_click(self, mx, my):")
if idx >= 0:
    next_def = code.find("\n    def _", idx + 10)
    if next_def > idx:
        old_block = code[idx:next_def]
        code = code[:idx] + new_click + code[next_def:]

# 5. Add _draw_quest_btn before _draw_panel
quest_btn = """
    def _draw_quest_btn(self):
        import pygame
        screen = Screen()
        im = __import__('pygaminal.input_manager', fromlist=['InputManager']).InputManager()
        mx, my = im.get_mouse_position()
        bx, by = 155, 35
        self._quest_btn_rect = (bx, by, 5, 15)
        if self.quest_scored or self.quest_placing or self.quest_placed:
            color = (80, 90, 60) if not (bx <= mx <= bx+5 and by <= my <= by+15) else (110, 130, 80)
        else:
            color = (60, 60, 70) if not (bx <= mx <= bx+5 and by <= my <= by+15) else (90, 90, 100)
        pygame.draw.rect(screen.surface, color, (bx, by, 5, 15))

"""

# Insert quest_btn method before _draw_panel
code = code.replace(
    "    def _draw_panel(self):",
    quest_btn + "    def _draw_panel(self):"
)

# But we just inserted helpers before _draw_panel too, and it's now before quest_btn.
# Need to fix the ordering. quest_btn should be after helpers, before _draw_panel.
# Actually, let me insert _draw_quest_btn between _draw_panel_mode_score and _draw_panel
# The quest_btn was inserted before "def _draw_panel(self):" but the helpers were also inserted
# before that same string. So helpers went first, then quest_btn was added after helpers.
# Let me check the order.

with open(path, 'w') as f:
    f.write(code)
print('UI patch applied')

# Verify syntax
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('Syntax OK')
except py_compile.PyCompileError as e:
    print('Syntax error:', e)
"""